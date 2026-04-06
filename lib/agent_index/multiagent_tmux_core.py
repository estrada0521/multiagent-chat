from __future__ import annotations

import subprocess


def tmux_prefix_args(tmux_socket: str) -> list[str]:
    socket = (tmux_socket or "").strip()
    if socket.startswith("/"):
        return ["tmux", "-S", socket]
    return ["tmux", "-L", socket]


def parse_pane_ids(panes_csv: str) -> list[str]:
    return [pane.strip() for pane in (panes_csv or "").split(",") if pane.strip()]


def retile_session_preserving_user_panes(*, session: str, user_panes_csv: str, tmux_socket: str) -> None:
    prefix = tmux_prefix_args(tmux_socket)
    subprocess.run(
        [*prefix, "select-layout", "-t", f"{session}:0", "tiled"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    for pane_id in parse_pane_ids(user_panes_csv):
        subprocess.run(
            [*prefix, "resize-pane", "-t", pane_id, "-y", "2"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
