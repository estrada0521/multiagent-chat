"""Gemini CLI: JSONL のランタイム表示・thought 整形・チャット index 同期。"""

from __future__ import annotations

import json
import logging
import os
import re
import time

from multiagent_chat.chat.runtime_format import _pane_runtime_gemini_with_occurrence_ids
from multiagent_chat.chat.sync.cursor import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
)
from multiagent_chat.chat.thinking_kind import classify_gemini_message_kind, strip_sender_prefix
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.core.runtime_display import runtime_event
from native_log_sync.core.runtime_paths import display_path

MAIN_LABEL: dict[str, str] = {
    "read_file": "Read",
    "write_file": "Write",
    "replace": "Edit",
    "list_directory": "Explore",
    "grep_search": "Search",
    "run_shell_command": "Shell",
    "list_background_processes": "Processes",
}

PATTERN_LABEL_RULES: list[tuple[str, str]] = [
    (
        r"\b(image|screenshot|photo|picture|attached)\b.{0,80}\b(view|look|inspect|examine|check|read)\b",
        "Read",
    ),
    (
        r"\b(view|look|inspect|examine|check|read)\b.{0,80}\b(image|screenshot|photo|picture|attached)\b",
        "Read",
    ),
    (r"\b(search|find|locate|look\s+for|grep|rg)\b", "Search"),
    (r"\b(commit|committing)\b", "Run"),
    (r"\b(test|verify|validate|check\s+whether)\b", "Run"),
    (r"\b(run|execute|restart|launch|start)\b", "Run"),
    (
        r"\b(update|modify|change|adjust|refine|fix|align|add|remove|replace|ensure|include|clean|simplify|deduplicate)\b",
        "Edit",
    ),
    (r"\b(write|create|scaffold|generate|add\s+a\s+new)\b", "Write"),
    (r"\b(read|open|inspect|examine|review|check|look\s+at|analy[sz]e)\b", "Read"),
]
DEFAULT_PLAN_LABEL: str = "Thinking"


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


def _pick(d: object, *keys: str) -> str:
    if not isinstance(d, dict):
        return ""
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _gemini_subline(tool_lower: str, args: object, *, workspace: str) -> str:
    ws = str(workspace or "")

    if tool_lower == "list_background_processes":
        return "list"

    if not isinstance(args, dict):
        return ""

    if tool_lower == "read_file":
        return display_path(_pick(args, "file_path", "path"), workspace=ws)

    if tool_lower == "write_file":
        return display_path(_pick(args, "file_path", "path"), workspace=ws)

    if tool_lower == "replace":
        return display_path(_pick(args, "file_path", "path"), workspace=ws)

    if tool_lower == "list_directory":
        return display_path(_pick(args, "dir_path", "path"), workspace=ws)

    if tool_lower == "grep_search":
        pat = _pick(args, "pattern", "q", "query")
        tgt_raw = _pick(args, "path", "dir_path")
        tgt = display_path(tgt_raw, workspace=ws) if tgt_raw else ""
        return f"{pat} in {tgt}" if pat and tgt else (pat or tgt)

    if tool_lower == "run_shell_command":
        cmd = str(args.get("command") or args.get("cmd") or "").strip()
        if not cmd:
            return ""
        line = cmd.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    return ""


def _sid(p: str, t: str) -> str:
    return f"{p}:{(t or '')[:120]}"


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    lower = str(name or "").strip().lower()
    main = MAIN_LABEL.get(lower)
    if main is None:
        return []
    a = _coerce_args(arguments)
    sub = _gemini_subline(lower, a, workspace=str(workspace or "")).strip()
    if not sub:
        return []
    return [runtime_event(main, sub, source_id=_sid(f"tool:{lower}", sub))]


from multiagent_chat.chat.sync.cursor import _parse_iso_timestamp_epoch


