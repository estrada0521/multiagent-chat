from __future__ import annotations

import re

from .names import agent_base_name
from .registry import AGENTS

_PROMPT_READY_BASES = {"claude", "codex", "gemini", "qwen", "cursor"}
_INLINE_FROM_PREFIX_BASES = {"qwen"}


def normalize_sender_payload(sender: str, payload: str) -> str:
    sender_label = "User" if sender == "user" else sender
    rest = str(payload or "")
    if rest.startswith("[From:"):
        idx = rest.find("]")
        if idx != -1:
            rest = rest[idx + 1 :]
            if rest.startswith(" "):
                rest = rest[1:]
    if not rest:
        return f"[From: {sender_label}]\n"
    if rest.startswith("\n"):
        rest = rest[1:]
    return f"[From: {sender_label}]\n{rest}\n"


def pane_delivery_payload(agent_name: str, payload: str) -> str:
    base = agent_base_name(agent_name)
    text = str(payload or "")
    if base not in _INLINE_FROM_PREFIX_BASES:
        return text
    header, sep, body = text.partition("\n")
    if not sep:
        return text.rstrip("\n")
    body = body.rstrip("\n")
    if not body:
        return header
    _sep = " \\\\n "
    return f"{header} {_sep.join(body.splitlines())}"


def pane_prompt_ready_from_text(agent_name: str, pane_text: str) -> bool:
    base = agent_base_name(agent_name)
    if base not in _PROMPT_READY_BASES:
        return True
    lines = [
        normalized
        for normalized in (
            (line or "").replace("\u00a0", " ").strip()
            for line in str(pane_text or "").splitlines()
        )
        if normalized
    ]
    tail = lines[-20:]
    if base == "claude":
        return any(line == "❯" for line in tail)
    if base == "codex":
        return any(line.startswith("›") for line in tail)
    if base == "cursor":
        return any("/ commands" in line and "@ files" in line for line in tail)
    pattern = (AGENTS.get(base).ready_pattern if base in AGENTS else "") or ""
    if not pattern or not tail:
        return False
    return re.search(pattern, "\n".join(tail), flags=re.MULTILINE) is not None
