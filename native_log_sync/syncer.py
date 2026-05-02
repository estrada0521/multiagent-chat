from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

from native_log_sync.agents._shared.runtime_state import (
    first_seen_for_agent as _first_seen_for_agent_impl,
    initialize_native_log_runtime_state as _init_state,
)
from native_log_sync.agents import on_pane_restart as _on_pane_restart_impl, on_pane_add as _on_pane_add_impl
from native_log_sync.agents._shared.workspace_paths import workspace_aliases as _workspace_aliases_impl
from native_log_sync.io.sync_state import (
    load_sync_state as _load_sync_state_impl,
    save_sync_state as _save_sync_state_impl,
    sync_cursor_status as _sync_cursor_status_impl,
)
from native_log_sync.refresh.binding_models import PaneBindingRequest
from native_log_sync.refresh.refresh_bindings import refresh_native_log_bindings as _refresh_bindings_impl
from native_log_sync.watch.emit_events import idle_running_display_for_api, refresh_idle_statuses


class NativeLogSyncer:
    """Owns all native-log-sync state. ChatRuntime holds one instance and delegates."""

    def __init__(
        self,
        *,
        index_path: Path | str,
        session_name: str,
        workspace: str,
        mark_idle_fn: Callable[[str], None],
        notify_state_fn: Callable[..., None],
        active_agents_fn: Callable[[], list[str]],
        session_is_active_fn: Callable[[], bool],
    ) -> None:
        self.index_path = Path(index_path)
        self.session_name = session_name
        self.workspace = workspace
        self._mark_idle = mark_idle_fn
        self._notify_state_fn = notify_state_fn
        self._active_agents_fn = active_agents_fn
        self._session_is_active_fn = session_is_active_fn
        _init_state(self)

    # ── callbacks required by native_log_sync internals ──

    def notify_session_state_changed(self, keys, *, reason: str = "") -> None:
        self._notify_state_fn(keys, reason=reason)

    def active_agents(self) -> list[str]:
        return self._active_agents_fn()

    @property
    def session_is_active(self) -> bool:
        return bool(self._session_is_active_fn())

    # ── state persistence ──

    def load_sync_state(self) -> dict:
        return _load_sync_state_impl(self)

    def save_sync_state(self) -> None:
        _save_sync_state_impl(self, time_module=time)

    # ── helpers used by sync functions ──

    def _first_seen_for_agent(self, agent: str) -> float:
        return _first_seen_for_agent_impl(self, agent, time_module=time)

    def _workspace_aliases(self, workspace: str) -> list[str]:
        return _workspace_aliases_impl(self, workspace, path_class=Path)

    # ── public API called by ChatRuntime ──

    def on_pane_restart(self, agent: str) -> None:
        _on_pane_restart_impl(self, agent)

    def on_pane_add(self, agent: str) -> None:
        _on_pane_add_impl(self, agent)

    def refresh(
        self,
        pane_requests: list[PaneBindingRequest],
        *,
        replace_all: bool = True,
        reason: str = "",
    ) -> list[dict]:
        bindings = _refresh_bindings_impl(self, pane_requests, replace_all=replace_all, reason=reason)
        return [
            {
                "agent": item.agent,
                "type": item.base,
                "pane_id": item.pane_id,
                "pane_pid": item.pane_pid,
                "log_path": item.path,
                "watch_roots": list(item.watch_roots),
                "source": item.source,
            }
            for item in bindings
        ]

    def agent_statuses(self, running_agents: set[str]) -> dict[str, str]:
        return refresh_idle_statuses(self, running_agents)

    def agent_runtime_state(self) -> dict[str, dict]:
        return idle_running_display_for_api(self._idle_running_display_by_agent)

    def cursor_status(self) -> list[dict]:
        return _sync_cursor_status_impl(self, os_module=os)

    def watched_paths(self) -> dict[str, str]:
        watcher = getattr(self, "_native_log_vnode_watcher", None)
        return watcher.get_watched_paths() if watcher else {}
