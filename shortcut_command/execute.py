from __future__ import annotations

from typing import Any

from shortcut_command.catalog import command_by_id
from shortcut_command.control import try_deliver_shortcut_control


def run_shortcut_command(
    rt: Any,
    *,
    command_id: str,
    arg: str,
    target: str,
) -> tuple[int, dict[str, Any]]:
    spec = command_by_id(command_id)
    if spec is None:
        msg = "unknown shortcut command"
        return 400, {"ok": False, "error": msg, "status_message": msg}
    resolved = (target or "").strip()
    if resolved:
        resolved = ",".join(rt.resolve_target_agents(resolved))

    if not resolved:
        msg = "target is required"
        return 400, {"ok": False, "error": msg, "status_message": msg}

    wire = _wire_payload(spec.id, arg)
    out = try_deliver_shortcut_control(rt, resolved, wire)
    if out is None:
        msg = "shortcut dispatch failed"
        return 500, {"ok": False, "error": msg, "status_message": msg}
    return out


def _wire_payload(command_id: str, arg: str) -> str:
    if command_id == "model":
        return "model"
    if command_id == "up":
        n = _parse_repeat(arg, default=1)
        return f"up {n}"
    if command_id == "down":
        n = _parse_repeat(arg, default=1)
        return f"down {n}"
    return command_id


def _parse_repeat(arg: str, *, default: int) -> int:
    raw = (arg or "").strip() or str(default)
    try:
        n = int(raw, 10)
    except ValueError:
        n = default
    return max(1, min(n, 100))
