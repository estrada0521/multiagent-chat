from __future__ import annotations


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
    del agent_name
    return str(payload or "")