def extract_gemini_message(entry: dict, min_event_ts: float | None = None) -> dict | None:
    """Gemini native log 1行から表示用メッセージ辞書を取り出す。"""
    if entry.get("type") != "gemini":
        return None
    if min_event_ts is not None:
        event_ts = _parse_iso_timestamp_epoch(str(entry.get("timestamp") or ""))
        if event_ts is None or event_ts < min_event_ts:
            return None
    msg_id = str(entry.get("id") or "")[:12]
    if not msg_id:
        return None

    content = entry.get("content", [])
    texts = []
    has_thought_part = False
    if isinstance(content, str):
        if content.strip():
            texts.append(content)
    elif isinstance(content, list):
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("thought") is True:
                has_thought_part = True
            text_raw = c.get("text")
            if text_raw:
                text = str(text_raw).strip()
                if text:
                    texts.append(text)

    if not texts:
        return None

    kind = classify_gemini_message_kind(texts, has_thought_part=has_thought_part)
    if kind == "agent-thinking":
        return {
            "msg_id": msg_id,
            "display_text": "",
            "is_thought": True,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    display = "\n".join(texts)
    return {
        "msg_id": msg_id,
        "display_text": display,
        "is_thought": False,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

_GEMINI_PLAN_PREFIX_RE = re.compile(
    r"^\s*(?:✦\s*)?(?:i\s+will|i['’]ll|i\s+am\s+going\s+to|let\s+me)\b\s*",
    re.IGNORECASE,
)
_GEMINI_PATHLIKE_RE = re.compile(r"(?:^|/)[\w.-]+\.[A-Za-z0-9]+(?:$|[/:#?])|/")


def _gemini_path_token(text: str, *, workspace: str = "") -> str:
    """thought 用: パスっぽいトークンはそのまま短く見せる（workspace 相対は Gemini 専用の単純ルール）。"""
    del workspace
    return str(text or "").strip()


def _gemini_query_in_target(query: str, target: str, *, workspace: str = "") -> str:
    del workspace
    q = str(query or "").strip()
    t = str(target or "").strip()
    if q and t:
        return f"{q} in {t}"
    return q or t


def _gemini_message_texts_and_thought(message: dict) -> tuple[list[str], bool]:
    content = message.get("content", []) if isinstance(message, dict) else []
    texts: list[str] = []
    has_thought_part = False
    if isinstance(content, str):
        text = content.strip()
        if text:
            texts.append(text)
    elif isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("thought") is True:
                has_thought_part = True
            text = str(part.get("text") or "").strip()
            if text:
                texts.append(text)
    return texts, has_thought_part


def _gemini_is_pathlike_token(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text.startswith(("/", "./", "../", "~")):
        return True
    if _GEMINI_PATHLIKE_RE.search(text):
        return True
    return bool(re.search(r"\.[A-Za-z0-9]{1,8}(?:$|[#:?])", text))


def _gemini_runtime_token(value: str, *, workspace: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if _gemini_is_pathlike_token(text):
        return _gemini_path_token(text, workspace=workspace)
    return text


def _gemini_clean_plan_text(text: str) -> str:
    body = strip_sender_prefix(str(text or "")).strip()
    if not body:
        return ""
    first_line = body.splitlines()[0].strip()
    first_line = _GEMINI_PLAN_PREFIX_RE.sub("", first_line, count=1).strip()
    first_line = re.sub(r"^(?:to|and|then)\s+", "", first_line, flags=re.IGNORECASE).strip()
    return first_line


def _gemini_runtime_action_detail(text: str, *, workspace: str = "") -> tuple[str, str]:
    body = strip_sender_prefix(str(text or "")).strip()
    first_line = body.splitlines()[0].strip() if body else ""
    lower = first_line.lower()

    action = DEFAULT_PLAN_LABEL
    for pattern, label in PATTERN_LABEL_RULES:
        if re.search(pattern, lower):
            action = label
            break

    backticks = [item.strip() for item in re.findall(r"`([^`]+)`", first_line) if item.strip()]
    path_tokens = [item for item in backticks if _gemini_is_pathlike_token(item)]
    non_path_tokens = [item for item in backticks if item not in path_tokens]
    if action == "Search" and len(backticks) >= 2:
        query = non_path_tokens[0] if non_path_tokens else backticks[0]
        target = path_tokens[0] if path_tokens else backticks[-1]
        detail = _gemini_query_in_target(query, target, workspace=workspace)
    elif action in {"Read", "Edit", "Write"} and path_tokens:
        detail = _gemini_runtime_token(path_tokens[0], workspace=workspace)
    elif backticks:
        detail = " ".join(_gemini_runtime_token(item, workspace=workspace) for item in backticks[:2]).strip()
    elif action == "Read" and re.search(
        r"\b(attached|this)\s+(?:image|screenshot|photo|picture)\b", lower
    ):
        detail = "attached image"
    else:
        detail = _gemini_clean_plan_text(first_line)
        detail = re.sub(
            r"^(?:search(?:\s+for)?|find|locate|read|open|inspect|examine|review|check|update|modify|change|adjust|refine|fix|run|execute|test|verify|validate|write|create)\s+",
            "",
            detail,
            flags=re.IGNORECASE,
        ).strip()
    detail = re.sub(r"\s+", " ", detail).strip(" .")
    if len(detail) > 120:
        detail = f"{detail[:117].rstrip()}..."
    return action, detail


def parse_native_gemini_log(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    """Gemini セッション JSONL をランタイム表示用に読む。"""
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
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict) or message.get("type") != "gemini":
                continue

            msg_id = str(message.get("id") or "").strip()[:12] or str(len(events))

            tool_calls = message.get("toolCalls")
            if isinstance(tool_calls, list) and tool_calls:
                last_tool = tool_calls[-1]
                name = str(last_tool.get("name") or "")
                args = last_tool.get("args") or {}

                events_from_tool = runtime_tool_events(name, args, workspace=workspace)
                if events_from_tool:
                    for ev in events_from_tool:
                        ev["source_id"] = f"gemini:{msg_id}:tool:{name}:{ev.get('text')}"
                        events.append(ev)
                    continue

            thoughts = message.get("thoughts")
            if isinstance(thoughts, list) and thoughts:
                last_thought = thoughts[-1]
                subject = str(last_thought.get("subject") or "").strip()
                if subject:
                    action = "Thinking"
                    detail = subject
                    refined_action, refined_detail = _gemini_runtime_action_detail(subject, workspace=workspace)
                    if refined_action != "Thinking":
                        action, detail = refined_action, refined_detail

                    events.append(
                        runtime_event(action, detail, source_id=f"gemini:{msg_id}:thought:{subject[:80]}")
                    )
                    continue

            texts, has_thought_part = _gemini_message_texts_and_thought(message)
            if not texts:
                continue
            kind = classify_gemini_message_kind(texts, has_thought_part=has_thought_part)
            first_text = texts[0]
            if kind != "agent-thinking" and not _GEMINI_PLAN_PREFIX_RE.match(strip_sender_prefix(first_text)):
                continue

            action, detail = _gemini_runtime_action_detail(first_text, workspace=workspace)
            source_detail = f"{action}:{detail[:80]}"
            events.append(runtime_event(action, detail, source_id=f"gemini:{msg_id}:{source_detail}"))

        return _pane_runtime_gemini_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error("Failed to parse native gemini log %s: %s", filepath, e)
        return None

def sync_gemini_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    first_seen_grace_seconds: float,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _FIRST_SEEN_GRACE_SECONDS = float(first_seen_grace_seconds)
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    prev_cursor = self._gemini_cursors.get(agent)
    try:
        workspace_text = str(self.workspace or "").strip()
        if not workspace_text:
            return

        workspace_aliases = self._workspace_aliases(workspace_text)
        
        session_path_str = resolve_gemini_native_log(
            agent=agent,
            workspace_aliases=workspace_aliases,
            native_log_path=native_log_path,
            gemini_cursors=self._gemini_cursors,
            should_stick_to_existing_cursor=self._should_stick_to_existing_cursor(agent),
            first_seen_ts=self._first_seen_for_agent(agent),
            first_seen_grace_seconds=_FIRST_SEEN_GRACE_SECONDS,
            global_claimed_paths=set(self._collect_global_native_log_claims().keys()),
        )
        
        if not session_path_str:
            return

        file_size = os.path.getsize(session_path_str)
        offset = _advance_native_cursor(self._gemini_cursors, agent, session_path_str, file_size)

        def _append_gemini_entry(entry: dict, *, min_event_ts: float | None = None) -> bool:
            extracted = extract_gemini_message(entry, min_event_ts=min_event_ts)
            if not extracted:
                return False
            
            msg_id = extracted["msg_id"]
            if msg_id in self._synced_msg_ids:
                return False
                
            self._synced_msg_ids.add(msg_id)
            
            if extracted["is_thought"]:
                return False

            jsonl_entry = {
                "timestamp": extracted["timestamp"],
                "session": self.session_name,
                "sender": agent,
                "targets": ["user"],
                "message": f"[From: {agent}]\n{extracted['display_text']}",
                "msg_id": msg_id,
            }
            append_jsonl_entry(self.index_path, jsonl_entry)
            return True

        def _scan_recent_gemini_entries(min_event_ts: float) -> bool:
            appended = False
            try:
                with open(session_path_str, "r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if _append_gemini_entry(entry, min_event_ts=min_event_ts):
                            appended = True
            except Exception:
                return False
            return appended

        if offset is None:
            appended_on_bind = False
            binding_changed = _cursor_binding_changed(prev_cursor, self._gemini_cursors.get(agent))
            if binding_changed:
                min_event_ts = time.time() - _SYNC_BIND_BACKFILL_WINDOW_SECONDS
                appended_on_bind = _scan_recent_gemini_entries(min_event_ts)
            if appended_on_bind or binding_changed:
                self.save_sync_state()
            return

        _assistant_appended = False
        with open(session_path_str, "r", encoding="utf-8") as f:
            f.seek(offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _append_gemini_entry(entry):
                    _assistant_appended = True

        self._gemini_cursors[agent] = NativeLogCursor(path=session_path_str, offset=file_size)
        self.save_sync_state()
        if _assistant_appended:
            self._agent_last_turn_done_ts[agent] = time.time()
            ev = self._agent_turn_done_events.get(agent)
            if ev is not None:
                ev.set()
    except Exception as exc:
        if prev_cursor is None:
            self._gemini_cursors.pop(agent, None)
        else:
            self._gemini_cursors[agent] = prev_cursor
        logging.error(f"Failed to sync Gemini message for {agent}: {exc}", exc_info=True)