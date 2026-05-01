from __future__ import annotations

from backend_core.agents.names import agent_base_name

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
