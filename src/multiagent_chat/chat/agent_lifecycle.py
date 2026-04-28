from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

from ..agents.registry import AGENTS


def agent_launch_cmd(self, agent_name: str) -> str:
    bin_dir = Path(self.agent_send_path).parent
    agent_exec_path = Path(resolve_agent_executable(agent_name))
    path_prefix = ":".join(
        [
            shlex.quote(str(bin_dir)),
            shlex.quote(str(agent_exec_path.parent)),
        ]
    )
    env_parts = [
        f"PATH={path_prefix}:$PATH",
        f"MULTIAGENT_SESSION={shlex.quote(self.session_name)}",
        f"MULTIAGENT_BIN_DIR={shlex.quote(str(bin_dir))}",
        f"MULTIAGENT_WORKSPACE={shlex.quote(self.workspace)}",
        f"MULTIAGENT_TMUX_SOCKET={shlex.quote(self.tmux_socket)}",
        f"MULTIAGENT_INDEX_PATH={shlex.quote(str(self.index_path))}",
        f"MULTIAGENT_AGENT_NAME={shlex.quote(agent_name)}",
    ]
    env_exports = "export " + " ".join(env_parts)
    agent_exec = shlex.quote(str(agent_exec_path))
    base = agent_name.split("-")[0] if "-" in agent_name else agent_name
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


def agent_resume_cmd(self, agent_name: str) -> str:
    bin_dir = Path(self.agent_send_path).parent
    agent_exec_path = Path(resolve_agent_executable(agent_name))
    path_prefix = ":".join(
        [
            shlex.quote(str(bin_dir)),
            shlex.quote(str(agent_exec_path.parent)),
        ]
    )
    env_parts = [
        f"PATH={path_prefix}:$PATH",
        f"MULTIAGENT_SESSION={shlex.quote(self.session_name)}",
        f"MULTIAGENT_BIN_DIR={shlex.quote(str(bin_dir))}",
        f"MULTIAGENT_WORKSPACE={shlex.quote(self.workspace)}",
        f"MULTIAGENT_TMUX_SOCKET={shlex.quote(self.tmux_socket)}",
        f"MULTIAGENT_INDEX_PATH={shlex.quote(str(self.index_path))}",
        f"MULTIAGENT_AGENT_NAME={shlex.quote(agent_name)}",
    ]
    env_exports = "export " + " ".join(env_parts)
    agent_exec = shlex.quote(str(agent_exec_path))
    base = agent_name.split("-")[0] if "-" in agent_name else agent_name
    adef = AGENTS.get(base)
    if not adef or not adef.resume_flag:
        return agent_launch_cmd(self, agent_name)
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


def resolve_agent_executable(agent_name: str) -> str:
    base = agent_name.split("-")[0] if "-" in agent_name else agent_name
    adef = AGENTS.get(base)
    exe_name = adef.exe if adef else agent_name
    found = shutil.which(exe_name)
    if found:
        return found
    if base == "cursor":
        found = shutil.which("cursor-agent")
        if found:
            return found
    if adef:
        for p in adef.fallback_paths:
            candidate = Path(p).expanduser()
            if candidate.is_file():
                return str(candidate)
    if adef and adef.fallback_nvm:
        nvm_bin = Path(os.environ.get("NVM_BIN", "")).expanduser()
        candidates: list[Path] = []
        if nvm_bin.is_dir():
            candidates.append(nvm_bin / exe_name)
        candidates.extend(
            sorted(
                (Path.home() / ".nvm" / "versions" / "node").glob(f"*/bin/{exe_name}"),
                reverse=True,
            )
        )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return exe_name


def restart_agent_pane(self, agent_name: str) -> tuple[bool, str]:
    pane_id = self.pane_id_for_agent(agent_name)
    if not pane_id:
        return False, f"pane not found for {agent_name}"
    shell = os.environ.get("SHELL") or "/bin/zsh"
    respawn_res = subprocess.run(
        [
            *self.tmux_prefix,
            "respawn-pane",
            "-k",
            "-t",
            pane_id,
            "-c",
            self.workspace,
            shell,
            "-lc",
            self.agent_launch_cmd(agent_name),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if respawn_res.returncode != 0:
        detail = (respawn_res.stderr or respawn_res.stdout or "").strip() or f"failed to restart {agent_name}"
        return False, detail
    self._pane_native_log_paths.pop(pane_id, None)
    try:
        self.refresh_native_log_bindings([agent_name], reason="restart")
    except Exception:
        pass
    subprocess.run([*self.tmux_prefix, "select-pane", "-t", pane_id, "-T", agent_name], capture_output=True, check=False)
    return True, pane_id


def resume_agent_pane(self, agent_name: str) -> tuple[bool, str]:
    pane_id = self.pane_id_for_agent(agent_name)
    if not pane_id:
        return False, f"pane not found for {agent_name}"
    shell = os.environ.get("SHELL") or "/bin/zsh"
    respawn_res = subprocess.run(
        [
            *self.tmux_prefix,
            "respawn-pane",
            "-k",
            "-t",
            pane_id,
            "-c",
            self.workspace,
            shell,
            "-lc",
            self.agent_resume_cmd(agent_name),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if respawn_res.returncode != 0:
        detail = (respawn_res.stderr or respawn_res.stdout or "").strip() or f"failed to resume {agent_name}"
        return False, detail
    self._pane_native_log_paths.pop(pane_id, None)
    try:
        self.refresh_native_log_bindings([agent_name], reason="resume")
    except Exception:
        pass
    subprocess.run([*self.tmux_prefix, "select-pane", "-t", pane_id, "-T", agent_name], capture_output=True, check=False)
    return True, pane_id
