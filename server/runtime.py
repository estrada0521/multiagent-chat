from __future__ import annotations
import logging

import subprocess
import threading
import uuid
from collections import deque
from datetime import datetime as dt_datetime
from pathlib import Path

from backend_core.agents.executables import (
    agent_launch_cmd as _agent_launch_cmd_impl,
    agent_resume_cmd as _agent_resume_cmd_impl,
    resolve_agent_executable_for_runtime as _resolve_agent_executable_impl,
)
from backend_core.tmux.lifecycle import (
    restart_agent_pane as _restart_agent_pane_impl,
    resume_agent_pane as _resume_agent_pane_impl,
)
from message_delivery import (
    mark_agent_sent as _mark_agent_sent_impl,
    send_message as _send_message_impl,
)
from .entry_write import (
    append_system_entry as _append_system_entry_impl,
    append_user_entry as _append_user_entry_impl,
)
from .index_cache import MATCHED_ENTRY_TAIL, message_entry_window
from workspace_sync.commit import (
    ensure_commit_announcements as _ensure_commit_announcements_impl,
)
from .payload import (
    build_payload_document,
    encode_payload_document,
)
from native_log_sync.syncer import NativeLogSyncer
from native_log_sync.refresh.binding_models import PaneBindingRequest
from backend_core.tmux.session import (
    active_agents as _active_agents_impl,
    pane_field as _pane_field_impl,
    pane_id_for_agent as _pane_id_for_agent_impl,
    resolve_tmux_session_name as _resolve_tmux_session_name_impl,
)
from .session_state import (
    build_session_state_payload as _build_session_state_payload_impl,
    initialize_session_state_bus as _initialize_session_state_bus_impl,
    publish_session_state_change as _publish_session_state_change_impl,
    wait_for_session_state_change as _wait_for_session_state_change_impl,
)
from pane_trace import trace_content as _trace_content_impl
from backend_core.tmux.instances import resolve_target_agents as resolve_target_agent_names
from backend_core.tmux.window import tmux_prefix_args
from backend_core.access.files import append_jsonl_entry
from .session_binding import WorkspaceSessionBinding


ENTRY_WINDOW_LIMIT = 2000


