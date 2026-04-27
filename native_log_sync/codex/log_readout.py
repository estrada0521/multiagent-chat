"""Codex: ロールアウト JSONL のランタイム表示とチャット index 同期。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path

from multiagent_chat.chat.sync.cursor import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
)
from multiagent_chat.chat.runtime_format import _pane_runtime_gemini_with_occurrence_ids
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.core.runtime_display import runtime_event
from native_log_sync.core.runtime_paths import display_path

QUIET: frozenset[str] = frozenset({"write_stdin"})
MAIN_LABEL: dict[str, str] = {
    "apply_patch": "Patch",
    "exec_command": "Shell",
    "view_image": "Read",
    "list_mcp_resources": "MCP",
    "spawn_agent": "Agent",
    "update_plan": "Plan",
    "send_input": "Input",
    "wait_agent": "Wait",
    "close_agent": "Close",
}


def _coerce_args(arguments: object) -> object:
    if not isinstance(arguments, str):
        return arguments
    t = arguments.strip()
    if not t or not t.startswith("{"):
        return t
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return t

_PATCH = re.compile(r"^\*\*\* Update File:\s*(.+)\s*$", re.MULTILINE)


def _patch_target_path(arg: object) -> str:
    text = arg if isinstance(arg, str) else ""
    if isinstance(arg, dict):
        for k in ("input", "patch", "content", "text"):
            v = arg.get(k)
            if isinstance(v, str) and v.strip():
                text = v
                break
    m = _PATCH.search(text)
    return m.group(1).strip() if m else "(patch)"


def _pick(d: object, *keys: str) -> str:
    if not isinstance(d, dict):
        return ""
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _codex_subline(tool_lower: str, args: object, *, workspace: str) -> str:
    ws = str(workspace or "")

    if tool_lower == "apply_patch":
        return _patch_target_path(args)

    if not isinstance(args, dict):
        return ""

    if tool_lower == "exec_command":
        cmd = str(args.get("cmd") or args.get("command") or "").strip()
        if not cmd:
            return ""
        line = cmd.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "view_image":
        return display_path(_pick(args, "path", "file_path"), workspace=ws)

    if tool_lower == "list_mcp_resources":
        srv = str(args.get("server") or "").strip() or "(server)"
        return f"list_resources · {srv}"

    if tool_lower == "spawn_agent":
        d = _pick(args, "message", "description", "prompt")
        if not d:
            d = str(args.get("agent_type") or "").strip() or "(spawn_agent)"
        line = d.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "update_plan":
        plan = args.get("plan")
        n = len(plan) if isinstance(plan, list) else 0
        return f"{n} steps" if n else "plan"

    if tool_lower == "send_input":
        msg = str(args.get("message") or "").strip()
        if not msg:
            return str(args.get("id") or "")
        line = msg.split("\n", 1)[0].strip()
        return line[:97] + "..." if len(line) > 100 else line

    if tool_lower == "wait_agent":
        targets = args.get("targets")
        if isinstance(targets, list) and targets:
            sub = ", ".join(str(t) for t in targets[:3])
            if len(targets) > 3:
                sub += f" +{len(targets) - 3}"
            return sub
        return "(wait)"

    if tool_lower == "close_agent":
        return str(args.get("target") or "").strip() or "(target)"

    return ""


def _sid(p: str, t: str) -> str:
    return f"{p}:{(t or '')[:120]}"


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    lower = str(name or "").strip().lower()
    if lower in QUIET:
        return []
    main = MAIN_LABEL.get(lower)
    if main is None:
        return []
    a = _coerce_args(arguments)
    sub = _codex_subline(lower, a, workspace=str(workspace or "")).strip()
    if not sub:
        return []
    return [runtime_event(main, sub, source_id=_sid(f"tool:{lower}", sub))]


def parse_native_codex_log(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    """Codex rollout JSONL をランタイム表示用イベントに変換する。"""
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
                    events.extend(runtime_tool_events(name, inp, workspace=workspace))
                elif ptype == "function_call":
                    name = payload.get("name", "")
                    args = payload.get("arguments", "")
                    events.extend(runtime_tool_events(name, args, workspace=workspace))
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
        logging.error("Failed to parse native codex log %s: %s", filepath, e)
        return None

def sync_codex_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    try:
        from native_log_sync.codex.log_location import resolve_codex_rollout_jsonl_path

        resolved_path = resolve_codex_rollout_jsonl_path(self, agent, native_log_path)
        if not resolved_path:
            return

        def _append_codex_entry(entry: dict, *, min_event_ts: float | None = None) -> bool:
            if min_event_ts is not None:
                event_ts = _parse_iso_timestamp_epoch(str(entry.get("timestamp") or ""))
                if event_ts is None or event_ts < min_event_ts:
                    return False

            display = ""
            kind = ""
            entry_type = entry.get("type", "")
            if entry_type == "response_item":
                payload = entry.get("payload", {})
                payload_type = str(payload.get("type") or "").strip().lower()
                if payload_type == "reasoning":
                    summary = payload.get("summary") or []
                    reasoning_lines = []
                    if isinstance(summary, list):
                        for item in summary:
                            if not isinstance(item, dict):
                                continue
                            text = str(item.get("text") or "").strip()
                            if text:
                                reasoning_lines.append(text)
                    if not reasoning_lines:
                        return False
                    display = "\n".join(reasoning_lines)
                    kind = "agent-thinking"
                else:
                    if payload.get("role") != "assistant":
                        return False
                    content = payload.get("content", [])
                    texts = []
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict):
                                t = c.get("text") or c.get("output_text", {}).get("text", "")
                                if t and str(t).strip():
                                    texts.append(str(t).strip())
                    if not texts:
                        return False
                    display = "\n".join(texts)
            elif entry_type == "event_msg":
                payload = entry.get("payload", {})
                payload_type = str(payload.get("type") or "").strip().lower()
                if payload_type == "error":
                    display = str(payload.get("message") or "").strip()
                elif payload_type == "agent_reasoning":
                    display = str(payload.get("text") or payload.get("message") or "").strip()
                    kind = "agent-thinking"
                else:
                    return False
                if not display:
                    return False
            else:
                return False

            src_ts = str(entry.get("timestamp") or "")
            key = f"codex:{agent}:{src_ts}:{display}"
            msg_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
            if msg_id in self._synced_msg_ids:
                return False

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            jsonl_entry = {
                "timestamp": timestamp,
                "session": self.session_name,
                "sender": agent,
                "targets": ["user"],
                "message": f"[From: {agent}]\n{display}",
                "msg_id": msg_id,
            }
            if kind:
                jsonl_entry["kind"] = kind
            append_jsonl_entry(self.index_path, jsonl_entry)
            self._synced_msg_ids.add(msg_id)
            return True

        def _scan_recent_codex_entries(min_event_ts: float) -> bool:
            appended = False
            try:
                with open(resolved_path, "r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if _append_codex_entry(entry, min_event_ts=min_event_ts):
                            appended = True
            except Exception:
                return False
            return appended

        file_size = os.path.getsize(resolved_path)
        prev_cursor = self._codex_cursors.get(agent)
        offset = _advance_native_cursor(self._codex_cursors, agent, resolved_path, file_size)
        if offset is None:
            appended_on_bind = False
            if _cursor_binding_changed(prev_cursor, self._codex_cursors.get(agent)):
                min_event_ts = time.time() - _SYNC_BIND_BACKFILL_WINDOW_SECONDS
                appended_on_bind = _scan_recent_codex_entries(min_event_ts)
            if appended_on_bind or _cursor_binding_changed(prev_cursor, self._codex_cursors.get(agent)):
                self.save_sync_state()
            return

        _assistant_text_appended = False
        _orig_append = _append_codex_entry

        def _append_codex_entry_tracked(entry: dict, *, min_event_ts: float | None = None) -> bool:
            nonlocal _assistant_text_appended
            result = _orig_append(entry, min_event_ts=min_event_ts)
            if result:
                entry_type = entry.get("type", "")
                if entry_type == "response_item":
                    payload = entry.get("payload", {})
                    if str(payload.get("type") or "").strip().lower() != "reasoning":
                        _assistant_text_appended = True
                elif entry_type == "event_msg":
                    payload = entry.get("payload", {})
                    if str(payload.get("type") or "").strip().lower() != "agent_reasoning":
                        _assistant_text_appended = True
            return result

        with open(resolved_path, "r", encoding="utf-8") as f:
            f.seek(offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                _append_codex_entry_tracked(entry)

        self._codex_cursors[agent] = NativeLogCursor(path=resolved_path, offset=file_size)
        self.save_sync_state()
        if _assistant_text_appended:
            self._agent_last_turn_done_ts[agent] = time.time()
            ev = self._agent_turn_done_events.get(agent)
            if ev is not None:
                ev.set()
    except Exception as exc:
        logging.error(f"Failed to sync Codex message for {agent}: {exc}")
