from __future__ import annotations

import shlex
from pathlib import Path

from multiagent_chat.agents.ensure_clis import resolve_agent_executable as resolve_known_agent_executable
from multiagent_chat.agents.registry import AGENTS


def _repo_root(repo_root: Path | str | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root).resolve()
    return Path(__file__).resolve().parents[2]


def resolve_agent_executable(agent_name: str, *, repo_root: Path | str | None = None) -> str:
    resolved_root = _repo_root(repo_root)
    found = resolve_known_agent_executable(resolved_root, agent_name)
    if found:
        return found
    base = agent_name.split("-", 1)[0] if "-" in agent_name else agent_name
    adef = AGENTS.get(base)
    return adef.exe if adef else agent_name


def agent_launch_cmd(runtime, agent_name: str) -> str:
    bin_dir = Path(runtime.agent_send_path).parent
    agent_exec_path = Path(resolve_agent_executable(agent_name, repo_root=runtime.repo_root))
    path_prefix = ":".join(
        [
            shlex.quote(str(bin_dir)),
            shlex.quote(str(agent_exec_path.parent)),
        ]
    )
    env_parts = [
        f"PATH={path_prefix}:$PATH",
        f"MULTIAGENT_SESSION={shlex.quote(runtime.session_name)}",
        f"MULTIAGENT_BIN_DIR={shlex.quote(str(bin_dir))}",
        f"MULTIAGENT_WORKSPACE={shlex.quote(runtime.workspace)}",
        f"MULTIAGENT_TMUX_SOCKET={shlex.quote(runtime.tmux_socket)}",
        f"MULTIAGENT_INDEX_PATH={shlex.quote(str(runtime.index_path))}",
        f"MULTIAGENT_AGENT_NAME={shlex.quote(agent_name)}",
    ]
    env_exports = "export " + " ".join(env_parts)
    agent_exec = shlex.quote(str(agent_exec_path))
    base = agent_name.split("-", 1)[0] if "-" in agent_name else agent_name
    adef = AGENTS.get(base)
    parts = [env_exports]
    if adef and adef.launch_env:
        parts.append(f"export {adef.launch_env}")
    launch_extra = adef.launch_extra if adef else ""
    launch_flags = adef.launch_flags if adef else ""
    extra = f" {launch_extra}" if launch_extra else ""
    flags = f" {launch_flags}" if launch_flags else ""
    parts.append(f"exec{extra} {agent_exec}{flags}")
    return "; ".join(parts)


def agent_resume_cmd(runtime, agent_name: str) -> str:
    bin_dir = Path(runtime.agent_send_path).parent
    agent_exec_path = Path(resolve_agent_executable(agent_name, repo_root=runtime.repo_root))
    path_prefix = ":".join(
        [
            shlex.quote(str(bin_dir)),
            shlex.quote(str(agent_exec_path.parent)),
        ]
    )
    env_parts = [
        f"PATH={path_prefix}:$PATH",
        f"MULTIAGENT_SESSION={shlex.quote(runtime.session_name)}",
        f"MULTIAGENT_BIN_DIR={shlex.quote(str(bin_dir))}",
        f"MULTIAGENT_WORKSPACE={shlex.quote(runtime.workspace)}",
        f"MULTIAGENT_TMUX_SOCKET={shlex.quote(runtime.tmux_socket)}",
        f"MULTIAGENT_INDEX_PATH={shlex.quote(str(runtime.index_path))}",
        f"MULTIAGENT_AGENT_NAME={shlex.quote(agent_name)}",
    ]
    env_exports = "export " + " ".join(env_parts)
    agent_exec = shlex.quote(str(agent_exec_path))
    base = agent_name.split("-", 1)[0] if "-" in agent_name else agent_name
    adef = AGENTS.get(base)
    if not adef or not adef.resume_flag:
        return agent_launch_cmd(runtime, agent_name)
    parts = [env_exports]
    if adef.launch_env:
        parts.append(f"export {adef.launch_env}")
    launch_extra = adef.launch_extra if adef.launch_extra else ""
    resume_extra = adef.resume_extra_flags if adef.resume_extra_flags else ""
    extra = f" {launch_extra}" if launch_extra else ""
    flags = f" {adef.resume_flag}"
    if resume_extra:
        flags += f" {resume_extra}"
    parts.append(f"exec{extra} {agent_exec}{flags}")
    return "; ".join(parts)
