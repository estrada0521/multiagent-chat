from __future__ import annotations
import fcntl
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

from ..agents.registry import generate_agent_message_selectors
from .agent_lifecycle import (
    agent_launch_cmd as _agent_launch_cmd_impl,
    agent_resume_cmd as _agent_resume_cmd_impl,
    resolve_agent_executable as _resolve_agent_executable_impl,
    restart_agent_pane as _restart_agent_pane_impl,
    resume_agent_pane as _resume_agent_pane_impl,
)
from .delivery import (
    launch_pending_session as _launch_pending_session_impl,
    mark_agent_sent as _mark_agent_sent_impl,
    parse_pane_direct_command as _parse_pane_direct_command_impl,
    pane_prompt_ready as _pane_prompt_ready_impl,
    send_message as _send_message_impl,
    wait_for_agent_prompt as _wait_for_agent_prompt_impl,
    wait_for_send_slot as _wait_for_send_slot_impl,
)
from .entry_write import (
    append_system_entry as _append_system_entry_impl,
)
from .entries import entry_window as _entry_window_impl
from .font_style import (
    chat_font_settings_inline_style as _chat_font_settings_inline_style_impl,
    font_family_stack as _font_family_stack_impl,
)
from .commit import (
    current_git_commit as _current_git_commit_impl,
    ensure_commit_announcements as _ensure_commit_announcements_impl,
    git_commits_since as _git_commits_since_impl,
    has_logged_commit_entry as _has_logged_commit_entry_impl,
    read_commit_state as _read_commit_state_impl,
    read_commit_state_locked as _read_commit_state_locked_impl,
    record_git_commit as _record_git_commit_impl,
    record_git_commit_locked as _record_git_commit_locked_impl,
    write_commit_state as _write_commit_state_impl,
    write_commit_state_locked as _write_commit_state_locked_impl,
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
from .thinking_kind import entry_with_inferred_kind, should_omit_entry_from_chat
from native_log_sync.api import (
    idle_display_for_api as _idle_running_display_for_api_impl,
    refresh_idle_statuses as _refresh_native_log_idle_running_statuses_impl,
)
from .native_log_state import (
    first_seen_for_agent as _first_seen_for_agent_impl,
    initialize_native_log_runtime_state as _initialize_native_log_runtime_state_impl,
)
from native_log_sync.io.state_paths import (
    canonical_native_log_sync_lock_path,
    canonical_native_log_sync_state_path,
)
from native_log_sync.agents._shared.path_state import (
    NativeLogCursor,
    OpenCodeCursor,
    _advance_native_cursor,
    _agent_base_name,
)
from native_log_sync.io.sync_timing import (
    FIRST_SEEN_GRACE_SECONDS,
    SYNC_BIND_BACKFILL_WINDOW_SECONDS,
)
from native_log_sync.agents._shared.workspace_paths import (
    workspace_aliases as _workspace_aliases_impl,
)
from native_log_sync.agents.claude.read_updates import (
    sync_claude_assistant_messages as _sync_claude_assistant_messages_impl,
)
from native_log_sync.agents.codex.read_updates import (
    sync_codex_assistant_messages as _sync_codex_assistant_messages_impl,
)
from native_log_sync.agents.copilot.read_updates import (
    sync_copilot_assistant_messages as _sync_copilot_assistant_messages_impl,
)
from native_log_sync.agents.cursor.read_updates import (
    sync_cursor_assistant_messages as _sync_cursor_assistant_messages_impl,
)
from native_log_sync.agents.gemini.read_updates import (
    sync_gemini_assistant_messages as _sync_gemini_assistant_messages_impl,
)
from native_log_sync.agents.opencode.read_updates import (
    sync_opencode_assistant_messages as _sync_opencode_assistant_messages_impl,
)
from native_log_sync.agents.qwen.read_updates import (
    sync_qwen_assistant_messages as _sync_qwen_assistant_messages_impl,
)
from native_log_sync.io.sync_state import load_sync_state as _load_sync_state_impl
from native_log_sync.io.sync_state import save_sync_state as _save_sync_state_impl
from native_log_sync.io.sync_state import sync_cursor_status as _sync_cursor_status_impl
from native_log_sync.refresh.binding_models import PaneBindingRequest
from native_log_sync.refresh.refresh_bindings import refresh_native_log_bindings as _refresh_native_log_bindings_impl
from .session_runtime import (
    active_agents as _active_agents_impl,
    agents_from_pane_env as _agents_from_pane_env_impl,
    pane_field as _pane_field_impl,
    pane_id_for_agent as _pane_id_for_agent_impl,
    resolve_target_agents as _resolve_target_agents_impl,
)
from auto_mode.api import auto_mode_status as _auto_mode_status_impl
from native_log_sync.agents.opencode.read_runtime import parse_opencode_runtime as _parse_opencode_runtime_impl
from .trace import trace_content as _trace_content_impl
from ..multiagent.instances import agents_from_tmux_env_output
from ..multiagent.instances import resolve_target_agents as resolve_target_agent_names
from ..jsonl_append import append_jsonl_entry
from ..redacted_placeholder import agent_index_entry_omit_for_redacted
from ..runtime.state import load_hub_settings as load_shared_hub_settings

_SEND_PROMPT_WAIT_SECONDS = 6.0
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
        self.commit_state_path = self.index_path.parent / ".agent-index-commit-state.json"
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
        _session_dir = self.index_path.parent
        self.sync_state_path = canonical_native_log_sync_state_path(_session_dir)
        self.sync_lock_path = canonical_native_log_sync_lock_path(_session_dir)
        self.tmux_prefix = ["tmux"]
        if self.tmux_socket:
            if "/" in self.tmux_socket:
                self.tmux_prefix.extend(["-S", self.tmux_socket])
            else:
                self.tmux_prefix.extend(["-L", self.tmux_socket])
        self._caffeinate_proc = None
        _initialize_native_log_runtime_state_impl(self)
        self._agent_last_send_ts: dict[str, float] = {}
        self._agent_running: set[str] = set()
        self._payload_cache_lock = threading.Lock()
        self._payload_cache: dict[tuple, bytes] = {}
        self._payload_cache_order: deque[tuple] = deque(maxlen=8)
        self._payload_targets_cache: tuple[float, list[str]] = (0.0, [])
        self._last_commit_announcement_check = 0.0
        self._matched_entries_cache_lock = threading.Lock()
        self._matched_entries_cache_sig: tuple[int, int] = (0, 0)
        self._matched_entries_cache_size = 0
        self._matched_entries_cache_entries: list[dict] = []
        self._matched_entries_cache_seen_ids: set[str] = set()
        self.running_grace_seconds = 2.0
        self._caffeinate_args = ["caffeinate", "-s"]
        try:
            settings = self.load_chat_settings()
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            settings = {}
        if bool(settings.get("chat_awake", False)):
            self.ensure_caffeinate_active()

    def load_chat_settings(self) -> dict:
        return load_shared_hub_settings(self.repo_root)

    def load_sync_state(self) -> dict:
        return _load_sync_state_impl(self)

    def _first_seen_for_agent(self, agent: str) -> float:
        return _first_seen_for_agent_impl(self, agent, time_module=time)

    def _workspace_aliases(self, workspace: str) -> list[str]:
        return _workspace_aliases_impl(self, workspace, path_class=Path)

    def save_sync_state(self) -> None:
        _save_sync_state_impl(self, time_module=time)

    def sync_cursor_status(self) -> list[dict]:
        return _sync_cursor_status_impl(self, os_module=os)

    def refresh_native_log_bindings(
        self,
        agents: list[str] | None = None,
        *,
        reason: str = "",
    ) -> list[dict]:
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
        bindings = _refresh_native_log_bindings_impl(self, pane_requests, reason=reason)
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

    def _parse_opencode_runtime(self, agent: str, limit: int) -> list[dict] | None:
        return _parse_opencode_runtime_impl(self, agent, limit)

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

    def _read_commit_state_locked(self, handle) -> dict:
        return _read_commit_state_locked_impl(
            self,
            handle,
            json_module=json,
            logging_module=logging,
        )

    def _write_commit_state_locked(self, handle, commit: dict) -> None:
        _write_commit_state_locked_impl(self, handle, commit, json_module=json)

    def has_logged_commit_entry(self, commit_hash: str, *, recent_limit: int = 256) -> bool:
        return _has_logged_commit_entry_impl(
            self,
            commit_hash,
            recent_limit=recent_limit,
            deque_class=deque,
            json_module=json,
            logging_module=logging,
        )

    def read_commit_state(self) -> dict:
        return _read_commit_state_impl(
            self,
            fcntl_module=fcntl,
            logging_module=logging,
        )

    def write_commit_state(self, commit: dict) -> None:
        _write_commit_state_impl(
            self,
            commit,
            fcntl_module=fcntl,
            logging_module=logging,
        )

    def _record_git_commit_locked(self, handle, commit: dict, *, agent: str = "") -> bool:
        return _record_git_commit_locked_impl(self, handle, commit, agent=agent)

    def record_git_commit(self, *, commit_hash: str, commit_short: str, subject: str, agent: str = "") -> bool:
        return _record_git_commit_impl(
            self,
            commit_hash=commit_hash,
            commit_short=commit_short,
            subject=subject,
            agent=agent,
            fcntl_module=fcntl,
            logging_module=logging,
        )

    def current_git_commit(self) -> dict | None:
        return _current_git_commit_impl(
            self,
            subprocess_module=subprocess,
            logging_module=logging,
        )

    def git_commits_since(self, base_hash: str) -> list[dict] | None:
        return _git_commits_since_impl(
            self,
            base_hash,
            subprocess_module=subprocess,
            logging_module=logging,
        )

    def ensure_commit_announcements(self) -> None:
        _ensure_commit_announcements_impl(
            self,
            fcntl_module=fcntl,
            logging_module=logging,
        )

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
        if not self.index_path.exists():
            return []
        try:
            stat = self.index_path.stat()
        except OSError:
            return []
        current_sig = (stat.st_size, stat.st_mtime_ns)
        with self._matched_entries_cache_lock:
            if self._matched_entries_cache_sig == current_sig:
                return list(self._matched_entries_cache_entries)
            can_append = (
                self._matched_entries_cache_size > 0
                and stat.st_size > self._matched_entries_cache_size
            )
            if can_append:
                entries = list(self._matched_entries_cache_entries)
                seen_ids = set(self._matched_entries_cache_seen_ids)
                start_offset = self._matched_entries_cache_size
            else:
                entries = []
                seen_ids = set()
                start_offset = 0
            read_size = max(0, stat.st_size - start_offset)
            try:
                with self.index_path.open("rb") as f:
                    f.seek(start_offset)
                    chunk = f.read(read_size)
            except OSError:
                return list(entries)

            processed_size = start_offset
            for raw_segment in chunk.splitlines(keepends=True):
                line = raw_segment.rstrip(b"\r\n").decode(
                    "utf-8", errors="replace"
                ).strip()
                if not line:
                    processed_size += len(raw_segment)
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    if not raw_segment.endswith((b"\n", b"\r")):
                        break
                    processed_size += len(raw_segment)
                    continue
                entry = entry_with_inferred_kind(entry)
                if should_omit_entry_from_chat(entry):
                    processed_size += len(raw_segment)
                    continue
                if not self.matches(entry):
                    processed_size += len(raw_segment)
                    continue
                if agent_index_entry_omit_for_redacted(str(entry.get("message") or "")):
                    processed_size += len(raw_segment)
                    continue
                msg_id = str(entry.get("msg_id") or "").strip()
                if msg_id:
                    if msg_id in seen_ids:
                        processed_size += len(raw_segment)
                        continue
                    seen_ids.add(msg_id)
                entries.append(entry)
                processed_size += len(raw_segment)
            self._matched_entries_cache_sig = (
                current_sig if processed_size == stat.st_size else (processed_size, 0)
            )
            self._matched_entries_cache_size = processed_size
            self._matched_entries_cache_entries = entries
            self._matched_entries_cache_seen_ids = seen_ids
            return list(entries)

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

    def mark_session_activated(self) -> None:
        self.session_is_active = True
        try:
            pending_path = self.pending_launch_path()
            if pending_path.exists():
                pending_path.unlink()
        except Exception:
            pass

    def payload(
        self,
        limit_override: int | None = None,
        before_msg_id: str = "",
        around_msg_id: str = "",
        light_mode: bool = False,
    ) -> bytes:
        now = time.monotonic()
        if now - self._last_commit_announcement_check >= 2.0:
            self._last_commit_announcement_check = now
            self.ensure_commit_announcements()
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

    def caffeinate_status(self) -> dict:
        if self._caffeinate_proc is not None and self._caffeinate_proc.poll() is None:
            return {"active": True}
        self._caffeinate_proc = None
        try:
            result = subprocess.run(["pgrep", "-x", "caffeinate"], capture_output=True)
            if result.returncode == 0:
                return {"active": True}
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            pass
        return {"active": False}

    def caffeinate_toggle(self) -> dict:
        if self.caffeinate_status()["active"]:
            if self._caffeinate_proc is not None:
                self._caffeinate_proc.terminate()
                self._caffeinate_proc = None
            else:
                subprocess.run(["killall", "caffeinate"], capture_output=True, check=False)
            return {"active": False}
        self.ensure_caffeinate_active()
        return {"active": True}

    def ensure_caffeinate_active(self) -> None:
        if self.caffeinate_status()["active"]:
            return
        self._caffeinate_proc = subprocess.Popen(self._caffeinate_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def auto_mode_status(self) -> dict:
        return _auto_mode_status_impl(
            self,
            subprocess_module=subprocess,
            os_module=os,
            path_class=Path,
            logging_module=logging,
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
        return _resolve_target_agents_impl(
            self,
            target,
            resolve_target_agent_names_fn=resolve_target_agent_names,
        )

    def pane_id_for_agent(self, agent_name: str) -> str:
        return _pane_id_for_agent_impl(
            self,
            agent_name,
            subprocess_module=subprocess,
        )

    def pane_field(self, pane_id: str, field: str) -> str:
        return _pane_field_impl(self, pane_id, field, subprocess_module=subprocess)

    def _pane_prompt_ready(self, pane_id: str, agent_name: str) -> bool:
        return _pane_prompt_ready_impl(self, pane_id, agent_name)

    def _wait_for_agent_prompt(self, pane_id: str, agent_name: str, *, send_prompt_wait_seconds: float = _SEND_PROMPT_WAIT_SECONDS) -> bool:
        return _wait_for_agent_prompt_impl(
            self,
            pane_id,
            agent_name,
            send_prompt_wait_seconds=send_prompt_wait_seconds,
        )

    def _wait_for_send_slot(self, agent_name: str) -> None:
        _wait_for_send_slot_impl(
            self,
            agent_name,
            claude_send_cooldown_seconds=_CLAUDE_SEND_COOLDOWN_SECONDS,
        )

    def _mark_agent_sent(self, agent_name: str) -> None:
        _mark_agent_sent_impl(self, agent_name)

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
        return _launch_pending_session_impl(self, requested_targets)

    @staticmethod
    def _parse_pane_direct_command(message: str) -> dict | None:
        return _parse_pane_direct_command_impl(message)

    def _sync_codex_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        _sync_codex_assistant_messages_impl(
            self,
            agent,
            native_log_path,
            sync_bind_backfill_window_seconds=SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )

    def _sync_cursor_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        _sync_cursor_assistant_messages_impl(
            self,
            agent,
            native_log_path,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
        )

    def _sync_copilot_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        _sync_copilot_assistant_messages_impl(self, agent, native_log_path)

    def _sync_claude_assistant_messages(
        self,
        agent: str,
        native_log_path: str | None = None,
        *,
        workspace_hint: str | None = None,
    ) -> None:
        _sync_claude_assistant_messages_impl(
            self,
            agent,
            native_log_path,
            workspace_hint=workspace_hint,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
            sync_bind_backfill_window_seconds=SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )

    def _sync_qwen_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        _sync_qwen_assistant_messages_impl(
            self,
            agent,
            native_log_path,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
            sync_bind_backfill_window_seconds=SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )

    def _sync_gemini_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        _sync_gemini_assistant_messages_impl(
            self,
            agent,
            native_log_path,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
            sync_bind_backfill_window_seconds=SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )

    def _sync_opencode_assistant_messages(self, agent: str) -> None:
        _sync_opencode_assistant_messages_impl(
            self,
            agent,
            sync_bind_backfill_window_seconds=SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )

    def agent_statuses(self) -> dict[str, str]:
        return _refresh_native_log_idle_running_statuses_impl(self)

    def agent_runtime_state(self) -> dict[str, dict]:
        return _idle_running_display_for_api_impl(self._idle_running_display_by_agent)

    def trace_content(self, agent: str, *, tail_lines: int | None = None) -> str:
        return _trace_content_impl(self, agent, tail_lines=tail_lines)