class ChatRuntime:
    def __init__(
        self,
        *,
        port: int,
        workspace: str,
        tmux_socket: str,
        hub_port: int,
        repo_root: Path | str,
        initial_running_agents: list[str] | None = None,
    ):
        self._session_binding = WorkspaceSessionBinding(workspace)
        self.port = int(port)
        self.workspace = self._session_binding.workspace
        self.tmux_socket = tmux_socket
        self.hub_port = int(hub_port)
        self.repo_root = Path(repo_root).resolve()
        self.server_instance = uuid.uuid4().hex
        self.tmux_prefix = tmux_prefix_args(self.tmux_socket) if self.tmux_socket else ["tmux"]
        # tmux never knows this session's AW name -- only the workspace it
        # runs in (AGENT_WINDOW_WORKSPACE, set once at creation and never
        # rewritten). Resolved once here and cached: it can't legitimately
        # change for the life of this process.
        self.tmux_session_name = _resolve_tmux_session_name_impl(self) or ""
        self.session_is_active = bool(self.tmux_session_name)
        self._agent_running = set(initial_running_agents or [])
        self._pane_id_cache: dict[str, str] = {}
        _initialize_session_state_bus_impl(self)
        self._native_log = NativeLogSyncer(
            session_binding=self._session_binding,
            workspace=self.workspace,
            mark_idle_fn=self._mark_idle,
            mark_running_from_native_activity_fn=self._mark_running_from_native_activity,
            notify_state_fn=self.notify_session_state_changed,
            active_agents_fn=self.active_agents,
            running_agents_fn=lambda: self._agent_running,
            pane_id_fn=self.pane_id_for_agent,
            session_is_active_fn=lambda: self.session_is_active,
        )
        self._payload_cache_lock = threading.Lock()
        self._payload_cache: dict[tuple, bytes] = {}
        self._payload_cache_order: deque[tuple] = deque(maxlen=8)
        self._matched_entries_cache_lock = threading.Lock()
        self._matched_entries_cache_sig: tuple[int, int] = (0, 0)
        self._matched_entries_cache_size = 0
        self._matched_entries_cache_entries: deque[dict] = deque(maxlen=MATCHED_ENTRY_TAIL)
        self._matched_entries_total = 0

    @property
    def session_name(self) -> str:
        return self._session_binding.session_name

    @property
    def log_path(self) -> Path:
        return self._session_binding.log_path

    @property
    def log_dir(self) -> str:
        return str(self._session_binding.session_dir)

    @property
    def session_dir(self) -> Path:
        return self._session_binding.session_dir

    def session_binding_snapshot(self) -> tuple[str, Path]:
        return self._session_binding.snapshot()

    def refresh_native_log_bindings(self, agents: list[str] | None = None) -> list[dict]:
        replace_all = agents is None
        target_agents = list(agents) if agents is not None else self.active_agents()
        pane_requests: list[PaneBindingRequest] = []
        for agent in target_agents:
            pane_id = self.pane_id_for_agent(agent)
            if not pane_id:
                continue
            pane_pid = self.pane_field(pane_id, "#{pane_pid}")
            pane_requests.append(
                PaneBindingRequest(
                    agent=agent,
                    pane_id=pane_id,
                    pane_pid=str(pane_pid or "").strip(),
                )
            )
        return self._native_log.refresh(pane_requests, replace_all=replace_all)

    def start_native_log_sync(self) -> None:
        if not self.session_is_active:
            return
        from native_log_sync.watch.watch_bindings import start_native_log_vnode_watcher
        self.refresh_native_log_bindings()
        start_native_log_vnode_watcher(self._native_log)

    def invalidate_payload_cache(self) -> None:
        with self._payload_cache_lock:
            self._payload_cache.clear()
            self._payload_cache_order.clear()

    def on_agent_pane_added(self, agent: str) -> None:
        self._native_log.on_pane_add(agent)

    def append_user_entry(self, message: str, *, targets: list[str], client: str | None = None) -> dict:
        return _append_user_entry_impl(
            self,
            message,
            targets=targets,
            datetime_class=dt_datetime,
            append_jsonl_entry_fn=append_jsonl_entry,
            client=client,
        )

    def append_system_entry(self, message: str, *, agent: str = "", **extra) -> dict:
        return _append_system_entry_impl(
            self,
            message,
            agent=agent,
            extra=extra,
            datetime_class=dt_datetime,
            append_jsonl_entry_fn=append_jsonl_entry,
        )

    def ensure_commit_announcements(self) -> None:
        _ensure_commit_announcements_impl(self)

    def _entry_window(
        self,
        *,
        limit_override: int | None = None,
        offset: int = 0,
    ) -> tuple[list[dict], bool, int]:
        return message_entry_window(
            self,
            limit_override=limit_override,
            default_limit=ENTRY_WINDOW_LIMIT,
            offset=offset,
        )

    def notify_session_state_changed(
        self,
        projections: str | list[str] | tuple[str, ...] | set[str] | None = None,
        *,
        reason: str = "",
    ) -> None:
        _publish_session_state_change_impl(self, projections, reason=reason)

    def wait_for_session_state_change(self, after_seq: int, timeout: float = 15.0) -> dict | None:
        return _wait_for_session_state_change_impl(self, after_seq, timeout=timeout)

    def session_state_payload(
        self,
        projections: str | list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> dict:
        return _build_session_state_payload_impl(
            self,
            server_instance=self.server_instance,
            session_name=self.session_name,
            projections=projections,
        )

    def payload(
        self,
        limit_override: int | None = None,
        offset: int = 0,
    ) -> bytes:
        try:
            stat = self.log_path.stat()
            index_sig = (stat.st_size, stat.st_mtime_ns)
        except OSError:
            index_sig = (0, 0)
        cache_key = (
            self.session_name,
            index_sig,
            limit_override,
            offset,
            bool(self.session_is_active),
        )
        with self._payload_cache_lock:
            cached = self._payload_cache.get(cache_key)
            if cached is not None:
                return cached
        entries, has_older, _total_count = self._entry_window(
            limit_override=limit_override,
            offset=offset,
        )
        payload_doc = build_payload_document(
            server_instance=self.server_instance,
            has_older=has_older,
            entries=entries,
        )
        body = encode_payload_document(payload_doc)
        with self._payload_cache_lock:
            if cache_key not in self._payload_cache:
                self._payload_cache_order.append(cache_key)
            self._payload_cache[cache_key] = body
            while len(self._payload_cache) > self._payload_cache_order.maxlen:
                old_key = self._payload_cache_order.popleft()
                self._payload_cache.pop(old_key, None)
        return body


    def active_agents(self) -> list[str]:
        return _active_agents_impl(
            self,
            subprocess_module=subprocess,
        )

    def resolve_target_agents(self, target: str) -> list[str]:
        return resolve_target_agent_names(target, self.active_agents())

    def pane_id_for_agent(self, agent_name: str) -> str:
        cached = self._pane_id_cache.get(agent_name)
        if cached:
            return cached
        pane_id = _pane_id_for_agent_impl(
            self,
            agent_name,
            subprocess_module=subprocess,
        )
        if pane_id:
            self._pane_id_cache[agent_name] = pane_id
        return pane_id

    def invalidate_pane_id_cache(self) -> None:
        """Drop cached pane IDs after a topology change (add/remove agent).

        A pane's tmux env var is only ever written at those two points, so
        the cache only needs invalidating there -- not on every send.
        """
        self._pane_id_cache.clear()

    def pane_field(self, pane_id: str, field: str) -> str:
        return _pane_field_impl(self, pane_id, field, subprocess_module=subprocess)

    def _mark_agent_sent(self, agent_name: str) -> None:
        _mark_agent_sent_impl(self, agent_name)

    def mark_agents_running(self, agents: list[str]) -> None:
        for agent in agents:
            self._mark_running(agent)

    def running_agents_for_reload(self) -> list[str]:
        return sorted(self._agent_running)

    def _mark_running(self, agent: str) -> None:
        already_running = agent in self._agent_running
        if not already_running:
            self._native_log.clear_agent_runtime_display(agent)
        self._agent_running.add(agent)
        if not already_running:
            if not self._native_log.has_log_binding(agent):
                self.refresh_native_log_bindings([agent])
                if self._native_log.has_log_binding(agent):
                    self._initial_sync_agent(agent)
                else:
                    logging.error("native log bind failed for %s", agent)
            else:
                # Re-resolve to detect session switches (e.g. new Claude conversation file)
                old_path = self._native_log.log_path_for_agent(agent)
                self.refresh_native_log_bindings([agent])
                new_path = self._native_log.log_path_for_agent(agent)
                if new_path and new_path != old_path:
                    self._initial_sync_agent(agent)
            self.notify_session_state_changed(["statuses", "agent_runtime"], reason="agent-status")

    def _mark_running_from_native_activity(self, agent: str) -> None:
        """Mark an idle agent running without rebinding its already-watched log."""
        if agent in self._agent_running:
            return
        self._agent_running.add(agent)
        self.notify_session_state_changed(["statuses"], reason="agent-native-activity")

    def _initial_sync_agent(self, agent: str) -> None:
        """Run a full initial emit to capture any log content written before binding."""
        from native_log_sync.watch.emit_events import emit_agent_updates
        path = self._native_log.log_path_for_agent(agent)
        if path:
            emit_agent_updates(self._native_log, agent, path)

    def _mark_idle(self, agent: str) -> None:
        was_running = agent in self._agent_running
        self._agent_running.discard(agent)
        cleared = self._native_log.clear_agent_runtime_display(agent)
        if was_running:
            self.notify_session_state_changed(["statuses", "agent_runtime"], reason="agent-status")
        elif cleared:
            self.notify_session_state_changed(["agent_runtime"], reason="agent-runtime-clear")

    def agent_launch_cmd(self, agent_name: str) -> str:
        return _agent_launch_cmd_impl(self, agent_name)

    def agent_resume_cmd(self, agent_name: str) -> str:
        return _agent_resume_cmd_impl(self, agent_name)

    @staticmethod
    def resolve_agent_executable(agent_name: str) -> str:
        return _resolve_agent_executable_impl(agent_name)

    def restart_agent_pane(self, agent_name: str) -> tuple[bool, str]:
        return _restart_agent_pane_impl(self, agent_name)

    def resume_agent_pane(self, agent_name: str) -> tuple[bool, str]:
        return _resume_agent_pane_impl(self, agent_name)

    def send_message(
        self,
        target: str,
        message: str,
        append_entry: bool = True,
        client: str | None = None,
    ) -> tuple[int, dict]:
        return _send_message_impl(
            self,
            target,
            message,
            append_entry=append_entry,
            client=client,
        )

    def agent_statuses(self) -> dict[str, str]:
        return self._native_log.agent_statuses(self._agent_running)

    def agent_runtime_state(self) -> dict[str, dict]:
        return self._native_log.agent_runtime_state()

    def native_log_watched_paths(self) -> dict[str, str]:
        return self._native_log.watched_paths()

    def trace_content(self, agent: str, *, tail_lines: int) -> str:
        pane_id = self.pane_id_for_agent(agent)
        if not pane_id:
            return "Offline"
        return _trace_content_impl(self, pane_id, tail_lines=tail_lines)
