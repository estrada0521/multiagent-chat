from __future__ import annotations

import logging
import subprocess
from typing import Any, Protocol

from native_log_sync.agents._shared.path_state import _agent_base_name

from shortcut_command.catalog import PANE_SINGLE_CONTROL_MESSAGES
from shortcut_command.parsing import parse_pane_direct_command


class ShortcutControlRuntime(Protocol):
    tmux_prefix: list[str]
    _agent_running: set[str]

    def restart_agent_pane(self, agent: str) -> tuple[bool, str]: ...

    def resume_agent_pane(self, agent: str) -> tuple[bool, str]: ...

    def pane_id_for_agent(self, agent: str) -> str | None: ...

    def append_system_entry(self, message: str, *, agent: str = "", **extra: Any) -> dict: ...


def try_deliver_shortcut_control(
    rt: ShortcutControlRuntime,
    target: str,
    message: str,
) -> tuple[int, dict] | None:
    pane_direct = parse_pane_direct_command(message)
    if message not in PANE_SINGLE_CONTROL_MESSAGES and not pane_direct:
        return None
    if not target:
        return 400, {"ok": False, "error": "target is required"}
    control_targets = [item.strip() for item in target.split(",") if item.strip()]
    try:
        for agent in control_targets:
            if message == "restart":
                ok, detail = rt.restart_agent_pane(agent)
                if not ok:
                    return 400, {"ok": False, "error": detail}
                continue
            if message == "resume":
                ok, detail = rt.resume_agent_pane(agent)
                if not ok:
                    return 400, {"ok": False, "error": detail}
                continue
            pane_id = rt.pane_id_for_agent(agent)
            if not pane_id:
                return 400, {"ok": False, "error": f"pane not found for {agent}"}
            if pane_direct:
                tmux_key = {"up": "Up", "down": "Down"}[pane_direct["name"]]
                for _ in range(pane_direct["repeat"]):
                    subprocess.run(
                        [*rt.tmux_prefix, "send-keys", "-t", pane_id, tmux_key],
                        capture_output=True,
                        check=False,
                    )
                continue
            tmux_key = {"interrupt": "Escape", "ctrlc": "C-c", "enter": "Enter"}[message]
            subprocess.run(
                [*rt.tmux_prefix, "send-keys", "-t", pane_id, tmux_key],
                capture_output=True,
                check=False,
            )
            if message in {"interrupt", "ctrlc"} and _agent_base_name(agent) == "cursor":
                rt._agent_running.discard(agent)
    except Exception as exc:
        logging.error("Unexpected error: %s", exc, exc_info=True)
        return 500, {"ok": False, "error": str(exc)}
    if message in {"restart", "resume"} and control_targets:
        action = "Restarted" if message == "restart" else "Resumed"
        rt.append_system_entry(
            f"{action}: {', '.join(control_targets)}",
            kind="agent-control",
            command=message,
            targets=control_targets,
        )
    mode = pane_direct["name"] if pane_direct else message
    return 200, {"ok": True, "mode": mode, "status_message": _status_completed(mode, control_targets)}


def _status_completed(mode: str, control_targets: list[str]) -> str:
    scope = ", ".join(control_targets) if control_targets else ""
    tail = f" ({scope})" if scope else ""
    return f"{mode} completed{tail}"
