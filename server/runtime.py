from __future__ import annotations
import logging

import json
import os
import subprocess
import threading
import time
import uuid
from collections import deque
from datetime import datetime as dt_datetime
from pathlib import Path
from urllib.parse import quote

from backend_core.agents.registry import generate_agent_message_selectors
from backend_core.agents.ensure_clis import (
    agent_launch_cmd as _agent_launch_cmd_impl,
    agent_resume_cmd as _agent_resume_cmd_impl,
    resolve_agent_executable_for_runtime as _resolve_agent_executable_impl,
)
from backend_core.tmux.lifecycle import (
    restart_agent_pane as _restart_agent_pane_impl,
    resume_agent_pane as _resume_agent_pane_impl,
)
from message_delivery import (
    _update_running_env as _update_running_env_impl,
    mark_agent_sent as _mark_agent_sent_impl,
    send_message as _send_message_impl,
    wait_for_send_slot as _wait_for_send_slot_impl,
)
from backend_core.session.launch import launch_session as _launch_session
from .entry_write import (
    append_system_entry as _append_system_entry_impl,
)
from .entries import entry_window as _entry_window_impl
from .font_style import (
    chat_font_settings_inline_style as _chat_font_settings_inline_style_impl,
    font_family_stack as _font_family_stack_impl,
)
from workspace_sync.commit import (
    ensure_commit_announcements as _ensure_commit_announcements_impl,
)
from .payload import (
    attachment_paths as payload_attachment_paths,
    build_payload_document,
    encode_payload_document,
    summarize_light_entry,
)
from .style import (
    BOLD_MODE_VIEWPORT_MAX_PX,
    _bh_agent_detail_selectors as _bh_agent_detail_selectors_impl,
    _chat_bold_mode_rules_block as _chat_bold_mode_rules_block_impl,
)
from .index_cache import matched_entries as _matched_entries_impl
from native_log_sync.syncer import NativeLogSyncer
from native_log_sync.refresh.binding_models import PaneBindingRequest
from backend_core.tmux.session import (
    active_agents as _active_agents_impl,
    agents_from_pane_env as _agents_from_pane_env_impl,
    pane_field as _pane_field_impl,
    pane_id_for_agent as _pane_id_for_agent_impl,
)
from auto_mode.monitor import monitor_status as _monitor_status_impl, set_monitor_active as _set_monitor_active_impl
from frontedge.session_state import (
    build_session_state_payload as _build_session_state_payload_impl,
    initialize_session_state_bus as _initialize_session_state_bus_impl,
    publish_session_state_change as _publish_session_state_change_impl,
    wait_for_session_state_change as _wait_for_session_state_change_impl,
)
from native_log_sync.agents.opencode.read_runtime import parse_opencode_runtime as _parse_opencode_runtime_impl
from pane_trace import trace_content as _trace_content_impl
from backend_core.tmux.instances import agents_from_tmux_env_output
from backend_core.tmux.instances import resolve_target_agents as resolve_target_agent_names
from backend_core.access.files import append_jsonl_entry
from backend_core.access.settings import load_hub_settings as load_shared_hub_settings

_CLAUDE_SEND_COOLDOWN_SECONDS = 8.0


def _chat_bold_mode_rules_block() -> str:
    return _chat_bold_mode_rules_block_impl()


def _bh_agent_detail_selectors(prefix: str = "") -> str:
    return _bh_agent_detail_selectors_impl(prefix=prefix)


