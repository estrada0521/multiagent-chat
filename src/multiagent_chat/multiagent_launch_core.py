from __future__ import annotations

import shlex


def _q(value: str) -> str:
    return shlex.quote(str(value))


def build_env_exports(
    *,
    script_dir: str,
    session_name: str,
    workspace: str,
    tmux_socket: str,
    index_path: str,
    agent_name: str | None = None,
    log_dir: str | None = None,
) -> str:
    assignments = [
        f"PATH={_q(script_dir)}:$PATH",
        f"MULTIAGENT_SESSION={_q(session_name)}",
        f"MULTIAGENT_BIN_DIR={_q(script_dir)}",
        f"MULTIAGENT_WORKSPACE={_q(workspace)}",
        f"MULTIAGENT_TMUX_SOCKET={_q(tmux_socket)}",
        f"MULTIAGENT_INDEX_PATH={_q(index_path)}",
    ]
    if agent_name is not None:
        assignments.append(f"MULTIAGENT_AGENT_NAME={_q(agent_name)}")
    if log_dir is None:
        assignments.append(f"MULTIAGENT_LOG_DIR={_q(f'{workspace}/logs')}")
    elif log_dir != "":
        assignments.append(f"MULTIAGENT_LOG_DIR={_q(log_dir)}")
    return "export " + " ".join(assignments)


def build_agent_launch_command(
    *,
    env_exports: str,
    executable: str,
    launch_extra: str = "",
    launch_flags: str = "",
    launch_env: str = "",
) -> str:
    cmd_parts = env_exports
    if launch_env:
        cmd_parts = f"{cmd_parts} {launch_env}"
    cmd_parts = f"{cmd_parts}; exec"
    if launch_extra:
        cmd_parts = f"{cmd_parts} {launch_extra}"
    cmd_parts = f"{cmd_parts} {executable}"
    if launch_flags:
        cmd_parts = f"{cmd_parts} {launch_flags}"
    return cmd_parts


def build_user_launch_command(*, env_exports: str, script_dir: str) -> str:
    return f"{env_exports}; exec {_q(f'{script_dir}/multiagent-user-shell')}"
