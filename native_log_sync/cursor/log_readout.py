"""Cursor: native JSONL の読み取り・ランタイム行・チャット index へのメッセージ同期。

どの JSON をツールとみなすか / 1行表示の形 / assistant 本文の取り出しはすべてここ。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path

from multiagent_chat.chat.sync.cursor import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _pick_latest_unclaimed_for_agent,
)
from multiagent_chat.jsonl_append import append_jsonl_entry
from multiagent_chat.redacted_placeholder import normalize_cursor_plaintext_for_index

from native_log_sync.core.jsonl_tail_runtime import parse_jsonl_tail_for_runtime
from native_log_sync.core.runtime_display import runtime_event
from native_log_sync.core.runtime_paths import display_path

_QUIET: frozenset[str] = frozenset({"todowrite"})


def parse_jsonl_for_runtime(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    return parse_jsonl_tail_for_runtime(
        filepath,
        limit,
        workspace,
        iter_tool_calls=iter_tool_calls,
        tool_events=runtime_tool_events,
        log_label="Cursor transcript JSONL",
    )


def iter_tool_calls(entry: dict) -> list[tuple[str, dict]]:
    if entry.get("role") != "assistant":
        return []
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return []
    out: list[tuple[str, dict]] = []
    for c in msg.get("content") or []:
        if not isinstance(c, dict):
            continue
        if c.get("type") != "tool_use":
            continue
        name = str(c.get("name") or "tool").strip()
        inp = c.get("input")
        if not isinstance(inp, dict):
            inp = c.get("arguments")
        if not isinstance(inp, dict):
            inp = {}
        out.append((name, inp))
    return out


def _source_id(prefix: str, tail: str) -> str:
    return f"{prefix}:{(tail or '')[:120]}"


def _coerce(arguments: object) -> object:
    if not isinstance(arguments, str):
        return arguments
    text = arguments.strip()
    if not text:
        return ""
    if not text.startswith("{"):
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _pick(d: object, *keys: str) -> str:
    if not isinstance(d, dict):
        return ""
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    raw = str(name or "").strip() or "tool"
    lower = raw.lower()
    if lower in _QUIET:
        return []
    ws = str(workspace or "")
    args_obj = _coerce(arguments)
    if not isinstance(args_obj, dict):
        return []

    if lower == "read":
        path = display_path(args_obj.get("path"), workspace=ws)
        bits: list[str] = []
        if "offset" in args_obj and args_obj.get("offset") is not None:
            bits.append(f"@{args_obj.get('offset')}")
        if "limit" in args_obj and args_obj.get("limit") is not None:
            bits.append(f"limit {args_obj.get('limit')}")
        suffix = f" ({', '.join(bits)})" if bits else ""
        sub = (path or "") + suffix
        if not sub.strip():
            return []
        return [runtime_event("Read", sub.strip(), source_id=_source_id("tool:read", sub))]

    if lower == "glob":
        pat = str(args_obj.get("glob_pattern") or "").strip()
        td = str(args_obj.get("target_directory") or "").strip()
        td_disp = display_path(td, workspace=ws) if td else ""
        if pat and td_disp:
            sub = f"{pat} in {td_disp}"
        elif pat:
            sub = pat
        else:
            sub = td_disp or "."
        return [runtime_event("Explore", sub, source_id=_source_id("tool:glob", sub))]

    if lower == "semanticsearch":
        q = str(args_obj.get("query") or "").strip()
        tds = args_obj.get("target_directories")
        extra = ""
        if isinstance(tds, list) and tds:
            t0 = str(tds[0] or "").strip()
            extra = display_path(t0, workspace=ws) if t0 else ""
        if q and extra:
            sub = f"{q} in {extra}"
        elif q:
            sub = q
        elif extra:
            sub = extra
        else:
            sub = "(semantic search)"
        return [runtime_event("Search", sub.strip(), source_id=_source_id("tool:semanticsearch", sub))]

    if lower == "readlints":
        paths_list = args_obj.get("paths")
        if isinstance(paths_list, list) and paths_list:
            parts = [display_path(p, workspace=ws) for p in paths_list[:3] if p]
            parts = [p for p in parts if p]
            if len(paths_list) > 3:
                sub = f"{', '.join(parts)} +{len(paths_list) - 3} more" if parts else f"{len(paths_list)} files"
            else:
                sub = ", ".join(parts) if parts else f"{len(paths_list)} files"
        else:
            sub = "lint"
        return [runtime_event("Lint", sub, source_id=_source_id("tool:readlints", sub))]

    if lower == "shell":
        cmd = str(args_obj.get("command") or args_obj.get("cmd") or "").strip()
        if not cmd:
            return []
        first = cmd.split("\n", 1)[0].strip()
        if len(first) > 120:
            first = first[:117] + "..."
        return [runtime_event("Shell", first, source_id=_source_id("tool:shell", first))]

    if lower == "grep":
        pat = _pick(args_obj, "pattern", "q", "query")
        raw_tgt = _pick(args_obj, "path", "dir_path")
        tgt = display_path(raw_tgt, workspace=ws) if raw_tgt else ""
        if pat and tgt:
            sub = f"{pat} in {tgt}"
        else:
            sub = pat or tgt
        if not sub:
            return []
        return [runtime_event("Search", sub, source_id=_source_id("tool:grep", sub))]

    if lower == "strreplace":
        path = display_path(_pick(args_obj, "path", "file_path"), workspace=ws)
        if not path:
            return []
        return [runtime_event("Edit", path, source_id=_source_id("tool:strreplace", path))]

    if lower == "write":
        path = display_path(_pick(args_obj, "path", "file_path"), workspace=ws)
        if not path:
            return []
        return [runtime_event("Write", path, source_id=_source_id("tool:write", path))]

    if lower == "delete":
        path = display_path(_pick(args_obj, "path", "file_path"), workspace=ws)
        if not path:
            return []
        return [runtime_event("Delete", path, source_id=_source_id("tool:delete", path))]

    if lower == "websearch":
        q = _pick(args_obj, "search_term", "query", "q")
        if not q:
            return []
        return [runtime_event("Search", q, source_id=_source_id("tool:websearch", q))]

    if lower == "webfetch":
        url = _pick(args_obj, "url", "uri")
        if not url:
            return []
        return [runtime_event("Fetch", url, source_id=_source_id("tool:webfetch", url))]

    return []


def _cursor_jsonl_assistant_turn_complete(entry: dict) -> bool:
    if entry.get("role") != "assistant":
        return False
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return False
    parts = [c for c in (msg.get("content") or []) if isinstance(c, dict)]
    if not parts:
        return False
    if any(c.get("type") == "tool_use" for c in parts):
        return False
    return True


def _cursor_assistant_line_has_tool_use(entry: dict) -> bool:
    if entry.get("role") != "assistant":
        return False
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return False
    for c in (msg.get("content") or []):
        if isinstance(c, dict) and c.get("type") == "tool_use":
            return True
    return False


def _cursor_assistant_text_chars(entry: dict) -> int:
    if entry.get("role") != "assistant":
        return 0
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return 0
    total = 0
    for c in (msg.get("content") or []):
        if isinstance(c, dict) and c.get("type") == "text":
            total += len(str(c.get("text") or ""))
    return total


def _cursor_turn_done_from_batch(batch: list[tuple[int, dict]]) -> bool:
    saw_tool_since_user = False
    turn_done = False
    for idx, (_ls, entry) in enumerate(batch):
        role = entry.get("role")
        if role == "user":
            saw_tool_since_user = False
            continue
        if role != "assistant":
            continue
        if _cursor_assistant_line_has_tool_use(entry):
            saw_tool_since_user = True
            continue
        if not _cursor_jsonl_assistant_turn_complete(entry):
            continue
        next_role = batch[idx + 1][1].get("role") if idx + 1 < len(batch) else None
        next_is_user = next_role == "user"
        if saw_tool_since_user or next_is_user:
            turn_done = True
            saw_tool_since_user = False
            continue
        if idx == len(batch) - 1 and _cursor_assistant_text_chars(entry) < 200:
            turn_done = True
    return turn_done


def sync_cursor_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    first_seen_grace_seconds: float,
) -> None:
    _FIRST_SEEN_GRACE_SECONDS = float(first_seen_grace_seconds)
    try:
        workspace = self.workspace or ""
        if not workspace:
            return
        transcript_path = str(Path(native_log_path)) if native_log_path else ""
        if not transcript_path:
            cursor = self._cursor_cursors.get(agent)
            if (
                cursor
                and cursor.path
                and os.path.exists(cursor.path)
                and self._should_stick_to_existing_cursor(agent)
            ):
                transcript_path = cursor.path
            else:
                candidates: list[Path] = []
                for root in self._cursor_transcript_roots(workspace):
                    candidates.extend(root.glob("*/*.jsonl"))
                if not candidates:
                    return
                min_mtime = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                picked = _pick_latest_unclaimed_for_agent(
                    candidates,
                    self._cursor_cursors,
                    agent,
                    min_mtime=min_mtime,
                    exclude_paths=set(self._collect_global_native_log_claims().keys()),
                )
                if picked is None:
                    return
                transcript_path = str(picked)
        elif self._is_globally_claimed_path(transcript_path):
            return
        if not os.path.exists(transcript_path):
            return
        file_size = os.path.getsize(transcript_path)
        prev_cursor = self._cursor_cursors.get(agent)
        offset = _advance_native_cursor(self._cursor_cursors, agent, transcript_path, file_size)
        if offset is None:
            if _cursor_binding_changed(prev_cursor, self._cursor_cursors.get(agent)):
                self.save_sync_state()
            return

        batch: list[tuple[int, dict]] = []
        with open(transcript_path, "r", encoding="utf-8") as f:
            f.seek(offset)
            while True:
                line_start = f.tell()
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                batch.append((line_start, entry))

        turn_done_seen = _cursor_turn_done_from_batch(batch)

        for line_start, entry in batch:
            display = ""
            role = entry.get("role", "")
            if role == "assistant":
                msg_obj = entry.get("message") if isinstance(entry, dict) else {}
                if not isinstance(msg_obj, dict):
                    continue
                content = msg_obj.get("content", [])
                if isinstance(content, str) and content.strip():
                    display = content.strip()
                elif isinstance(content, list):
                    texts = []
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text = str(c.get("text") or "").strip()
                            if text:
                                texts.append(text)
                    if not texts:
                        continue
                    display = "\n".join(texts)
            elif role == "system":
                msg_obj = entry.get("message") if isinstance(entry, dict) else {}
                if isinstance(msg_obj, dict):
                    content = msg_obj.get("content", "")
                    if isinstance(content, str) and content.strip():
                        display = content.strip()
                elif isinstance(msg_obj, str) and msg_obj.strip():
                    display = msg_obj.strip()

            if not display:
                continue

            display = normalize_cursor_plaintext_for_index(display)
            if not display:
                continue

            key = f"cursor:{agent}:{transcript_path}:{line_start}:{display}"
            msg_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
            if msg_id in self._synced_msg_ids:
                continue
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            jsonl_entry = {
                "timestamp": timestamp,
                "session": self.session_name,
                "sender": agent,
                "targets": ["user"],
                "message": f"[From: {agent}]\n{display}",
                "msg_id": msg_id,
            }
            append_jsonl_entry(self.index_path, jsonl_entry)
            self._synced_msg_ids.add(msg_id)

        if turn_done_seen:
            self._agent_last_turn_done_ts[agent] = time.time()
            ev = self._agent_turn_done_events.get(agent)
            if ev is not None:
                ev.set()

        self._cursor_cursors[agent] = NativeLogCursor(path=transcript_path, offset=file_size)
        self.save_sync_state()
    except Exception as exc:
        logging.error("Failed to sync Cursor message for %s: %s", agent, exc)
