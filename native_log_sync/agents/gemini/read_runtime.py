from __future__ import annotations

import json
import logging
import os
import re
import time

from multiagent_chat.chat.runtime_format import _pane_runtime_gemini_with_occurrence_ids
from native_log_sync.io.cursor_state import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
)
from multiagent_chat.chat.thinking_kind import classify_gemini_message_kind, strip_sender_prefix
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.agents._shared.runtime_display import runtime_event
from native_log_sync.agents._shared.runtime_paths import display_path

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


def extract_gemini_message(entry: dict, min_event_ts: float | None = None) -> dict | None:
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
