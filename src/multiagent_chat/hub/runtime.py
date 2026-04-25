from __future__ import annotations
import logging

import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .chat_supervisor import (
    chat_launch_env as _chat_launch_env_impl,
    chat_launch_session_dir as _chat_launch_session_dir_impl,
    chat_launch_workspace as _chat_launch_workspace_impl,
    chat_ready as _chat_ready_impl,
    chat_server_matches as _chat_server_matches_impl,
    chat_server_state as _chat_server_state_impl,
    delete_archived_session as _delete_archived_session_impl,
    ensure_chat_server as _ensure_chat_server_impl,
    kill_repo_session as _kill_repo_session_impl,
    revive_archived_session as _revive_archived_session_impl,
    stop_chat_server as _stop_chat_server_impl,
)
from .session_query import (
    archived_sessions as _archived_sessions_impl,
    build_session_record as _build_session_record_impl,
    collect_repo_sessions as _collect_repo_sessions_impl,
    count_nonempty_lines,
    format_epoch,
    host_without_port as _host_without_port_impl,
    latest_message_preview,
    latest_message_preview_from_paths,
    parse_saved_time,
    parse_session_dir,
    safe_mtime,
    session_index_path as _session_index_path_impl,
    session_index_paths as _session_index_paths_impl,
)
from ..instance_core import agents_from_tmux_env_output
from ..instance_core import expected_instance_names as resolve_expected_instance_names
from ..state_core import load_hub_settings as load_shared_hub_settings
from ..state_core import local_runtime_log_dir
from ..state_core import port_is_bindable
from ..state_core import resolve_chat_port
from ..state_core import save_chat_port_override
from ..state_core import save_hub_settings as save_shared_hub_settings


@dataclass(frozen=True)
class TmuxRunResult:
    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


@dataclass(frozen=True)
class SessionQueryResult:
    records: dict[str, dict]
    state: str  # "ok" | "unhealthy"
    detail: str = ""


@dataclass(frozen=True)
class RepoSessionsQueryResult:
    sessions: list[dict]
    state: str  # "ok" | "unhealthy"
    detail: str = ""


