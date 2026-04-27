from __future__ import annotations

import json
import logging
import re

from multiagent_chat.chat.runtime_format import _pane_runtime_gemini_with_occurrence_ids
from multiagent_chat.chat.thinking_kind import classify_gemini_message_kind, strip_sender_prefix

from native_log_sync.core.runtime_display import (
    runtime_display_path,
    runtime_event,
    runtime_named_tool_events,
    runtime_search_detail,
)
from native_log_sync.gemini import plan_rules
from native_log_sync.gemini.tools import QUIET_TOOLS, TOOL_MAP

_GEMINI_PLAN_PREFIX_RE = re.compile(
    r"^\s*(?:✦\s*)?(?:i\s+will|i['’]ll|i\s+am\s+going\s+to|let\s+me)\b\s*",
    re.IGNORECASE,
)
_GEMINI_PATHLIKE_RE = re.compile(r"(?:^|/)[\w.-]+\.[A-Za-z0-9]+(?:$|[/:#?])|/")


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
        return runtime_display_path(text, workspace=workspace)
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

    action = plan_rules.DEFAULT_LABEL
    for pattern, label in plan_rules.PATTERN_LABEL_RULES:
        if re.search(pattern, lower):
            action = label
            break

    backticks = [item.strip() for item in re.findall(r"`([^`]+)`", first_line) if item.strip()]
    path_tokens = [item for item in backticks if _gemini_is_pathlike_token(item)]
    non_path_tokens = [item for item in backticks if item not in path_tokens]
    if action == "Search" and len(backticks) >= 2:
        query = non_path_tokens[0] if non_path_tokens else backticks[0]
        target = path_tokens[0] if path_tokens else backticks[-1]
        detail = runtime_search_detail(query, target, workspace=workspace)
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

                events_from_tool = runtime_named_tool_events(
                    name, args, workspace=workspace, tool_map=TOOL_MAP, quiet_tools=QUIET_TOOLS
                )
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
