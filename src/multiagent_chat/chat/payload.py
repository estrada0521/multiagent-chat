from __future__ import annotations

import json
import re

_ATTACHED_PATH_PATTERN = re.compile(r"\[Attached:\s*([^\]]+)\]")
_ATTACHED_MARKER_PATTERN = re.compile(r"(?:\n)?\[Attached:\s*[^\]]+\]")


def attachment_paths(message: str) -> list[str]:
    text = str(message or "")
    return [match.strip() for match in _ATTACHED_PATH_PATTERN.findall(text)]


def summarize_light_entry(
    entry: dict,
    *,
    message_char_limit: int,
    code_threshold: int,
    attachment_preview_limit: int,
) -> dict:
    summary = dict(entry)
    message = str(summary.get("message") or "")
    attached = attachment_paths(message)
    if attached:
        summary["attached_paths"] = attached

    body_only = _ATTACHED_MARKER_PATTERN.sub("", message).strip()
    heavy_code = "```" in body_only and len(body_only) > code_threshold
    truncated = len(body_only) > message_char_limit
    if not truncated and not heavy_code:
        return summary

    preview = body_only[:message_char_limit].rstrip()
    notes = ["[Public preview truncated. Load full message.]"]
    if attached:
        preview_paths = attached[:attachment_preview_limit]
        notes.extend([f"[Attached: {path}]" for path in preview_paths])
        remaining = len(attached) - len(preview_paths)
        if remaining > 0:
            notes.append(f"(+{remaining} more attachments)")
    summary["message"] = (preview + ("\n\n" if preview else "") + "\n".join(notes)).strip()
    summary["deferred_body"] = True
    summary["message_length"] = len(message)
    return summary


def build_payload_document(
    *,
    meta: dict,
    filter_agent: str | None,
    follow_mode: bool,
    targets: list[str],
    has_older: bool,
    light_mode: bool,
    entries: list[dict],
) -> dict:
    return {
        **meta,
        "filter": (filter_agent or "all"),
        "follow": bool(follow_mode),
        "targets": list(targets or []),
        "has_older": bool(has_older),
        "light_mode": bool(light_mode),
        "entries": list(entries or []),
    }


def encode_payload_document(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=True).encode("utf-8")
