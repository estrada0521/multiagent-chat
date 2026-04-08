from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path

from .chat_runtime_format_core import (
    _pane_runtime_gemini_with_occurrence_ids,
    _pane_runtime_with_occurrence_ids,
)
from .chat_sync_cursor_core import _native_path_claim_key


def _get_process_tree(pid: str) -> set[str]:
    """Get all descendant PIDs for a given PID using `ps`."""
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,ppid"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        children_map = {}
        for line in out.splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2:
                c, p = parts[0], parts[1]
                children_map.setdefault(p, []).append(c)

        pids = {pid}
        q = [pid]
        while q:
            curr = q.pop(0)
            for c in children_map.get(curr, []):
                if c not in pids:
                    pids.add(c)
                    q.append(c)
        return pids
    except Exception:
        return {pid}


def _resolve_native_log_file(
    pane_pid: str,
    log_pattern: str,
    base_name: str = "",
) -> str | None:
    """Find an open file matching log_pattern for pane_pid (including descendants)."""
    pids = _get_process_tree(str(pane_pid).strip())
    if not pids:
        return None

    if base_name == "copilot":
        for pid in pids:
            state_dir = Path.home() / ".copilot" / "session-state"
            if not state_dir.exists():
                continue
            for lock_file in state_dir.glob(f"*/inuse.{pid}.lock"):
                session_dir = lock_file.parent
                log_file = session_dir / "events.jsonl"
                if log_file.exists():
                    return str(log_file)

    try:
        cmd = ["lsof", "-p", ",".join(pids), "-Fn"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
        ranked_candidates: list[tuple[float, str]] = []
        seen_claim_keys: set[str] = set()
        for line in out.splitlines():
            if not line.startswith("n"):
                continue
            path = line[1:]
            if not re.search(log_pattern, path):
                continue
            stat_result: os.stat_result | None = None
            mtime = -1.0
            try:
                stat_result = os.stat(path)
                mtime = stat_result.st_mtime
            except OSError:
                pass
            claim_key = _native_path_claim_key(path, stat_result=stat_result)
            if claim_key in seen_claim_keys:
                continue
            seen_claim_keys.add(claim_key)
            ranked_candidates.append((mtime, path))
        if ranked_candidates:
            ranked_candidates.sort(key=lambda item: item[0], reverse=True)
            return ranked_candidates[0][1]
    except Exception:
        pass
    return None


def _parse_native_codex_log(filepath: str, limit: int) -> list[dict] | None:
    """Parse Codex rollout JSONL file."""
    try:
        tail_bytes = 65_536
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - tail_bytes)
            f.seek(start)
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        if start > 0 and lines:
            lines = lines[1:]

        events = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "response_item" and "payload" in data:
                payload = data["payload"]
                ptype = payload.get("type")

                if ptype == "reasoning":
                    summary = payload.get("summary") or []
                    for item in summary:
                        if not isinstance(item, dict):
                            continue
                        text = str(item.get("text") or "").strip()
                        if not text:
                            continue
                        events.append(
                            {
                                "kind": "fixed",
                                "text": f"✦ {text}",
                                "source_id": f"thought:codex:✦ {text}",
                            }
                        )
                elif ptype == "custom_tool_call":
                    name = payload.get("name", "")
                    inp = payload.get("input", "")
                    events.extend(_runtime_tool_events(name, inp))
                elif ptype == "function_call":
                    name = payload.get("name", "")
                    args = payload.get("arguments", "")
                    events.extend(_runtime_tool_events(name, args))
            if data.get("type") == "event_msg" and "payload" in data:
                payload = data["payload"] or {}
                if payload.get("type") == "agent_reasoning":
                    text = str(payload.get("text") or "").strip()
                    if text:
                        events.append(
                            {
                                "kind": "fixed",
                                "text": f"✦ {text}",
                                "source_id": f"thought:codex:✦ {text}",
                            }
                        )
        return _pane_runtime_gemini_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native codex log {filepath}: {e}")
        return None


_RUNTIME_APPLY_PATCH_FILE_RE = re.compile(
    r"^\*\*\*\s+(Add|Update|Delete)\s+File:\s+(.+?)\s*$",
    re.MULTILINE,
)


def _runtime_tool_summary(arguments: object) -> str:
    args_obj: object = arguments
    if isinstance(arguments, str):
        text = arguments.strip()
        if not text:
            return ""
        if text.startswith("*** Begin Patch"):
            return ""
        try:
            parsed = json.loads(text)
        except Exception:
            return text[:80]
        if isinstance(parsed, dict):
            args_obj = parsed
        else:
            return text[:80]
    if not isinstance(args_obj, dict):
        return ""
    for key in ("cmd", "command", "path", "file_path", "query", "pattern", "description", "prompt"):
        value = args_obj.get(key)
        if value and isinstance(value, str):
            return value[:80]
    return ""


