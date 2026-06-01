from __future__ import annotations

import re

_GEMINI_PLAN_PREFIX = re.compile(
    r"^\s*(?:✦\s*)?(?:i\s+will|i['’]ll|i\s+am\s+going\s+to|let\s+me)\b",
    re.IGNORECASE,
)
_MAX_PLAN_TEXT_LEN = 280
_LEGACY_EPHEMERAL_KIND = "agent-thinking"


def _normalized_nonempty_texts(texts: list[str]) -> list[str]:
    return [str(text or "").strip() for text in texts if str(text or "").strip()]


def _is_planning_style_text(text: str) -> bool:
    body = str(text or "").strip()
    if not body or len(body) > _MAX_PLAN_TEXT_LEN:
        return False
    first_line = body.splitlines()[0].strip()
    if not first_line:
        return False
    return bool(_GEMINI_PLAN_PREFIX.match(first_line))


def _has_gemini_plan_prefix(text: str) -> bool:
    body = str(text or "").strip()
    if not body:
        return False
    first_line = body.splitlines()[0].strip()
    if not first_line:
        return False
    return bool(_GEMINI_PLAN_PREFIX.match(first_line))


def strip_sender_prefix(message: str) -> str:
    text = str(message or "").replace("\r\n", "\n").strip()
    if text.startswith("[From:"):
        close = text.find("]")
        if close != -1:
            text = text[close + 1 :].lstrip()
    return text


def is_ephemeral_thought_content(texts: list[str], *, has_thought_part: bool = False) -> bool:
    if has_thought_part:
        return True
    normalized = _normalized_nonempty_texts(texts)
    if not normalized:
        return False
    return _has_gemini_plan_prefix(" ".join(normalized))


def should_omit_entry_from_chat(entry: dict) -> bool:
    if not isinstance(entry, dict):
        return False
    sender_name = str(entry.get("sender") or "").strip().lower()
    if not sender_name or sender_name in {"user", "system"}:
        return False
    sender_base = re.sub(r"-\d+$", "", sender_name)
    kind = str(entry.get("kind") or "").strip().lower()
    if kind == _LEGACY_EPHEMERAL_KIND:
        return True
    body = strip_sender_prefix(str(entry.get("message") or ""))
    if sender_base == "gemini" and _has_gemini_plan_prefix(body):
        return True
    if sender_base != "qwen" and _is_planning_style_text(body):
        return True
    return False
