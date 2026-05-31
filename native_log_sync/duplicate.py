from __future__ import annotations

import hashlib
import re


_MIN_FINGERPRINT_CHARS = 80


def message_content_fingerprint(sender: str, message: str) -> str | None:
    """Stable fingerprint for substantial agent messages.

    Some native logs can be rebound or rewritten with different native IDs.
    Use content-level dedup only for long or multiline messages so repeated
    short replies such as "pong" are still allowed.
    """
    body = str(message or "").strip()
    if not body:
        return None
    if len(body) < _MIN_FINGERPRINT_CHARS and "\n" not in body:
        return None
    normalized = re.sub(r"\s+", " ", body).strip()
    if len(normalized) < _MIN_FINGERPRINT_CHARS:
        return None
    key = f"{str(sender or '').strip()}\0{normalized}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def already_synced_message(runtime, sender: str, message: str, msg_id: str = "") -> bool:
    msg_id = str(msg_id or "").strip()
    if msg_id and msg_id in getattr(runtime, "_synced_msg_ids", set()):
        return True
    fingerprint = message_content_fingerprint(sender, message)
    return bool(
        fingerprint
        and fingerprint in getattr(runtime, "_synced_message_fingerprints", set())
    )


def mark_message_synced(runtime, sender: str, message: str, msg_id: str = "") -> None:
    msg_id = str(msg_id or "").strip()
    if msg_id:
        runtime._synced_msg_ids.add(msg_id)
    fingerprint = message_content_fingerprint(sender, message)
    if fingerprint:
        runtime._synced_message_fingerprints.add(fingerprint)