class ChatRuntime:
    PUBLIC_LIGHT_MESSAGE_CHAR_LIMIT = 1500
    PUBLIC_LIGHT_CODE_THRESHOLD = 800
    PUBLIC_LIGHT_ATTACHMENT_PREVIEW_LIMIT = 2

    def __init__(
        self,
        *,
        index_path: Path | str,
        limit: int,
        filter_agent: str,
        session_name: str,
        follow_mode: bool,
        port: int,
        agent_send_path: Path | str,
        workspace: str,
        log_dir: str,
        targets: list[str],
        tmux_socket: str,
        hub_port: int,
        repo_root: Path | str,
        session_is_active: bool,
    ):
        self.index_path = Path(index_path)
        self.limit = int(limit) if int(limit) > 0 else 50
        self.filter_agent = (filter_agent or "").strip().lower()
        self.session_name = session_name
        self.follow_mode = bool(follow_mode)
        self.port = int(port)
        self.agent_send_path = str(agent_send_path)
        self.workspace = workspace
        self.log_dir = log_dir
        self.targets = list(targets or [])
        self.tmux_socket = tmux_socket
        self.hub_port = int(hub_port)
        self.repo_root = Path(repo_root).resolve()
        self.session_is_active = bool(session_is_active)
        self.server_instance = uuid.uuid4().hex
        self.tmux_prefix = ["tmux"]
        if self.tmux_socket:
            if "/" in self.tmux_socket:
                self.tmux_prefix.extend(["-S", self.tmux_socket])
            else:
                self.tmux_prefix.extend(["-L", self.tmux_socket])
        self._caffeinate_proc = None
        self._agent_last_send_ts: dict[str, float] = {}
        self._agent_running: set[str] = set()
        _initialize_session_state_bus_impl(self)
        self._native_log = NativeLogSyncer(
            index_path=self.index_path,
            session_name=self.session_name,
            workspace=self.workspace,
            mark_idle_fn=self._mark_idle,
            notify_state_fn=self.notify_session_state_changed,
            active_agents_fn=self.active_agents,
        )
        self._payload_cache_lock = threading.Lock()
        self._payload_cache: dict[tuple, bytes] = {}
        self._payload_cache_order: deque[tuple] = deque(maxlen=8)
        self._payload_targets_cache: tuple[float, list[str]] = (0.0, [])
        self._matched_entries_cache_lock = threading.Lock()
        self._matched_entries_cache_sig: tuple[int, int] = (0, 0)
        self._matched_entries_cache_size = 0
        self._matched_entries_cache_entries: list[dict] = []
        self._matched_entries_cache_seen_ids: set[str] = set()

    def load_chat_settings(self) -> dict:
        return load_shared_hub_settings(self.repo_root)

    def refresh_native_log_bindings(
        self,
        agents: list[str] | None = None,
        *,
        reason: str = "",
    ) -> list[dict]:
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
        return self._native_log.refresh(pane_requests, replace_all=replace_all, reason=reason)

    def start_native_log_sync(self) -> None:
        from native_log_sync.api import start_watchers
        self.refresh_native_log_bindings(reason="startup")
        start_watchers(self._native_log)

    def _parse_opencode_runtime(self, agent: str, limit: int) -> list[dict] | None:
        return _parse_opencode_runtime_impl(self._native_log, agent, limit)

    @staticmethod
    def _font_family_stack(selection: str, role: str) -> str:
        return _font_family_stack_impl(selection, role)

    @classmethod
    def chat_font_settings_inline_style(cls, settings: dict) -> str:
        return _chat_font_settings_inline_style_impl(
            settings,
            bold_mode_viewport_max_px=BOLD_MODE_VIEWPORT_MAX_PX,
            generate_agent_message_selectors_fn=generate_agent_message_selectors,
            chat_bold_mode_rules_block_fn=_chat_bold_mode_rules_block,
            bh_agent_detail_selectors_fn=_bh_agent_detail_selectors,
            font_family_stack_fn=cls._font_family_stack,
        )


    def append_system_entry(self, message: str, *, agent: str = "", **extra) -> dict:
        return _append_system_entry_impl(
            self,
            message,
            agent=agent,
            extra=extra,
            datetime_class=dt_datetime,
            uuid_module=uuid,
            append_jsonl_entry_fn=append_jsonl_entry,
        )

    def ensure_commit_announcements(self) -> None:
        _ensure_commit_announcements_impl(self)

    def matches(self, entry: dict) -> bool:
        if not self.filter_agent:
            return True
        if entry.get("sender", "").lower() == self.filter_agent:
            return True
        return any(t.lower() == self.filter_agent for t in entry.get("targets", []))

    @staticmethod
    def attachment_paths(message: str) -> list[str]:
        return payload_attachment_paths(message)

    def _matched_entries(self) -> list[dict]:
        return _matched_entries_impl(self)

    def _entry_window(
        self,
        *,
        limit_override: int | None = None,
        before_msg_id: str = "",
        around_msg_id: str = "",
    ) -> tuple[list[dict], bool, int]:
        return _entry_window_impl(
            self._matched_entries(),
            limit_override=limit_override,
            default_limit=self.limit,
            before_msg_id=before_msg_id,
            around_msg_id=around_msg_id,
        )

    def _light_entry(self, entry: dict) -> dict:
        return summarize_light_entry(
            entry,
            message_char_limit=self.PUBLIC_LIGHT_MESSAGE_CHAR_LIMIT,
            code_threshold=self.PUBLIC_LIGHT_CODE_THRESHOLD,
            attachment_preview_limit=self.PUBLIC_LIGHT_ATTACHMENT_PREVIEW_LIMIT,
        )

    def read_entries(
        self,
        limit_override: int | None = None,
        before_msg_id: str = "",
        around_msg_id: str = "",
        light_mode: bool = False,
    ) -> list[dict]:
        entries, _has_older = self._entry_window(
            limit_override=limit_override,
            before_msg_id=before_msg_id,
            around_msg_id=around_msg_id,
        )
        if light_mode:
            return [self._light_entry(entry) for entry in entries]
        return entries

    def entry_by_id(self, msg_id: str, *, light_mode: bool = False):
        target = (msg_id or "").strip()
        if not target:
            return None
        for entry in reversed(self._matched_entries()):
            if str(entry.get("msg_id") or "") != target:
                continue
            return self._light_entry(entry) if light_mode else entry
        return None

    def _reply_preview_for(self, reply_to: str) -> str:
        source = self.entry_by_id(reply_to, light_mode=True)
        if not source:
            return ""
        src_sender = str(source.get("sender") or "unknown").strip() or "unknown"
        src_message = str(source.get("message") or "")
        if src_message.startswith("[From:"):
            idx = src_message.find("]")
            if idx != -1:
                src_message = src_message[idx + 1 :].lstrip()
        preview = src_message[:80].replace("\n", " ")
        return f"{src_sender}: {preview}"

    def normalized_events_for_msg(self, msg_id: str) -> dict | None:
        entry = self.entry_by_id(msg_id, light_mode=False)
        if entry is None:
            return None
        rel = str(entry.get("normalized_event_path") or "").strip()
        if not rel:
            return {"entry": entry, "events": [], "path": "", "missing": True}
        base = self.index_path.parent.resolve()
        path = (base / rel).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            return {"entry": entry, "events": [], "path": rel, "missing": True}
        if not path.exists():
            return {"entry": entry, "events": [], "path": rel, "missing": True}
        events: list[dict] = []
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f):
                text = line.strip()
                if not text:
                    continue
                try:
                    events.append(json.loads(text))
                except json.JSONDecodeError:
                    events.append({"event": "raw.line", "seq": idx, "text": text})
        return {"entry": entry, "events": events, "path": rel, "missing": False}

    def provider_runtime_state(self) -> dict:
        path = self.index_path.parent / ".provider-runtime.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def session_metadata(self) -> dict:
        session_slug = quote(self.session_name, safe="")
        launch_pending = self.launch_pending()
        return {
            "server_instance": self.server_instance,
            "session": self.session_name,
            "active": self.session_is_active,
            "launch_pending": launch_pending,
            "source": str(self.index_path),
            "workspace": self.workspace,
            "log_dir": self.log_dir,
            "port": self.port,
            "hub_port": self.hub_port,
            "session_path": f"/session/{session_slug}/",
            "follow_path": f"/session/{session_slug}/?follow=1",
        }

    def pending_launch_path(self) -> Path:
        return self.index_path.parent / ".pending-launch.json"

    def pending_launch_config(self) -> dict:
        path = self.pending_launch_path()
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        pending_session = str(data.get("session") or "").strip()
        if pending_session and pending_session != self.session_name:
            return {}
        return data

    def launch_pending(self) -> bool:
        return (not self.session_is_active) and bool(self.pending_launch_config())

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

    def mark_session_activated(self) -> None:
        self.session_is_active = True
        try:
            pending_path = self.pending_launch_path()
            if pending_path.exists():
                pending_path.unlink()
        except Exception:
            pass
        self.notify_session_state_changed(["base", "targets", "statuses"], reason="session-activated")

    def payload(
        self,
        limit_override: int | None = None,
        before_msg_id: str = "",
        around_msg_id: str = "",
        light_mode: bool = False,
    ) -> bytes:
        now = time.monotonic()
        try:
            stat = self.index_path.stat()
            index_sig = (stat.st_size, stat.st_mtime_ns)
        except OSError:
            index_sig = (0, 0)
        cache_key = (
            index_sig,
            limit_override,
            before_msg_id,
            around_msg_id,
            bool(light_mode),
            bool(self.session_is_active),
            bool(self.follow_mode),
            self.filter_agent,
        )
        with self._payload_cache_lock:
            cached = self._payload_cache.get(cache_key)
            if cached is not None:
                return cached
        meta = self.session_metadata()
        entries, has_older, total_count = self._entry_window(
            limit_override=limit_override,
            before_msg_id=before_msg_id,
            around_msg_id=around_msg_id,
        )
        meta["total_messages"] = total_count
        if light_mode:
            entries = [self._light_entry(entry) for entry in entries]
        targets_cached_at, cached_targets = self._payload_targets_cache
        if now - targets_cached_at < 2.0:
            targets = list(cached_targets)
        else:
            targets = self.active_agents()
            self._payload_targets_cache = (now, list(targets))
        payload_doc = build_payload_document(
            meta=meta,
            filter_agent=self.filter_agent,
            follow_mode=self.follow_mode,
            targets=targets,
            has_older=has_older,
            light_mode=bool(light_mode),
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


    def auto_mode_status(self) -> dict:
        return _monitor_status_impl(
            self.tmux_prefix,
            self.session_name,
            subprocess_module=subprocess,
            os_module=os,
            path_class=Path,
            logging_module=logging,
        )

    def _apply_saved_monitor_setting(self) -> bool:
        try:
            active = bool(self.load_chat_settings().get("chat_auto_mode", False))
        except Exception as exc:
            logging.error("Failed to load chat_auto_mode setting: %s", exc, exc_info=True)
            return False
        script_path = Path(self.agent_send_path).resolve().parent.parent / "auto_mode" / "auto-mode"
        return _set_monitor_active_impl(
            self.tmux_prefix,
            self.session_name,
            auto_mode_script=script_path,
            tmux_socket=getattr(self, "tmux_socket", ""),
            active=active,
        )

    def active_agents(self) -> list[str]:
        return _active_agents_impl(
            self,
            subprocess_module=subprocess,
            logging_module=logging,
        )

    def _agents_from_pane_env(self) -> list[str]:
        return _agents_from_pane_env_impl(
            self,
            subprocess_module=subprocess,
            logging_module=logging,
            agents_from_tmux_env_output_fn=agents_from_tmux_env_output,
        )

    def resolve_target_agents(self, target: str) -> list[str]:
        return resolve_target_agent_names(target, self.active_agents())

    def pane_id_for_agent(self, agent_name: str) -> str:
        return _pane_id_for_agent_impl(
            self,
            agent_name,
            subprocess_module=subprocess,
        )

    def pane_field(self, pane_id: str, field: str) -> str:
        return _pane_field_impl(self, pane_id, field, subprocess_module=subprocess)

    def _wait_for_send_slot(self, agent_name: str) -> None:
        _wait_for_send_slot_impl(
            self,
            agent_name,
            claude_send_cooldown_seconds=_CLAUDE_SEND_COOLDOWN_SECONDS,
        )

    def _mark_agent_sent(self, agent_name: str) -> None:
        _mark_agent_sent_impl(self, agent_name)

    def _mark_running(self, agent: str) -> None:
        already_running = agent in self._agent_running
        self._agent_running.add(agent)
        _update_running_env_impl(self, agent, True)
        if not already_running:
            self.notify_session_state_changed(["statuses"], reason="agent-status")

    def _mark_idle(self, agent: str) -> None:
        was_running = agent in self._agent_running
        self._agent_running.discard(agent)
        _update_running_env_impl(self, agent, False)
        if was_running:
            self.notify_session_state_changed(["statuses"], reason="agent-status")

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
        reply_to: str = "",
        silent: bool = False,
        raw: bool = False,
        append_entry: bool = True,
    ) -> tuple[int, dict]:
        return _send_message_impl(
            self,
            target,
            message,
            reply_to=reply_to,
            silent=silent,
            raw=raw,
            append_entry=append_entry,
        )

    def launch_pending_session(self, requested_targets: list[str] | tuple[str, ...] | str) -> tuple[int, dict]:
        if not self.launch_pending():
            return 400, {"ok": False, "error": "session is already active"}
        if isinstance(requested_targets, str):
            raw_targets = [item.strip() for item in requested_targets.split(",") if item.strip()]
        else:
            raw_targets = [str(item).strip() for item in (requested_targets or []) if str(item).strip()]
        if not raw_targets:
            return 400, {"ok": False, "error": "agent required"}
        delivery_targets: list[str] = []
        seen_targets: set[str] = set()
        for raw_target in raw_targets:
            if raw_target in {"user", "others"}:
                return 400, {"ok": False, "error": "select an initial agent"}
            for resolved in self.resolve_target_agents(raw_target):
                if resolved in {"user", "others"} or resolved in seen_targets:
                    continue
                seen_targets.add(resolved)
                delivery_targets.append(resolved)
        if len(delivery_targets) != 1:
            return 400, {"ok": False, "error": "select exactly one initial agent"}
        activated, payload = _launch_session(self, delivery_targets)
        if not activated:
            return 400, payload
        self._apply_saved_monitor_setting()
        return 200, {
            **payload,
            "selected_agent": delivery_targets[0],
            "targets": self.active_agents(),
        }

    def agent_statuses(self) -> dict[str, str]:
        return self._native_log.agent_statuses(self._agent_running)

    def agent_runtime_state(self) -> dict[str, dict]:
        return self._native_log.agent_runtime_state()

    def trace_content(self, agent: str, *, tail_lines: int | None = None) -> str:
        pane_id = self.pane_id_for_agent(agent)
        if not pane_id:
            return "Offline"
        return _trace_content_impl(self, pane_id, tail_lines=tail_lines)
