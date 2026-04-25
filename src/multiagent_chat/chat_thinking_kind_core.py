from __future__ import annotations

import re

_GEMINI_PLAN_PREFIX = re.compile(
    r"^\s*(?:✦\s*)?(?:i\s+will|i['’]ll|i\s+am\s+going\s+to|let\s+me)\b",
    re.IGNORECASE,
)
_MAX_PLAN_TEXT_LEN = 280


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


def classify_gemini_message_kind(
    texts: list[str],
    *,
    has_thought_part: bool = False,
) -> str | None:
    normalized = _normalized_nonempty_texts(texts)
    if not normalized:
        return None
    if has_thought_part:
        return "agent-thinking"

    joined = " ".join(normalized)
    if _has_gemini_plan_prefix(joined):
        return "agent-thinking"
    return None


def infer_entry_kind(sender: str, message: str, *, existing_kind: str = "") -> str | None:
    kind = str(existing_kind or "").strip()
    if kind:
        return kind
    sender_name = str(sender or "").strip().lower()
    if not sender_name or sender_name in {"user", "system"}:
        return None
    sender_base = re.sub(r"-\d+$", "", sender_name)
    if sender_base == "qwen":
        return None
    body = strip_sender_prefix(message)
    if sender_base == "gemini" and _has_gemini_plan_prefix(body):
        return "agent-thinking"
    if _is_planning_style_text(body):
        return "agent-thinking"
    return None


def entry_with_inferred_kind(entry: dict) -> dict:
    if not isinstance(entry, dict):
        return entry
    kind = infer_entry_kind(
        str(entry.get("sender") or ""),
        str(entry.get("message") or ""),
        existing_kind=str(entry.get("kind") or ""),
    )
    if not kind or str(entry.get("kind") or "").strip() == kind:
        return entry
    out = dict(entry)
    out["kind"] = kind
    return out


def should_omit_entry_from_chat(entry: dict) -> bool:
    if not isinstance(entry, dict):
        return False
    sender_name = str(entry.get("sender") or "").strip().lower()
    sender_base = re.sub(r"-\d+$", "", sender_name)
    kind = str(entry.get("kind") or "").strip().lower()
    # Explicitly omit all qwen agent-thinking entries
    if sender_base == "qwen" and kind == "agent-thinking":
        return True
    if sender_base == "gemini":
        if kind == "agent-thinking":
            return True
        body = strip_sender_prefix(str(entry.get("message") or ""))
        if _has_gemini_plan_prefix(body):
            return True
    return False
