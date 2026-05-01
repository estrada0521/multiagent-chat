from __future__ import annotations

import shlex
from pathlib import Path

from backend_core.agents.ensure_clis import resolve_agent_executable as resolve_known_agent_executable
from backend_core.agents.registry import AGENTS
from native_log_sync.agents._shared.path_state import _agent_base_name


def _repo_root(repo_root: Path | str | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root).resolve()
    return Path(__file__).resolve().parents[2]


def agent_launch_readiness(workspace: Path | str, agent_name: str) -> dict[str, str]:
    base = _agent_base_name(agent_name)
    executable = resolve_agent_executable(base, repo_root=workspace)
    if not executable:
        adef = AGENTS.get(base)
        disp = adef.display_name if adef else base
        return {"agent": base, "status": "missing_cli", "error": f"{disp} CLI is not installed on this Mac."}
    return {"agent": base, "status": "ok", "executable": executable}


def expected_instance_names(base_agents: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for agent in base_agents:
        counts[agent] = counts.get(agent, 0) + 1
    indices: dict[str, int] = {}
    resolved = []
    for agent in base_agents:
        if counts.get(agent, 0) > 1:
            indices[agent] = indices.get(agent, 0) + 1
            resolved.append(f"{agent}-{indices[agent]}")
        else:
            resolved.append(agent)
    return resolved


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
