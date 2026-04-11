from __future__ import annotations
import fcntl
import logging

import json
import os
import subprocess
import time
import uuid
from collections import deque
from datetime import datetime as dt_datetime
from pathlib import Path
from urllib.parse import quote

from .agent_registry import generate_agent_message_selectors
from .chat_agent_lifecycle_core import (
    agent_launch_cmd as _agent_launch_cmd_impl,
    agent_resume_cmd as _agent_resume_cmd_impl,
    resolve_agent_executable as _resolve_agent_executable_impl,
    restart_agent_pane as _restart_agent_pane_impl,
    resume_agent_pane as _resume_agent_pane_impl,
)
from .chat_delivery_core import (
    mark_agent_sent as _mark_agent_sent_impl,
    parse_pane_direct_command as _parse_pane_direct_command_impl,
    pane_has_claude_trust_prompt as _pane_has_claude_trust_prompt_impl,
    pane_has_cursor_trust_prompt as _pane_has_cursor_trust_prompt_impl,
    pane_has_escape_cancel_prompt as _pane_has_escape_cancel_prompt_impl,
    pane_has_gemini_trust_prompt as _pane_has_gemini_trust_prompt_impl,
    pane_prompt_ready as _pane_prompt_ready_impl,
    send_message as _send_message_impl,
    wait_for_agent_prompt as _wait_for_agent_prompt_impl,
    wait_for_send_slot as _wait_for_send_slot_impl,
)
from .chat_entry_write_core import (
    append_system_entry as _append_system_entry_impl,
    load_thinking_totals as _load_thinking_totals_impl,
)
from .chat_entries_core import entry_window as _entry_window_impl
from .chat_font_style_core import (
    chat_font_settings_inline_style as _chat_font_settings_inline_style_impl,
    font_family_stack as _font_family_stack_impl,
)
from .chat_commit_core import (
    commit_state_payload as _commit_state_payload_impl,
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
from .chat_payload_core import (
    attachment_paths as payload_attachment_paths,
    build_payload_document,
    encode_payload_document,
    summarize_light_entry,
)
from .chat_runtime_parse_core import (
    _get_process_tree as _get_process_tree_impl,
    _parse_cursor_jsonl_runtime as _parse_cursor_jsonl_runtime_impl,
    _parse_native_claude_log as _parse_native_claude_log_impl,
    _parse_native_codex_log as _parse_native_codex_log_impl,
    _parse_native_gemini_log as _parse_native_gemini_log_impl,
    _pane_runtime_new_events as _pane_runtime_new_events_impl,
    _resolve_native_log_file as _resolve_native_log_file_impl,
    _runtime_apply_patch_ops as _runtime_apply_patch_ops_impl,
    _runtime_tool_events as _runtime_tool_events_impl,
    _runtime_tool_summary as _runtime_tool_summary_impl,
)
from .chat_style_core import (
    BOLD_MODE_VIEWPORT_MAX_PX,
    _agent_markdown_selectors as _agent_markdown_selectors_impl,
    _bh_agent_detail_selectors as _bh_agent_detail_selectors_impl,
    _chat_bold_mode_rules_block as _chat_bold_mode_rules_block_impl,
)
from .chat_thinking_kind_core import entry_with_inferred_kind, should_omit_entry_from_chat
from .chat_sync_cursor_core import (
    NativeLogCursor,
    OpenCodeCursor,
    _advance_native_cursor,
    _agent_base_name,
    _coerce_native_cursor,
    _coerce_opencode_cursor,
    _dedup_cursor_claims,
    _load_cursor_dict,
    _load_opencode_dict,
    _native_path_claim_key,
    _pick_latest_unclaimed,
    _pick_latest_unclaimed_for_agent,
)
from .chat_sync_providers_core import (
    sync_claude_assistant_messages as _sync_claude_assistant_messages_impl,
    sync_codex_assistant_messages as _sync_codex_assistant_messages_impl,
    sync_copilot_assistant_messages as _sync_copilot_assistant_messages_impl,
    sync_cursor_assistant_messages as _sync_cursor_assistant_messages_impl,
    sync_cursor_storedb_assistant_messages as _sync_cursor_storedb_assistant_messages_impl,
    sync_gemini_assistant_messages as _sync_gemini_assistant_messages_impl,
    sync_opencode_assistant_messages as _sync_opencode_assistant_messages_impl,
    sync_qwen_assistant_messages as _sync_qwen_assistant_messages_impl,
)
from .chat_sync_state_core import (
    apply_recent_targeted_claim_handoffs as _apply_recent_targeted_claim_handoffs_impl,
    codex_rollout_candidates as _codex_rollout_candidates_impl,
    collect_global_native_log_claims as _collect_global_native_log_claims_impl,
    cursor_storedb_candidates as _cursor_storedb_candidates_impl,
    cursor_transcript_roots as _cursor_transcript_roots_impl,
    first_seen_for_agent as _first_seen_for_agent_impl,
    handoff_shared_sync_claim as _handoff_shared_sync_claim_impl,
    has_outbound_target_for_agent as _has_outbound_target_for_agent_impl,
    is_globally_claimed_path as _is_globally_claimed_path_impl,
    load_sync_state as _load_sync_state_impl,
    maybe_heartbeat_sync_state as _maybe_heartbeat_sync_state_impl,
    native_cursor_map_for_agent as _native_cursor_map_for_agent_impl,
    pick_codex_rollout_for_agent as _pick_codex_rollout_for_agent_impl,
    prune_sync_claims_to_active_agents as _prune_sync_claims_to_active_agents_impl,
    recent_index_entries as _recent_index_entries_impl,
    save_sync_state as _save_sync_state_impl,
    should_stick_to_existing_cursor as _should_stick_to_existing_cursor_impl,
    sync_cursor_status as _sync_cursor_status_impl,
    workspace_aliases as _workspace_aliases_impl,
    workspace_git_root as _workspace_git_root_impl,
)
from .chat_session_runtime_core import (
    active_agents as _active_agents_impl,
    agents_from_pane_env as _agents_from_pane_env_impl,
    auto_mode_status as _auto_mode_status_impl,
    pane_id_for_agent as _pane_id_for_agent_impl,
    resolve_target_agents as _resolve_target_agents_impl,
)
from .chat_status_core import (
    agent_runtime_state as _agent_runtime_state_impl,
    agent_statuses as _agent_statuses_impl,
    parse_opencode_runtime as _parse_opencode_runtime_impl,
)
from .chat_trace_core import trace_content as _trace_content_impl
from .instance_core import agents_from_tmux_env_output
from .instance_core import resolve_target_agents as resolve_target_agent_names
from .jsonl_append import append_jsonl_entry
from .redacted_placeholder import agent_index_entry_omit_for_redacted, normalize_cursor_plaintext_for_index
from .state_core import load_hub_settings as load_shared_hub_settings
from .state_core import load_session_thinking_totals as load_shared_session_thinking_totals

_FIRST_SEEN_GRACE_SECONDS = 120.0
_GLOBAL_LOG_CLAIM_TTL_SECONDS = 180.0
_GLOBAL_LOG_CLAIM_REFRESH_SECONDS = 5.0
_CLAUDE_GIT_ROOT_FALLBACK_DELAY_SECONDS = 15.0
_CLAUDE_BIND_BACKFILL_WINDOW_SECONDS = 45.0
_SYNC_BIND_BACKFILL_WINDOW_SECONDS = 45.0
_SEND_PROMPT_WAIT_SECONDS = 6.0
_CLAUDE_SEND_COOLDOWN_SECONDS = 8.0


def _get_process_tree(pid: str) -> set[str]:
    return _get_process_tree_impl(pid)

def _resolve_native_log_file(pane_pid: str, log_pattern: str, base_name: str = "") -> str | None:
    return _resolve_native_log_file_impl(pane_pid, log_pattern, base_name)

def _parse_native_codex_log(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    return _parse_native_codex_log_impl(filepath, limit, workspace)


def _parse_native_gemini_log(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    return _parse_native_gemini_log_impl(filepath, limit, workspace)


def _runtime_tool_summary(arguments: object, workspace: str = "") -> str:
    return _runtime_tool_summary_impl(arguments, workspace=workspace)


def _runtime_apply_patch_ops(arguments: object) -> list[tuple[str, str]]:
    return _runtime_apply_patch_ops_impl(arguments)


def _runtime_tool_events(name: object, arguments: object, workspace: str = "") -> list[dict]:
    return _runtime_tool_events_impl(name, arguments, workspace=workspace)


def _parse_cursor_jsonl_runtime(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    return _parse_cursor_jsonl_runtime_impl(filepath, limit, workspace)


def _parse_native_claude_log(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    return _parse_native_claude_log_impl(filepath, limit, workspace)


def _pane_runtime_new_events(previous: list[dict], current: list[dict]) -> list[dict]:
    return _pane_runtime_new_events_impl(previous, current)


def _agent_markdown_selectors(*suffixes: str, prefix: str = "") -> str:
    return _agent_markdown_selectors_impl(*suffixes, prefix=prefix)

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
        self.sync_state_path = self.index_path.parent / ".agent-index-sync-state.json"
        self.sync_lock_path = self.index_path.parent / ".agent-index-sync.lock"
        self.tmux_prefix = ["tmux"]
        if self.tmux_socket:
            if "/" in self.tmux_socket:
                self.tmux_prefix.extend(["-S", self.tmux_socket])
            else:
                self.tmux_prefix.extend(["-L", self.tmux_socket])
        self._caffeinate_proc = None
        self._pane_snapshots = {}
        self._pane_last_change = {}
        self._pane_runtime_matches = {}
        self._pane_runtime_state = {}
        # pane_id -> (pane_pid, native_log_path)
        self._pane_native_log_paths: dict[str, tuple[str, str]] = {}
        self._pane_runtime_event_seq = 0
        self._global_log_claims: dict[str, tuple[str, str]] = {}
        self._global_log_claims_fetched_at = 0.0
        self._last_sync_state_heartbeat = 0.0
        self._workspace_git_root_cache: dict[str, str] = {}
        self._claude_bind_backfill_until: dict[str, float] = {}
        self._agent_last_send_ts: dict[str, float] = {}
        
        # Persistent sync state — per-agent (path, offset) cursors into each
        # CLI's native log file. Historic format used bare-int offsets; those
        # are discarded on load so we re-anchor rather than reading junk from
        # a different file that happens to be at the same byte position.
        self._sync_state = self.load_sync_state()
        self._codex_cursors: dict[str, NativeLogCursor] = _load_cursor_dict(self._sync_state.get("codex_cursors"))
        self._cursor_cursors: dict[str, NativeLogCursor] = _load_cursor_dict(self._sync_state.get("cursor_cursors"))
        self._copilot_cursors: dict[str, NativeLogCursor] = _load_cursor_dict(self._sync_state.get("copilot_cursors"))
        self._qwen_cursors: dict[str, NativeLogCursor] = _load_cursor_dict(self._sync_state.get("qwen_cursors"))
        self._claude_cursors: dict[str, NativeLogCursor] = _load_cursor_dict(self._sync_state.get("claude_cursors"))
        self._gemini_cursors: dict[str, NativeLogCursor] = _load_cursor_dict(self._sync_state.get("gemini_cursors"))
        self._opencode_cursors: dict[str, OpenCodeCursor] = _load_opencode_dict(self._sync_state.get("opencode_cursors"))
        # Backward-compat: migrate the previous ``cursor_state`` schema (which
        # already stored path+offset pairs) into the new _cursor_cursors dict.
        if not self._cursor_cursors:
            self._cursor_cursors = _load_cursor_dict(self._sync_state.get("cursor_state"))
        if not self._opencode_cursors:
            self._opencode_cursors = _load_opencode_dict(self._sync_state.get("opencode_state"))
        # Remove accidental duplicate claims (two agents pointing at the
        # same file). Stale state from earlier versions of this runtime
        # contained these and caused one agent's messages to be attributed
        # to the other. Keep the alphabetically-first claimant and drop
        # the rest; the displaced agent will re-claim cleanly via the
        # first-seen gate on its next sync tick.
        self._codex_cursors = _dedup_cursor_claims(self._codex_cursors)
        self._cursor_cursors = _dedup_cursor_claims(self._cursor_cursors)
        self._copilot_cursors = _dedup_cursor_claims(self._copilot_cursors)
        self._qwen_cursors = _dedup_cursor_claims(self._qwen_cursors)
        self._claude_cursors = _dedup_cursor_claims(self._claude_cursors)
        self._gemini_cursors = _dedup_cursor_claims(self._gemini_cursors)
        # Per-agent timestamps of when this runtime first observed each
        # agent. Used as the ``min_mtime`` gate when picking a log file so
        # we don't silently latch onto a pre-existing file from before the
        # agent's CLI had a chance to write anything.
        self._agent_first_seen_ts: dict[str, float] = {}
        raw_first_seen = self._sync_state.get("agent_first_seen_ts")
        if isinstance(raw_first_seen, dict):
            for _k, _v in raw_first_seen.items():
                if isinstance(_k, str) and isinstance(_v, (int, float)):
                    self._agent_first_seen_ts[_k] = float(_v)
        
        self._synced_msg_ids: set[str] = set()  # guard against in-session duplicates
        # Pre-load synced msg_ids from persisted sync state first (survives
        # restarts even if the JSONL index hasn't been flushed yet).
        _persisted_ids = self._sync_state.get("synced_msg_ids")
        if isinstance(_persisted_ids, list):
            for _mid in _persisted_ids:
                if isinstance(_mid, str) and _mid.strip():
                    self._synced_msg_ids.add(_mid.strip())
        # Then pre-load from JSONL so syncers don't re-ingest existing
        # entries after a restart, and so multiple chat_server instances on the
        # same session won't duplicate each other.
        _preload_prefixes = ("gemini", "codex", "cursor", "claude", "copilot", "qwen", "opencode")
        try:
            if self.index_path.exists():
                with open(self.index_path, "r", encoding="utf-8") as _f:
                    for _line in _f:
                        _line = _line.strip()
                        if not _line:
                            continue
                        try:
                            _obj = json.loads(_line)
                            _sender = str(_obj.get("sender") or "")
                            _agent = str(_obj.get("agent") or "")
                            if _sender.startswith(_preload_prefixes) or _agent:
                                _mid = str(_obj.get("msg_id") or "").strip()
                                if _mid:
                                    self._synced_msg_ids.add(_mid)
                        except:
                            pass
        except Exception:
            pass
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

    def _collect_global_native_log_claims(self) -> dict[str, tuple[str, str]]:
        return _collect_global_native_log_claims_impl(
            self,
            global_log_claim_refresh_seconds=_GLOBAL_LOG_CLAIM_REFRESH_SECONDS,
            global_log_claim_ttl_seconds=_GLOBAL_LOG_CLAIM_TTL_SECONDS,
            subprocess_module=subprocess,
            time_module=time,
            path_class=Path,
        )

    def _is_globally_claimed_path(self, path: str) -> bool:
        return _is_globally_claimed_path_impl(self, path)

    def _first_seen_for_agent(self, agent: str) -> float:
        return _first_seen_for_agent_impl(self, agent, time_module=time)

    def _should_stick_to_existing_cursor(self, agent: str) -> bool:
        return _should_stick_to_existing_cursor_impl(self, agent)

    def _has_outbound_target_for_agent(self, agent: str, *, tail_bytes: int = 65536) -> bool:
        return _has_outbound_target_for_agent_impl(self, agent, tail_bytes=tail_bytes)

    def _workspace_git_root(self, workspace: str) -> str:
        return _workspace_git_root_impl(
            self,
            workspace,
            subprocess_module=subprocess,
            path_class=Path,
        )

    def _workspace_aliases(self, workspace: str) -> list[str]:
        return _workspace_aliases_impl(self, workspace, path_class=Path)

    def _cursor_transcript_roots(self, workspace: str) -> list[Path]:
        return _cursor_transcript_roots_impl(self, workspace, path_class=Path)

    def _cursor_storedb_candidates(self, workspace: str) -> list[Path]:
        return _cursor_storedb_candidates_impl(self, workspace, path_class=Path)

    def _codex_rollout_candidates(self, workspace: str) -> list[Path]:
        return _codex_rollout_candidates_impl(self, workspace, path_class=Path)

    def _pick_codex_rollout_for_agent(self, agent: str) -> Path | None:
        return _pick_codex_rollout_for_agent_impl(
            self,
            agent,
            first_seen_grace_seconds=_FIRST_SEEN_GRACE_SECONDS,
        )

    def maybe_heartbeat_sync_state(self, *, interval_seconds: float = 30.0) -> None:
        _maybe_heartbeat_sync_state_impl(
            self,
            interval_seconds=interval_seconds,
            time_module=time,
        )

    def prune_sync_claims_to_active_agents(self, active_agents: list[str]) -> bool:
        return _prune_sync_claims_to_active_agents_impl(self, active_agents)

    def _recent_index_entries(self, *, max_lines: int = 160) -> list[dict]:
        return _recent_index_entries_impl(self, max_lines=max_lines)

    def apply_recent_targeted_claim_handoffs(
        self,
        active_agents: list[str],
        *,
        lookback_seconds: float = 45.0,
    ) -> bool:
        return _apply_recent_targeted_claim_handoffs_impl(
            self,
            active_agents,
            lookback_seconds=lookback_seconds,
            time_module=time,
            datetime_class=dt_datetime,
        )

    def save_sync_state(self) -> None:
        _save_sync_state_impl(self, time_module=time)

    def sync_cursor_status(self) -> list[dict]:
        return _sync_cursor_status_impl(self, os_module=os)

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


    def load_thinking_totals(self) -> dict[str, int]:
        return _load_thinking_totals_impl(
            self,
            load_shared_session_thinking_totals_fn=load_shared_session_thinking_totals,
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

    @staticmethod
    def _commit_state_payload(commit: dict) -> dict:
        return _commit_state_payload_impl(commit)

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
        entries = []
        seen_ids: set[str] = set()
        with self.index_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry = entry_with_inferred_kind(entry)
                if should_omit_entry_from_chat(entry):
                    continue
                if not self.matches(entry):
                    continue
                if agent_index_entry_omit_for_redacted(str(entry.get("message") or "")):
                    continue
                msg_id = str(entry.get("msg_id") or "").strip()
                if msg_id:
                    if msg_id in seen_ids:
                        continue
                    seen_ids.add(msg_id)
                entries.append(entry)
        return entries

    def _entry_window(
        self,
        *,
        limit_override: int | None = None,
        before_msg_id: str = "",
        around_msg_id: str = "",
    ) -> tuple[list[dict], bool]:
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
        self.ensure_commit_announcements()
        meta = self.session_metadata()
        entries, has_older = self._entry_window(
            limit_override=limit_override,
            before_msg_id=before_msg_id,
            around_msg_id=around_msg_id,
        )
        if light_mode:
            entries = [self._light_entry(entry) for entry in entries]
        payload_doc = build_payload_document(
            meta=meta,
            filter_agent=self.filter_agent,
            follow_mode=self.follow_mode,
            targets=self.active_agents(),
            has_older=has_older,
            light_mode=bool(light_mode),
            entries=entries,
        )
        return encode_payload_document(payload_doc)

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

    def save_logs(self, *, reason: str = "autosave"):
        """Run multiagent save to capture panes to workspace/central logs (overwrites)."""
        reason = (reason or "autosave").strip()[:64] or "autosave"
        if not self.session_is_active:
            return 409, {"ok": False, "error": "session inactive", "reason": reason}
        bin_dir = Path(self.agent_send_path).parent.resolve()
        multiagent = bin_dir / "multiagent"
        if not multiagent.is_file():
            return 500, {"ok": False, "error": "multiagent not found", "reason": reason}
        env = os.environ.copy()
        env.pop("MULTIAGENT_AGENT_NAME", None)
        env["MULTIAGENT_SESSION"] = self.session_name
        env["MULTIAGENT_WORKSPACE"] = self.workspace
        env["MULTIAGENT_BIN_DIR"] = str(bin_dir)
        if self.tmux_socket:
            env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
        if self.log_dir:
            env["MULTIAGENT_LOG_DIR"] = self.log_dir
        try:
            proc = subprocess.run(
                [str(multiagent), "save", "--session", self.session_name],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
                cwd=self.workspace or None,
                check=False,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return 500, {"ok": False, "error": str(exc), "reason": reason}
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            return 500, {"ok": False, "error": err, "reason": reason}
        return 200, {"ok": True, "reason": reason}

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

    def _pane_prompt_ready(self, pane_id: str, agent_name: str) -> bool:
        return _pane_prompt_ready_impl(self, pane_id, agent_name)

    def _pane_has_escape_cancel_prompt(self, pane_id: str, agent_name: str) -> bool:
        return _pane_has_escape_cancel_prompt_impl(self, pane_id, agent_name)

    def _pane_has_claude_trust_prompt(self, pane_id: str, agent_name: str) -> bool:
        return _pane_has_claude_trust_prompt_impl(self, pane_id, agent_name)

    def _pane_has_gemini_trust_prompt(self, pane_id: str, agent_name: str) -> bool:
        return _pane_has_gemini_trust_prompt_impl(self, pane_id, agent_name)

    def _pane_has_cursor_trust_prompt(self, pane_id: str, agent_name: str) -> bool:
        return _pane_has_cursor_trust_prompt_impl(self, pane_id, agent_name)

    def _wait_for_agent_prompt(self, pane_id: str, agent_name: str) -> bool:
        return _wait_for_agent_prompt_impl(
            self,
            pane_id,
            agent_name,
            send_prompt_wait_seconds=_SEND_PROMPT_WAIT_SECONDS,
        )

    def _wait_for_send_slot(self, agent_name: str) -> None:
        _wait_for_send_slot_impl(
            self,
            agent_name,
            claude_send_cooldown_seconds=_CLAUDE_SEND_COOLDOWN_SECONDS,
        )

    def _mark_agent_sent(self, agent_name: str) -> None:
        _mark_agent_sent_impl(self, agent_name)

    def _native_cursor_map_for_agent(self, agent_name: str) -> dict[str, NativeLogCursor] | None:
        return _native_cursor_map_for_agent_impl(self, agent_name)

    def _handoff_shared_sync_claim(self, agent_name: str) -> bool:
        return _handoff_shared_sync_claim_impl(self, agent_name)

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

    @staticmethod
    def _parse_pane_direct_command(message: str) -> dict | None:
        return _parse_pane_direct_command_impl(message)

    def _sync_codex_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        _sync_codex_assistant_messages_impl(
            self,
            agent,
            native_log_path,
            sync_bind_backfill_window_seconds=_SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )

    def _sync_cursor_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        _sync_cursor_assistant_messages_impl(
            self,
            agent,
            native_log_path,
            first_seen_grace_seconds=_FIRST_SEEN_GRACE_SECONDS,
        )

    def _sync_cursor_storedb_assistant_messages(self, agent: str, store_db_path: str) -> None:
        _sync_cursor_storedb_assistant_messages_impl(self, agent, store_db_path)

    def _sync_copilot_assistant_messages(self, agent: str, native_log_path: str) -> None:
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
            first_seen_grace_seconds=_FIRST_SEEN_GRACE_SECONDS,
            sync_bind_backfill_window_seconds=_SYNC_BIND_BACKFILL_WINDOW_SECONDS,
            claude_git_root_fallback_delay_seconds=_CLAUDE_GIT_ROOT_FALLBACK_DELAY_SECONDS,
            claude_bind_backfill_window_seconds=_CLAUDE_BIND_BACKFILL_WINDOW_SECONDS,
        )

    def _sync_qwen_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        _sync_qwen_assistant_messages_impl(
            self,
            agent,
            native_log_path,
            first_seen_grace_seconds=_FIRST_SEEN_GRACE_SECONDS,
            sync_bind_backfill_window_seconds=_SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )

    def _sync_gemini_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        _sync_gemini_assistant_messages_impl(
            self,
            agent,
            native_log_path,
            first_seen_grace_seconds=_FIRST_SEEN_GRACE_SECONDS,
            sync_bind_backfill_window_seconds=_SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )

    def _sync_opencode_assistant_messages(self, agent: str) -> None:
        _sync_opencode_assistant_messages_impl(
            self,
            agent,
            sync_bind_backfill_window_seconds=_SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )

    def agent_statuses(self) -> dict[str, str]:
        return _agent_statuses_impl(self)

    def agent_runtime_state(self) -> dict[str, dict]:
        return _agent_runtime_state_impl(self)

    def trace_content(self, agent: str, *, tail_lines: int | None = None) -> str:
        return _trace_content_impl(self, agent, tail_lines=tail_lines)
