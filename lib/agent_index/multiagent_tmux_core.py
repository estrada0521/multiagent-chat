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


def window_target_for_pane(*, pane_id: str, tmux_socket: str) -> str:
    pane = (pane_id or "").strip()
    if not pane:
        return ""
    prefix = tmux_prefix_args(tmux_socket)
    res = subprocess.run(
        [*prefix, "display-message", "-p", "-t", pane, "#{window_id}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return ""
    return (res.stdout or "").strip()


def configure_window_size(*, target: str, width: int, height: int, tmux_socket: str) -> None:
    target_name = (target or "").strip()
    if not target_name:
        return
    prefix = tmux_prefix_args(tmux_socket)
    subprocess.run(
        [*prefix, "set-window-option", "-t", target_name, "window-size", "manual"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(
        [*prefix, "resize-window", "-t", target_name, "-x", str(width), "-y", str(height)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def create_agent_window(
    *,
    session: str,
    instance_name: str,
    workspace: str,
    width: int,
    height: int,
    tmux_socket: str,
) -> str:
    prefix = tmux_prefix_args(tmux_socket)
    res = subprocess.run(
        [
            *prefix,
            "new-window",
            "-d",
            "-P",
            "-F",
            "#{pane_id}",
            "-t",
            f"{session}:",
            "-n",
            instance_name,
            "-c",
            workspace,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return ""
    pane_id = (res.stdout or "").strip()
    if not pane_id:
        return ""
    window_target = window_target_for_pane(pane_id=pane_id, tmux_socket=tmux_socket)
    configure_window_size(
        target=window_target or pane_id,
        width=width,
        height=height,
        tmux_socket=tmux_socket,
    )
    return pane_id


def split_agent_pane(*, target_pane: str, workspace: str, tmux_socket: str) -> str:
    prefix = tmux_prefix_args(tmux_socket)
    res = subprocess.run(
        [*prefix, "split-window", "-h", "-P", "-F", "#{pane_id}", "-t", target_pane, "-c", workspace],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return ""
    return (res.stdout or "").strip()


def configure_agent_pane_defaults(*, pane_id: str, tmux_socket: str) -> None:
    pane = (pane_id or "").strip()
    if not pane:
        return
    prefix = tmux_prefix_args(tmux_socket)
    subprocess.run(
        [*prefix, "set-option", "-pt", pane, "remain-on-exit", "on"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(
        [*prefix, "set-option", "-pt", pane, "mouse", "on"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def kill_window_target(*, window_target: str, tmux_socket: str) -> bool:
    target = (window_target or "").strip()
    if not target:
        return False
    prefix = tmux_prefix_args(tmux_socket)
    res = subprocess.run(
        [*prefix, "kill-window", "-t", target],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return res.returncode == 0


def kill_pane_target(*, pane_id: str, tmux_socket: str) -> bool:
    pane = (pane_id or "").strip()
    if not pane:
        return False
    prefix = tmux_prefix_args(tmux_socket)
    res = subprocess.run(
        [*prefix, "kill-pane", "-t", pane],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return res.returncode == 0