class HubRuntime:
    def __init__(self, repo_root: Path | str, script_path: Path | str, tmux_socket: str = "", hub_port: int = 0):
        self.repo_root = Path(repo_root).resolve()
        self.script_path = Path(script_path).resolve()
        self.script_dir = self.script_path.parent
        self.multiagent_path = self.script_dir / "multiagent"
        self.agent_send_path = self.script_dir / "agent-send"
        self.central_log_dir = local_runtime_log_dir(self.repo_root)
        self.tmux_socket = tmux_socket
        self.hub_port = int(hub_port or 0)
        self.tmux_prefix = ["tmux"]
        if tmux_socket:
            if "/" in tmux_socket:
                self.tmux_prefix.extend(["-S", tmux_socket])
            else:
                self.tmux_prefix.extend(["-L", tmux_socket])
        self._launch_locks = {}  # session_name -> threading.Lock
        self._launch_locks_master = threading.Lock()

    def _get_launch_lock(self, session_name: str) -> threading.Lock:
        with self._launch_locks_master:
            if session_name not in self._launch_locks:
                self._launch_locks[session_name] = threading.Lock()
            return self._launch_locks[session_name]

    def tmux_run(self, args, timeout=2) -> TmuxRunResult:
        try:
            res = subprocess.run(
                [*self.tmux_prefix, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return TmuxRunResult(
                args=list(args),
                returncode=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            return TmuxRunResult(
                args=list(args),
                returncode=124,  # Standard timeout exit code
                stdout=exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                stderr=f"tmux command timed out after {timeout} seconds",
                timed_out=True,
            )

    def tmux_env(self, session_name: str, key: str) -> str:
        result = self.tmux_run(["show-environment", "-t", session_name, key])
        line = result.stdout.strip()
        if result.returncode == 0 and "=" in line:
            return line.split("=", 1)[1]
        return ""

    def tmux_env_query(self, session_name: str, key: str) -> tuple[str, bool]:
        """Returns (value, timed_out)"""
        result = self.tmux_run(["show-environment", "-t", session_name, key])
        line = result.stdout.strip()
        if result.returncode == 0 and "=" in line:
            return line.split("=", 1)[1], result.timed_out
        return "", result.timed_out

    def session_agents(self, session_name: str) -> list[str]:
        agents, _ = self.session_agents_query(session_name)
        return agents

    def session_agents_query(self, session_name: str) -> tuple[list[str], bool]:
        """Returns (agents, timed_out)"""
        agents_str, timed_out = self.tmux_env_query(session_name, "MULTIAGENT_AGENTS")
        if timed_out:
            return [], True
        if agents_str:
            return [a.strip() for a in agents_str.split(",") if a.strip()], False

        result = self.tmux_run(["show-environment", "-t", session_name])
        if result.timed_out:
            return [], True
        if result.returncode == 0:
            agents = agents_from_tmux_env_output(result.stdout)
            if agents:
                return agents, False
        return [], False

    @staticmethod
    def expected_instance_names(base_agents: list[str]) -> list[str]:
        return resolve_expected_instance_names(base_agents)

    def session_has_expected_panes(self, session_name: str, expected_instances: list[str]) -> bool:
        if self.tmux_run(["has-session", "-t", f"={session_name}"], timeout=1).returncode != 0:
            return False
        for agent in expected_instances:
            pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
            if not self.tmux_env(session_name, pane_var):
                return False
        return True

    def wait_for_session_instances(self, session_name: str, base_agents: list[str], timeout_seconds: float = 12.0) -> bool:
        expected_instances = self.expected_instance_names(base_agents)
        deadline = time.time() + max(0.5, timeout_seconds)
        while time.time() < deadline:
            if self.session_has_expected_panes(session_name, expected_instances):
                return True
            time.sleep(0.15)
        return self.session_has_expected_panes(session_name, expected_instances)

    def chat_port_for_session(self, session_name: str) -> int:
        return resolve_chat_port(self.repo_root, session_name)

    def session_index_paths(
        self,
        session_name: str,
        workspace: str = "",
        explicit_log_dir: str = "",
    ):
        return _session_index_paths_impl(
            self,
            session_name,
            workspace,
            explicit_log_dir,
        )

    def session_index_path(
        self,
        session_name: str,
        workspace: str = "",
        explicit_log_dir: str = "",
    ):
        return _session_index_path_impl(
            self,
            session_name,
            workspace,
            explicit_log_dir,
        )

    @staticmethod
    def host_without_port(host_header: str) -> str:
        return _host_without_port_impl(host_header)

    def _build_session_record(
        self,
        *,
        name: str,
        workspace: str,
        agents: list[str],
        status: str,
        attached: int,
        dead_panes: int,
        created_epoch: int = 0,
        created_at: str = "",
        updated_epoch: int = 0,
        updated_at: str = "",
        explicit_log_dir: str = "",
        index_paths: list[Path] | None = None,
        preferred_index_path: Path | None = None,
    ) -> dict:
        return _build_session_record_impl(
            self,
            name=name,
            workspace=workspace,
            agents=agents,
            status=status,
            attached=attached,
            dead_panes=dead_panes,
            created_epoch=created_epoch,
            created_at=created_at,
            updated_epoch=updated_epoch,
            updated_at=updated_at,
            explicit_log_dir=explicit_log_dir,
            index_paths=index_paths,
            preferred_index_path=preferred_index_path,
        )

    def repo_sessions(self) -> list[dict]:
        res = self.repo_sessions_query()
        return res.sessions

    def repo_sessions_query(self) -> RepoSessionsQueryResult:
        sessions, state, detail = _collect_repo_sessions_impl(self)
        return RepoSessionsQueryResult(sessions, state, detail)

    def archived_sessions(self, active_names: set[str] | list[str] | None = None) -> list[dict]:
        return _archived_sessions_impl(self, active_names)

    def active_session_records(self) -> dict[str, dict]:
        res = self.active_session_records_query()
        return res.records

    def active_session_records_query(self) -> SessionQueryResult:
        res = self.repo_sessions_query()
        return SessionQueryResult(
            records={item["name"]: item for item in res.sessions},
            state=res.state,
            detail=res.detail,
        )

    def archived_session_records(self, active_names: set[str] | list[str] | None = None) -> dict[str, dict]:
        return {item["name"]: item for item in self.archived_sessions(active_names)}

    def load_hub_settings(self) -> dict:
        return load_shared_hub_settings(self.repo_root)

    def save_hub_settings(self, raw: dict) -> dict:
        return save_shared_hub_settings(self.repo_root, raw)

    def chat_ready(self, chat_port: int) -> bool:
        return _chat_ready_impl(self, chat_port)

    def chat_server_state(self, chat_port: int) -> dict | None:
        return _chat_server_state_impl(self, chat_port)

    def chat_server_matches(self, session_name: str, chat_port: int) -> bool:
        return _chat_server_matches_impl(self, session_name, chat_port)

    def stop_chat_server(self, session_name: str) -> tuple[bool, str]:
        return _stop_chat_server_impl(
            self,
            session_name,
            subprocess_module=subprocess,
            os_module=os,
            signal_module=signal,
            time_module=time,
        )

    def _chat_launch_workspace(self, session_name: str) -> tuple[str, bool]:
        return _chat_launch_workspace_impl(self, session_name)

    def _chat_launch_session_dir(self, session_name: str, workspace: str, explicit_log_dir: str) -> Path:
        return _chat_launch_session_dir_impl(self, session_name, workspace, explicit_log_dir)

    def _chat_launch_env(self) -> dict[str, str]:
        return _chat_launch_env_impl(self)

    def ensure_chat_server(self, session_name: str) -> tuple[bool, int, str]:
        return _ensure_chat_server_impl(
            self,
            session_name,
            port_is_bindable_fn=port_is_bindable,
            save_chat_port_override_fn=save_chat_port_override,
            subprocess_module=subprocess,
            sys_module=sys,
            time_module=time,
        )

    def revive_archived_session(self, session_name: str) -> tuple[bool, str]:
        return _revive_archived_session_impl(self, session_name)

    def kill_repo_session(self, session_name: str) -> tuple[bool, str]:
        return _kill_repo_session_impl(self, session_name)

    def delete_archived_session(self, session_name: str) -> tuple[bool, str]:
        return _delete_archived_session_impl(self, session_name)