def _runtime_apply_patch_ops(arguments: object) -> list[tuple[str, str]]:
    args_obj: object = arguments
    if isinstance(arguments, str):
        text = arguments.strip()
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                args_obj = parsed
            else:
                args_obj = text
        else:
            args_obj = text
    patch_text = ""
    if isinstance(args_obj, dict):
        for key in ("patch", "input", "arguments"):
            value = args_obj.get(key)
            if isinstance(value, str) and "*** Begin Patch" in value:
                patch_text = value
                break
    elif isinstance(args_obj, str) and "*** Begin Patch" in args_obj:
        patch_text = args_obj
    if not patch_text:
        return []
    ops: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    action_map = {"Add": "Create", "Update": "Edit", "Delete": "Delete"}
    for action, raw_path in _RUNTIME_APPLY_PATCH_FILE_RE.findall(patch_text):
        path = str(raw_path or "").strip()
        if not path:
            continue
        verb = action_map.get(action, "Edit")
        item = (verb, path)
        if item in seen:
            continue
        seen.add(item)
        ops.append(item)
    return ops


def _runtime_tool_events(name: object, arguments: object) -> list[dict]:
    tool_name = str(name or "tool").strip() or "tool"
    if tool_name.lower() == "apply_patch":
        ops = _runtime_apply_patch_ops(arguments)
        if ops:
            events: list[dict] = []
            for verb, path in ops[:8]:
                events.append(
                    {
                        "kind": "fixed",
                        "text": f"{verb}({path})",
                        "source_id": f"tool:apply_patch:{verb.lower()}:{path[:80]}",
                    }
                )
            remaining = len(ops) - 8
            if remaining > 0:
                events.append(
                    {
                        "kind": "fixed",
                        "text": f"Edit(+{remaining} files)",
                        "source_id": f"tool:apply_patch:extra:{remaining}",
                    }
                )
            return events
    summary = _runtime_tool_summary(arguments)
    display = f"{tool_name}({summary})" if summary else tool_name
    return [
        {
            "kind": "fixed",
            "text": display,
            "source_id": f"tool:{tool_name}:{summary[:40]}",
        }
    ]


def _parse_cursor_jsonl_runtime(filepath: str, limit: int) -> list[dict] | None:
    """Extract recent tool_use events from a cursor-tracked JSONL for runtime display."""
    try:
        tail_bytes = 32_768
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - tail_bytes)
            f.seek(start)
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        if start > 0 and lines:
            lines = lines[1:]

        events: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") == "assistant":
                msg = entry.get("message")
                if not isinstance(msg, dict):
                    continue
                for c in (msg.get("content") or []):
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        name = c.get("name", "tool")
                        inp = c.get("input") or {}
                        events.extend(_runtime_tool_events(name, inp))

            if entry.get("type") == "tool.execution_start":
                data = entry.get("data") or {}
                name = data.get("toolName", "tool")
                args = data.get("arguments") or {}
                events.extend(_runtime_tool_events(name, args))
            if entry.get("type") == "assistant.message":
                data = entry.get("data") or {}
                for tr in (data.get("toolRequests") or []):
                    if not isinstance(tr, dict):
                        continue
                    name = tr.get("name", "tool")
                    args = tr.get("arguments") or {}
                    events.extend(_runtime_tool_events(name, args))

            if entry.get("role") == "assistant":
                msg = entry.get("message")
                if not isinstance(msg, dict):
                    continue
                for c in (msg.get("content") or []):
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        name = c.get("name", "tool")
                        inp = c.get("input") or {}
                        events.extend(_runtime_tool_events(name, inp))

        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse cursor JSONL runtime {filepath}: {e}")
        return None


def _parse_native_claude_log(filepath: str, limit: int) -> list[dict] | None:
    """Parse Claude telemetry JSON log."""
    try:
        events = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_data = data.get("event_data", {})
                event_name = event_data.get("event_name", "")

                if event_name == "tengu_tool_call":
                    meta_str = event_data.get("additional_metadata", "{}")
                    try:
                        meta = json.loads(meta_str)
                    except Exception:
                        meta = {}
                    tool_name = meta.get("tool_name", "tool")
                    tool_input = meta.get("tool_input", "")
                    events.append(
                        {
                            "kind": "fixed",
                            "text": f"Ran {tool_name} {tool_input}",
                            "source_id": f"tool:claude:Ran {tool_name} {tool_input}",
                        }
                    )

        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native claude log {filepath}: {e}")
        return None


def _pane_runtime_new_events(previous: list[dict], current: list[dict]) -> list[dict]:
    if not current:
        return []
    prev_ids = [str((item or {}).get("source_id") or "") for item in (previous or [])]
    cur_ids = [str((item or {}).get("source_id") or "") for item in current]
    max_overlap = min(len(prev_ids), len(cur_ids))
    for overlap in range(max_overlap, 0, -1):
        if prev_ids[-overlap:] == cur_ids[:overlap]:
            return current[overlap:]
    return [] if prev_ids == cur_ids else current
