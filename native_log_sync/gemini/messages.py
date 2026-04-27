from __future__ import annotations

import time

from multiagent_chat.chat.sync.cursor import _parse_iso_timestamp_epoch
from multiagent_chat.chat.thinking_kind import classify_gemini_message_kind


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
