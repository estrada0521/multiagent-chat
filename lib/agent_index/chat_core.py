from __future__ import annotations
import fcntl
import hashlib
import logging

import json
import os
import re
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
    pane_has_claude_trust_prompt as _pane_has_claude_trust_prompt_impl,
    pane_has_cursor_trust_prompt as _pane_has_cursor_trust_prompt_impl,
    pane_has_escape_cancel_prompt as _pane_has_escape_cancel_prompt_impl,
    pane_has_gemini_trust_prompt as _pane_has_gemini_trust_prompt_impl,
    pane_prompt_ready as _pane_prompt_ready_impl,
    wait_for_agent_prompt as _wait_for_agent_prompt_impl,
    wait_for_send_slot as _wait_for_send_slot_impl,
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
from .chat_thinking_kind_core import entry_with_inferred_kind
from .chat_sync_cursor_core import (
    NativeLogCursor,
    OpenCodeCursor,
    _advance_native_cursor,
    _agent_base_name,
    _agent_instance_number,
    _coerce_native_cursor,
    _coerce_opencode_cursor,
    _cursor_dict_to_json,
    _dedup_cursor_claims,
    _load_cursor_dict,
    _load_opencode_dict,
    _native_path_claim_key,
    _opencode_dict_to_json,
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
from .chat_status_core import (
    agent_runtime_state as _agent_runtime_state_impl,
    agent_statuses as _agent_statuses_impl,
    parse_opencode_runtime as _parse_opencode_runtime_impl,
    trace_content as _trace_content_impl,
)
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

def _parse_native_codex_log(filepath: str, limit: int) -> list[dict] | None:
    return _parse_native_codex_log_impl(filepath, limit)


def _runtime_tool_summary(arguments: object) -> str:
    return _runtime_tool_summary_impl(arguments)


def _runtime_apply_patch_ops(arguments: object) -> list[tuple[str, str]]:
    return _runtime_apply_patch_ops_impl(arguments)


def _runtime_tool_events(name: object, arguments: object) -> list[dict]:
    return _runtime_tool_events_impl(name, arguments)


def _parse_cursor_jsonl_runtime(filepath: str, limit: int) -> list[dict] | None:
    return _parse_cursor_jsonl_runtime_impl(filepath, limit)


def _parse_native_claude_log(filepath: str, limit: int) -> list[dict] | None:
    return _parse_native_claude_log_impl(filepath, limit)

def _parse_native_gemini_log(session_name: str, repo_root: Path | str, agent: str, limit: int) -> list[dict] | None:
    return _parse_native_gemini_log_impl(session_name, repo_root, agent, limit)



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
        self.limit = int(limit)
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
        # Pre-load synced msg_ids from JSONL so syncers don't re-ingest existing
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
        saved_limit = settings.get("message_limit")
        if saved_limit is not None and int(saved_limit) > 0:
            self.limit = int(saved_limit)
        if bool(settings.get("chat_awake", False)):
            self.ensure_caffeinate_active()

    def load_chat_settings(self) -> dict:
        cap = self.limit if self.limit > 0 else 2000
        return load_shared_hub_settings(self.repo_root, message_limit_cap=cap)

    def load_sync_state(self) -> dict:
        if not self.sync_state_path.exists():
            return {}
        try:
            with self.sync_state_path.open("r", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                raw = handle.read().strip()
                if not raw:
                    return {}
                return json.loads(raw)
        except Exception as exc:
            logging.error(f"Failed to load sync state: {exc}")
            return {}

    def _collect_global_native_log_claims(self) -> dict[str, tuple[str, str]]:
        now = time.time()
        if now - self._global_log_claims_fetched_at < _GLOBAL_LOG_CLAIM_REFRESH_SECONDS:
            return self._global_log_claims

        claims: dict[str, tuple[str, str]] = {}
        base = Path(self.log_dir)
        if not base.exists():
            self._global_log_claims = claims
            self._global_log_claims_fetched_at = now
            return claims

        active_sessions: set[str] | None = None
        try:
            sessions_res = subprocess.run(
                [*self.tmux_prefix, "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if sessions_res.returncode == 0:
                active_sessions = {
                    line.strip()
                    for line in (sessions_res.stdout or "").splitlines()
                    if line.strip()
                }
        except Exception:
            active_sessions = None

        cursor_paths = (
            ("codex_cursors", "codex"),
            ("cursor_cursors", "cursor"),
            ("copilot_cursors", "copilot"),
            ("qwen_cursors", "qwen"),
            ("claude_cursors", "claude"),
            ("gemini_cursors", "gemini"),
        )
        for state_path in base.glob("*/.agent-index-sync-state.json"):
            try:
                session_name = state_path.parent.name
                if session_name == self.session_name:
                    continue
                if active_sessions is not None and session_name not in active_sessions:
                    continue
                if now - state_path.stat().st_mtime > _GLOBAL_LOG_CLAIM_TTL_SECONDS:
                    continue
                raw = json.loads(state_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            if not isinstance(raw, dict):
                continue
            for key, _type in cursor_paths:
                value = raw.get(key)
                if not isinstance(value, dict):
                    continue
                for claimant_agent, cursor in value.items():
                    if not isinstance(claimant_agent, str):
                        continue
                    cursor_path = cursor[0] if isinstance(cursor, (list, tuple)) else ""
                    if not isinstance(cursor_path, str) or not cursor_path:
                        continue
                    claims[str(Path(cursor_path))] = (session_name, claimant_agent)

        self._global_log_claims = claims
        self._global_log_claims_fetched_at = now
        return claims

    def _is_globally_claimed_path(self, path: str) -> bool:
        candidate_key = _native_path_claim_key(path)
        for claimed_path in self._collect_global_native_log_claims().keys():
            if _native_path_claim_key(claimed_path) == candidate_key:
                return True
        return False

    def _first_seen_for_agent(self, agent: str) -> float:
        """Return (and lazily initialize) the timestamp when this runtime first observed *agent*.

        The value is used as a ``min_mtime`` gate in ``_pick_latest_unclaimed``
        so that pre-existing log files (which may belong to a different CLI
        instance) are not silently claimed before the agent's CLI has had a
        chance to write anything new.
        """
        ts = self._agent_first_seen_ts.get(agent)
        if ts is None:
            ts = time.time()
            self._agent_first_seen_ts[agent] = ts
        return ts

    def _should_stick_to_existing_cursor(self, agent: str) -> bool:
        base = _agent_base_name(agent)
        peers = {
            name
            for name in self._agent_first_seen_ts.keys()
            if _agent_base_name(name) == base and name != agent
        }
        if peers:
            return True
        try:
            for name in self.active_agents():
                if _agent_base_name(name) == base and name != agent:
                    return True
        except Exception:
            pass
        return False

    def _has_outbound_target_for_agent(self, agent: str, *, tail_bytes: int = 65536) -> bool:
        if not self.index_path.exists():
            return False
        try:
            with self.index_path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                start = max(0, size - max(1024, int(tail_bytes)))
                handle.seek(start)
                raw = handle.read()
            if start > 0:
                nl = raw.find(b"\n")
                if nl != -1:
                    raw = raw[nl + 1 :]
            text = raw.decode("utf-8", errors="ignore")
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                targets = entry.get("targets")
                if not isinstance(targets, list):
                    continue
                if agent not in [str(t).strip() for t in targets]:
                    continue
                sender = str(entry.get("sender") or "").strip()
                if sender and sender != agent:
                    return True
        except Exception:
            return False
        return False

    def _workspace_git_root(self, workspace: str) -> str:
        cached = self._workspace_git_root_cache.get(workspace)
        if cached is not None:
            return cached
        git_root = ""
        try:
            res = subprocess.run(
                ["git", "-C", workspace, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if res.returncode == 0:
                candidate = (res.stdout or "").strip()
                if candidate:
                    git_root = str(Path(candidate).resolve())
        except Exception:
            git_root = ""
        self._workspace_git_root_cache[workspace] = git_root
        return git_root

    def _workspace_aliases(self, workspace: str) -> list[str]:
        aliases: list[str] = []
        seen: set[str] = set()

        def _push_alias(value: str) -> None:
            item = str(value or "").strip()
            if not item or item in seen:
                return
            seen.add(item)
            aliases.append(item)

        def _tmp_aliases(value: str) -> list[str]:
            item = str(value or "").strip()
            if not item:
                return []
            if item == "/tmp" or item.startswith("/tmp/"):
                return [item, f"/private{item}"]
            if item == "/private/tmp" or item.startswith("/private/tmp/"):
                return [item, item[len("/private"):]]
            return [item]

        for candidate in (workspace, self._workspace_git_root(workspace)):
            value = str(candidate or "").strip()
            if not value:
                continue
            variants = [value]
            try:
                variants.append(str(Path(value).resolve()))
            except Exception:
                pass
            for variant in variants:
                for alias in _tmp_aliases(variant):
                    _push_alias(alias)
        return aliases

    def _cursor_transcript_roots(self, workspace: str) -> list[Path]:
        slug_candidates: list[str] = []
        seen_slugs: set[str] = set()

        def _append_slug_from_path(path_value: str) -> None:
            slug = str(path_value).replace("/", "-").lstrip("-")
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                slug_candidates.append(slug)

        for path_value in self._workspace_aliases(workspace):
            _append_slug_from_path(path_value)

        roots: list[Path] = []
        for slug in slug_candidates:
            root = Path.home() / ".cursor" / "projects" / slug / "agent-transcripts"
            if root.exists():
                roots.append(root)
        return roots

    def _cursor_storedb_candidates(self, workspace: str) -> list[Path]:
        candidates: list[Path] = []
        seen: set[Path] = set()
        for path_value in self._workspace_aliases(workspace):
            key = hashlib.md5(path_value.encode("utf-8")).hexdigest()
            chat_root = Path.home() / ".cursor" / "chats" / key
            if not chat_root.exists():
                continue
            for store_db in chat_root.glob("*/store.db"):
                resolved = store_db.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                candidates.append(resolved)
        return candidates

    def _codex_rollout_candidates(self, workspace: str) -> list[Path]:
        workspace_text = str(workspace or "").strip()
        workspace_aliases: set[str] = set()
        if workspace_text:
            workspace_aliases.add(workspace_text)
            try:
                workspace_aliases.add(str(Path(workspace_text).resolve()))
            except Exception:
                pass
        if not workspace_aliases:
            return []
        sessions_root = Path.home() / ".codex" / "sessions"
        if not sessions_root.exists():
            return []

        ranked: list[tuple[float, Path]] = []
        for candidate in sessions_root.glob("*/*/*/rollout-*.jsonl"):
            try:
                ranked.append((candidate.stat().st_mtime, candidate))
            except OSError:
                continue
        ranked.sort(key=lambda item: item[0], reverse=True)

        candidates: list[Path] = []
        for _mtime, candidate in ranked[:200]:
            try:
                with candidate.open("r", encoding="utf-8", errors="replace") as handle:
                    first_line = handle.readline().strip()
                if not first_line:
                    continue
                payload = json.loads(first_line)
            except Exception:
                continue
            if payload.get("type") != "session_meta":
                continue
            meta = payload.get("payload") if isinstance(payload, dict) else {}
            cwd = str((meta or {}).get("cwd") or "").strip()
            if not cwd:
                continue
            resolved_candidates = {cwd}
            try:
                resolved_candidates.add(str(Path(cwd).resolve()))
            except Exception:
                pass
            if resolved_candidates.isdisjoint(workspace_aliases):
                continue
            candidates.append(candidate)
        return candidates

    def _pick_codex_rollout_for_agent(self, agent: str) -> Path | None:
        workspace = str(self.workspace or "").strip()
        if not workspace:
            return None
        candidates = self._codex_rollout_candidates(workspace)
        if not candidates:
            return None
        min_mtime = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
        return _pick_latest_unclaimed_for_agent(
            candidates,
            self._codex_cursors,
            agent,
            min_mtime=min_mtime,
            exclude_paths=set(self._collect_global_native_log_claims().keys()),
        )

    def maybe_heartbeat_sync_state(self, *, interval_seconds: float = 30.0) -> None:
        interval = max(1.0, float(interval_seconds))
        now = time.time()
        if now - self._last_sync_state_heartbeat < interval:
            return
        self.save_sync_state()

    def prune_sync_claims_to_active_agents(self, active_agents: list[str]) -> bool:
        """Drop stale per-agent sync cursors for agents no longer active.

        Session topology can change over time (add/remove/renumber instances).
        If stale cursor claims remain for removed agents, claim-aware file
        selection may exclude the active agent from the newest transcript.
        """
        active = {str(agent).strip() for agent in (active_agents or []) if str(agent).strip()}
        if not active:
            return False

        changed = False

        active_by_base: dict[str, list[str]] = {}
        for agent in sorted(
            active,
            key=lambda name: (
                _agent_base_name(name),
                _agent_instance_number(name) if _agent_instance_number(name) is not None else 0,
            ),
        ):
            active_by_base.setdefault(_agent_base_name(agent), []).append(agent)

        def _migrate_aliases(mapping: dict) -> None:
            nonlocal changed
            if not mapping:
                return
            for base, active_names in active_by_base.items():
                if not active_names:
                    continue

                # When a previously single instance gets renumbered after Add Agent
                # (e.g. claude -> claude-1), preserve the old claim ownership.
                primary_numbered = f"{base}-1"
                if (
                    primary_numbered in active
                    and primary_numbered not in mapping
                    and base in mapping
                    and base not in active
                ):
                    mapping[primary_numbered] = mapping.pop(base)
                    changed = True

                # When topology collapses back to a single unsuffixed instance
                # (e.g. revive or restart), keep whichever surviving numbered
                # claim remains for that base.
                if len(active_names) == 1 and active_names[0] == base and base not in mapping:
                    numbered_candidates = [
                        name
                        for name in mapping.keys()
                        if _agent_base_name(name) == base and name not in active
                    ]
                    if numbered_candidates:
                        numbered_candidates.sort(
                            key=lambda name: (
                                _agent_instance_number(name)
                                if _agent_instance_number(name) is not None
                                else 10_000
                            )
                        )
                        source = numbered_candidates[0]
                        mapping[base] = mapping.pop(source)
                        changed = True

        def _prune(mapping: dict) -> None:
            nonlocal changed
            stale = [agent for agent in mapping.keys() if agent not in active]
            if not stale:
                return
            changed = True
            for agent in stale:
                mapping.pop(agent, None)

        _migrate_aliases(self._codex_cursors)
        _migrate_aliases(self._cursor_cursors)
        _migrate_aliases(self._copilot_cursors)
        _migrate_aliases(self._qwen_cursors)
        _migrate_aliases(self._claude_cursors)
        _migrate_aliases(self._gemini_cursors)
        _migrate_aliases(self._opencode_cursors)
        _migrate_aliases(self._agent_first_seen_ts)

        _prune(self._codex_cursors)
        _prune(self._cursor_cursors)
        _prune(self._copilot_cursors)
        _prune(self._qwen_cursors)
        _prune(self._claude_cursors)
        _prune(self._gemini_cursors)
        _prune(self._opencode_cursors)
        _prune(self._agent_first_seen_ts)

        if changed:
            self.save_sync_state()
        return changed

    def _recent_index_entries(self, *, max_lines: int = 160) -> list[dict]:
        if max_lines <= 0 or not self.index_path.exists():
            return []
        recent_lines: deque[str] = deque(maxlen=max_lines)
        try:
            with self.index_path.open("r", encoding="utf-8", errors="replace") as handle:
                for raw in handle:
                    line = raw.strip()
                    if line:
                        recent_lines.append(line)
        except Exception:
            return []
        entries: list[dict] = []
        for line in recent_lines:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                entries.append(item)
        return entries

    def apply_recent_targeted_claim_handoffs(
        self,
        active_agents: list[str],
        *,
        lookback_seconds: float = 45.0,
    ) -> bool:
        active = {str(agent).strip() for agent in (active_agents or []) if str(agent).strip()}
        if not active:
            return False
        recent_entries = self._recent_index_entries()
        if not recent_entries:
            return False
        cutoff = time.time() - max(1.0, float(lookback_seconds))
        latest_target_by_base: dict[str, str] = {}
        for entry in reversed(recent_entries):
            sender = str(entry.get("sender") or "").strip().lower()
            if sender == "system":
                continue
            targets = entry.get("targets")
            if not isinstance(targets, list) or len(targets) != 1:
                continue
            target = str(targets[0] or "").strip()
            if not target or target == "user" or target not in active:
                continue
            ts_raw = str(entry.get("timestamp") or "").strip()
            if ts_raw:
                try:
                    ts_epoch = dt_datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S").timestamp()
                    if ts_epoch < cutoff:
                        break
                except Exception:
                    pass
            base = _agent_base_name(target)
            if base not in latest_target_by_base:
                latest_target_by_base[base] = target
        changed = False
        for target in latest_target_by_base.values():
            if self._handoff_shared_sync_claim(target):
                changed = True
        return changed

    def save_sync_state(self) -> None:
        try:
            state = {
                "codex_cursors": _cursor_dict_to_json(self._codex_cursors),
                "cursor_cursors": _cursor_dict_to_json(self._cursor_cursors),
                "copilot_cursors": _cursor_dict_to_json(self._copilot_cursors),
                "qwen_cursors": _cursor_dict_to_json(self._qwen_cursors),
                "claude_cursors": _cursor_dict_to_json(self._claude_cursors),
                "gemini_cursors": _cursor_dict_to_json(self._gemini_cursors),
                "opencode_cursors": _opencode_dict_to_json(self._opencode_cursors),
                "agent_first_seen_ts": dict(self._agent_first_seen_ts),
                "last_sync": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            # Write to a temporary file first then rename for atomicity if needed,
            # but simple 'w' with flock is usually sufficient for this size.
            with self.sync_state_path.open("w", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                handle.write(json.dumps(state, ensure_ascii=False))
                handle.flush()
                os.fsync(handle.fileno())
            self._last_sync_state_heartbeat = time.time()
        except Exception as exc:
            logging.error(f"Failed to save sync state: {exc}")

    def sync_cursor_status(self) -> list[dict]:
        """Return per-agent sync cursor info for the debug UI."""
        agents = self.active_agents()
        result: list[dict] = []
        cursor_maps: list[tuple[str, dict[str, NativeLogCursor]]] = [
            ("codex", self._codex_cursors),
            ("cursor", self._cursor_cursors),
            ("copilot", self._copilot_cursors),
            ("qwen", self._qwen_cursors),
            ("claude", self._claude_cursors),
            ("gemini", self._gemini_cursors),
        ]
        for agent in agents:
            base = _agent_base_name(agent)
            entry: dict = {"agent": agent, "type": base, "log_path": None, "offset": None, "file_size": None, "session_id": None, "last_msg_id": None}
            # Check native-log cursors
            for _type, cmap in cursor_maps:
                if agent in cmap:
                    c = cmap[agent]
                    entry["log_path"] = c.path
                    entry["offset"] = c.offset
                    try:
                        entry["file_size"] = os.path.getsize(c.path)
                    except OSError:
                        entry["file_size"] = None
                    break
            # Check OpenCode cursors
            if agent in self._opencode_cursors:
                oc = self._opencode_cursors[agent]
                entry["session_id"] = oc.session_id
                entry["last_msg_id"] = oc.last_msg_id
            # first_seen_ts
            entry["first_seen_ts"] = self._first_seen_for_agent(agent)
            result.append(entry)
        return result

    def _parse_opencode_runtime(self, agent: str, limit: int) -> list[dict] | None:
        return _parse_opencode_runtime_impl(self, agent, limit)

    @staticmethod
    def _font_family_stack(selection: str, role: str) -> str:
        value = str(selection or "").strip()
        sans_stack = '"anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Meiryo", sans-serif'
        serif_stack = '"anthropicSerif", "anthropicSerif Fallback", "Anthropic Serif", "Hiragino Mincho ProN", "Yu Mincho", "YuMincho", "Noto Serif JP", Georgia, "Times New Roman", Times, serif'
        default_stack = sans_stack if role == "user" else serif_stack
        if value == "preset-gothic":
            return sans_stack
        if value == "preset-mincho":
            return serif_stack
        if value.startswith("system:"):
            family = value.split(":", 1)[1].strip()
            if family:
                return f'"{family}", {default_stack}'
        return default_stack

    @classmethod
    def chat_font_settings_inline_style(cls, settings: dict) -> str:
        user_family = cls._font_family_stack(settings.get("user_message_font", "preset-gothic"), "user")
        agent_family = cls._font_family_stack(settings.get("agent_message_font", "preset-mincho"), "agent")
        agent_font_mode = str(settings.get("agent_font_mode", "serif") or "serif").strip().lower()
        if agent_font_mode == "gothic":
            thinking_body_variation = '"wght" 360, "opsz" 16'
            thinking_keyword_variation = '"wght" 530, "opsz" 16'
            thinking_letter_spacing = "-0.01em"
        else:
            thinking_body_variation = '"wght" 360'
            thinking_keyword_variation = '"wght" 530'
            thinking_letter_spacing = "0"
        theme = str(settings.get("theme", "black-hole") or "black-hole").strip().lower()
        try:
            message_text_size = max(11, min(18, int(settings.get("message_text_size", 13))))
        except Exception:
            message_text_size = 13
        try:
            message_max_width = max(400, min(2000, int(settings.get("message_max_width", 900))))
        except Exception:
            message_max_width = 900
        try:
            user_opacity = max(0.2, min(1.0, float(settings.get("user_message_opacity_blackhole", 1.0))))
        except Exception:
            user_opacity = 1.0
        try:
            agent_opacity = max(0.2, min(1.0, float(settings.get("agent_message_opacity_blackhole", 1.0))))
        except Exception:
            agent_opacity = 1.0
        if theme == "black-hole":
            user_color = f"rgba(252, 252, 252, {user_opacity:.2f})"
            agent_color = f"rgba(252, 252, 252, {agent_opacity:.2f})"
        else:
            # Light themes should inherit dark foreground tones.
            user_color = f"rgba(26, 30, 36, {user_opacity:.2f})"
            agent_color = f"rgba(26, 30, 36, {agent_opacity:.2f})"
        
        bold_parts: list[str] = []
        inner = _chat_bold_mode_rules_block()
        if settings.get("bold_mode_mobile"):
            bold_parts.append(
                f"@media (max-width: {BOLD_MODE_VIEWPORT_MAX_PX}px) {{\n{inner}\n    }}"
            )
        if settings.get("bold_mode_desktop"):
            bold_parts.append(
                f"@media (min-width: {BOLD_MODE_VIEWPORT_MAX_PX + 1}px) {{\n{inner}\n    }}"
            )
        bold_style = "\n".join(bold_parts)
        return f"""
    :root {{
      --message-text-size: {message_text_size}px;
      --message-text-line-height: {message_text_size + 9}px;
      --message-max-width: {message_max_width}px;
      --user-message-blackhole-color: {user_color};
      --agent-message-blackhole-color: {agent_color};
      --agent-thinking-font-family: {agent_family};
      --agent-thinking-body-variation: {thinking_body_variation};
      --agent-thinking-keyword-variation: {thinking_keyword_variation};
      --agent-thinking-letter-spacing: {thinking_letter_spacing};
    }}
    .shell {{
      max-width: var(--message-max-width) !important;
    }}
    .composer {{
      width: min(var(--message-max-width), calc(100vw - 24px)) !important;
      max-width: var(--message-max-width) !important;
    }}
    .composer-main-shell {{
      max-width: var(--message-max-width) !important;
    }}
    .statusline {{
      width: min(var(--message-max-width), calc(100vw - 16px)) !important;
    }}
    .brief-editor-panel {{
      width: min(92vw, var(--message-max-width)) !important;
      max-width: var(--message-max-width) !important;
    }}
    .message.user .md-body {{
      font-family: {user_family} !important;
      color: var(--user-message-blackhole-color) !important;
    }}
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4,
    .message.user .md-body blockquote {{
      color: var(--user-message-blackhole-color) !important;
    }}
    {generate_agent_message_selectors(" .md-body")} {{
      font-family: {agent_family} !important;
      color: var(--agent-message-blackhole-color) !important;
    }}
    {_bh_agent_detail_selectors(prefix="")} {{
      color: var(--agent-message-blackhole-color) !important;
    }}
    {bold_style}
    """


    def load_thinking_totals(self) -> dict[str, int]:
        return load_shared_session_thinking_totals(self.repo_root, self.session_name, self.workspace)

    def append_system_entry(self, message: str, *, agent: str = "", **extra) -> dict:
        entry = {
            "timestamp": dt_datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session": self.session_name,
            "sender": "system",
            "targets": [],
            "message": message,
            "msg_id": uuid.uuid4().hex[:12],
        }
        if agent:
            entry["agent"] = agent
        entry.update(extra)
        append_jsonl_entry(self.index_path, entry)
        return entry

    def _read_commit_state_locked(self, handle) -> dict:
        handle.seek(0)
        raw = handle.read().strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return {}

    @staticmethod
    def _commit_state_payload(commit: dict) -> dict:
        return {
            "last_commit_hash": commit["hash"],
            "last_commit_short": commit["short"],
            "last_commit_subject": commit["subject"],
        }

    def _write_commit_state_locked(self, handle, commit: dict) -> None:
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(self._commit_state_payload(commit), ensure_ascii=False))
        handle.flush()

    def has_logged_commit_entry(self, commit_hash: str, *, recent_limit: int = 256) -> bool:
        commit_hash = (commit_hash or "").strip()
        if not commit_hash or not self.index_path.exists():
            return False
        try:
            recent_lines: deque[str] = deque(maxlen=max(32, int(recent_limit)))
            with self.index_path.open("r", encoding="utf-8") as f:
                for line in f:
                    recent_lines.append(line)
            for line in reversed(recent_lines):
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if entry.get("kind") != "git-commit":
                    continue
                if (entry.get("commit_hash") or "").strip() == commit_hash:
                    return True
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
        return False

    def start_direct_provider_run(self, provider: str, prompt: str, reply_to: str = "", provider_model: str = "") -> tuple[int, dict]:
        provider_name = (provider or "").strip().lower()
        prompt = (prompt or "").strip()
        reply_to = (reply_to or "").strip()
        provider_model = (provider_model or "").strip()
        if not self.session_is_active:
            return 409, {"ok": False, "error": "archived session is read-only"}
        supported_providers = {"gemini", "ollama"}
        if provider_name not in supported_providers:
            return 400, {"ok": False, "error": f"unsupported direct provider: {provider_name}"}
        if not prompt:
            return 400, {"ok": False, "error": "message is required"}
        bin_dir = Path(self.agent_send_path).parent
        runner_map = {
            "gemini": "multiagent-gemini-direct-run",
            "ollama": "multiagent-ollama-direct-run",
        }
        runner = bin_dir / runner_map[provider_name]
        if not runner.is_file():
            return 500, {"ok": False, "error": f"{runner_map[provider_name]} not found"}
        env = os.environ.copy()
        env.pop("MULTIAGENT_AGENT_NAME", None)
        env["MULTIAGENT_SESSION"] = self.session_name
        env["MULTIAGENT_WORKSPACE"] = self.workspace
        env["MULTIAGENT_LOG_DIR"] = self.log_dir
        env["MULTIAGENT_BIN_DIR"] = str(bin_dir)
        env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
        env.pop("TMUX", None)
        env.pop("TMUX_PANE", None)
        command = [
            str(runner),
            "--session",
            self.session_name,
            "--workspace",
            self.workspace,
            "--sender",
            provider_name,
            "--target",
            "user",
            "--prompt-sender",
            "user",
            "--prompt-target",
            provider_name,
        ]
        if self.log_dir:
            command.extend(["--log-dir", self.log_dir])
        if reply_to:
            command.extend(["--reply-to", reply_to])
        if provider_model:
            command.extend(["--model", provider_model])
        try:
            proc = subprocess.Popen(
                command,
                cwd=self.workspace or None,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
                close_fds=True,
            )
            if proc.stdin is not None:
                proc.stdin.write(prompt)
                if not prompt.endswith("\n"):
                    proc.stdin.write("\n")
                proc.stdin.close()
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return 500, {"ok": False, "error": str(exc)}
        return 200, {"ok": True, "mode": "provider-direct", "provider": provider_name}

    def read_commit_state(self) -> dict:
        if not self.commit_state_path.exists():
            return {}
        try:
            with self.commit_state_path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                try:
                    return self._read_commit_state_locked(handle)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return {}

    def write_commit_state(self, commit: dict) -> None:
        try:
            self.commit_state_path.parent.mkdir(parents=True, exist_ok=True)
            with self.commit_state_path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    self._write_commit_state_locked(handle, commit)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            pass

    def _record_git_commit_locked(self, handle, commit: dict, *, agent: str = "") -> bool:
        if self.has_logged_commit_entry(commit["hash"]):
            self._write_commit_state_locked(handle, commit)
            return False
        self.append_system_entry(
            f"Commit: {commit['short']} {commit['subject']}",
            kind="git-commit",
            commit_hash=commit["hash"],
            commit_short=commit["short"],
            agent=agent,
        )
        self._write_commit_state_locked(handle, commit)
        return True

    def record_git_commit(self, *, commit_hash: str, commit_short: str, subject: str, agent: str = "") -> bool:
        commit = {
            "hash": (commit_hash or "").strip(),
            "short": (commit_short or "").strip(),
            "subject": str(subject or "").strip(),
        }
        if not commit["hash"] or not commit["short"] or not commit["subject"]:
            return False
        try:
            self.commit_state_path.parent.mkdir(parents=True, exist_ok=True)
            with self.commit_state_path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    return self._record_git_commit_locked(handle, commit, agent=agent)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return False

    def current_git_commit(self) -> dict | None:
        try:
            result = subprocess.run(
                ["git", "-C", self.workspace, "log", "-1", "--format=%H%x1f%h%x1f%s"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return None
        if result.returncode != 0:
            return None
        line = result.stdout.strip()
        if not line:
            return None
        parts = line.split("\x1f", 2)
        if len(parts) != 3:
            return None
        return {"hash": parts[0], "short": parts[1], "subject": parts[2]}

    def git_commits_since(self, base_hash: str) -> list[dict] | None:
        try:
            result = subprocess.run(
                ["git", "-C", self.workspace, "log", "--reverse", "--format=%H%x1f%h%x1f%s", f"{base_hash}..HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return None
        if result.returncode != 0:
            return None
        commits = []
        for line in result.stdout.splitlines():
            parts = line.split("\x1f", 2)
            if len(parts) != 3:
                continue
            commits.append({"hash": parts[0], "short": parts[1], "subject": parts[2]})
        return commits

    def ensure_commit_announcements(self) -> None:
        current = self.current_git_commit()
        if not current:
            return
        try:
            self.commit_state_path.parent.mkdir(parents=True, exist_ok=True)
            with self.commit_state_path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    state = self._read_commit_state_locked(handle)
                    last_hash = state.get("last_commit_hash", "")
                    if not last_hash:
                        self._write_commit_state_locked(handle, current)
                        return
                    if last_hash == current["hash"]:
                        return
                    commits = self.git_commits_since(last_hash)
                    if commits is None:
                        commits = [current]
                    if not commits:
                        self._write_commit_state_locked(handle, current)
                        return
                    for commit in commits:
                        self._record_git_commit_locked(handle, commit)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)

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
        entries = self._matched_entries()
        target_around = around_msg_id.strip()
        l = limit_override if limit_override is not None else self.limit
        if target_around:
            idx = next((i for i, entry in enumerate(entries) if str(entry.get("msg_id") or "") == target_around), -1)
            if idx >= 0:
                if l and l > 0:
                    half = max(0, l // 2)
                    start = max(0, idx - half)
                    end = min(len(entries), start + l)
                    start = max(0, end - l)
                    has_older = start > 0
                    return entries[start:end], has_older
                return entries, idx > 0
        if before_msg_id:
            target = before_msg_id.strip()
            idx = next((i for i, entry in enumerate(entries) if str(entry.get("msg_id") or "") == target), -1)
            if idx < 0:
                return [], False
            entries = entries[:idx]
        has_older = False
        if l and l > 0:
            has_older = len(entries) > l
            return entries[-l:], has_older
        return entries, False

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
        return {
            "server_instance": self.server_instance,
            "session": self.session_name,
            "active": self.session_is_active,
            "source": str(self.index_path),
            "workspace": self.workspace,
            "log_dir": self.log_dir,
            "port": self.port,
            "hub_port": self.hub_port,
            "session_path": f"/session/{session_slug}/",
            "follow_path": f"/session/{session_slug}/?follow=1",
        }

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
        try:
            result = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name, "MULTIAGENT_AUTO_MODE"],
                capture_output=True,
                text=True,
                check=False,
            )
            active = result.stdout.strip() == "MULTIAGENT_AUTO_MODE=1"
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            active = False
        approval_file = f"/tmp/multiagent_auto_approved_{self.session_name}"
        try:
            last_approval = os.path.getmtime(approval_file)
            last_approval_agent = Path(approval_file).read_text().strip().lower()
        except OSError:
            last_approval = 0
            last_approval_agent = ""
        return {"active": active, "last_approval": last_approval, "last_approval_agent": last_approval_agent}

    def active_agents(self) -> list[str]:
        """Return the list of agent instance names from MULTIAGENT_AGENTS."""
        try:
            r = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name, "MULTIAGENT_AGENTS"],
                capture_output=True, text=True, timeout=2, check=False,
            )
            line = r.stdout.strip()
            if r.returncode == 0 and "=" in line:
                return [a for a in line.split("=", 1)[1].split(",") if a]
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            pass
        pane_agents = self._agents_from_pane_env()
        if pane_agents:
            return pane_agents
        return list(self.targets) if self.targets else []

    def _agents_from_pane_env(self) -> list[str]:
        """Recover instance names from MULTIAGENT_PANE_* while MULTIAGENT_AGENTS is still settling."""
        try:
            r = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return []
        if r.returncode != 0:
            return []
        return agents_from_tmux_env_output(r.stdout)

    def resolve_target_agents(self, target: str) -> list[str]:
        return resolve_target_agent_names(target, self.active_agents())

    def pane_id_for_agent(self, agent_name: str) -> str:
        pane_var = f"MULTIAGENT_PANE_{agent_name.upper().replace('-', '_')}"
        res = subprocess.run(
            [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip().split("=", 1)[-1] if "=" in res.stdout else ""

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
        base = _agent_base_name(agent_name)
        if base == "codex":
            return self._codex_cursors
        if base == "cursor":
            return self._cursor_cursors
        if base == "copilot":
            return self._copilot_cursors
        if base == "qwen":
            return self._qwen_cursors
        if base == "claude":
            return self._claude_cursors
        if base == "gemini":
            return self._gemini_cursors
        return None

    def _handoff_shared_sync_claim(self, agent_name: str) -> bool:
        """Move a shared same-base sync claim to an explicitly-targeted agent.

        Some CLIs can temporarily emit both instances into a single native log
        right after add/remove transitions. When we have exactly one same-base
        claim and target a different instance, transfer that claim so the next
        synced reply follows the explicit routing target.
        """
        target = str(agent_name or "").strip()
        if not target:
            return False
        base = _agent_base_name(target)
        donor = ""
        moved = False
        if base == "opencode":
            if target in self._opencode_cursors:
                return False
            same_base_claimants = [
                name
                for name in sorted(self._opencode_cursors.keys())
                if _agent_base_name(name) == base and name != target
            ]
            if len(same_base_claimants) != 1:
                return False
            donor = same_base_claimants[0]
            donor_cursor = self._opencode_cursors.get(donor)
            if donor_cursor is None:
                return False
            self._opencode_cursors[target] = donor_cursor
            self._opencode_cursors.pop(donor, None)
            moved = True
        else:
            cmap = self._native_cursor_map_for_agent(target)
            if not cmap or target in cmap:
                return False
            same_base_claimants = [
                name for name in sorted(cmap.keys()) if _agent_base_name(name) == base and name != target
            ]
            if len(same_base_claimants) != 1:
                return False
            donor = same_base_claimants[0]
            donor_cursor = cmap.get(donor)
            if donor_cursor is None:
                return False
            cmap[target] = donor_cursor
            cmap.pop(donor, None)
            moved = True
        if not moved:
            return False
        donor_first_seen = self._agent_first_seen_ts.get(donor)
        if donor_first_seen is not None and target not in self._agent_first_seen_ts:
            self._agent_first_seen_ts[target] = donor_first_seen
        self.save_sync_state()
        return True

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
        provider_direct: str = "",
        provider_model: str = "",
    ) -> tuple[int, dict]:
        target = (target or "").strip()
        message = (message or "").strip()
        reply_to = (reply_to or "").strip()
        provider_direct = (provider_direct or "").strip().lower()
        provider_model = (provider_model or "").strip()
        if not message:
            return 400, {"ok": False, "error": "message is required"}
        if provider_direct:
            return self.start_direct_provider_run(provider_direct, message, reply_to, provider_model=provider_model)
        if target:
            target = ",".join(self.resolve_target_agents(target))
        env = os.environ.copy()
        env["MULTIAGENT_SESSION"] = self.session_name
        env["MULTIAGENT_WORKSPACE"] = self.workspace
        env["MULTIAGENT_LOG_DIR"] = self.log_dir
        env["MULTIAGENT_INDEX_PATH"] = str(self.index_path)
        env["MULTIAGENT_BIN_DIR"] = str(Path(self.agent_send_path).parent)
        env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
        env.pop("TMUX", None)
        env.pop("TMUX_PANE", None)
        env["MULTIAGENT_AGENT_NAME"] = "user"
        bin_dir = Path(self.agent_send_path).parent
        pane_direct = self._parse_pane_direct_command(message)
        if message in {"brief", "save", "interrupt", "ctrlc", "enter", "restart", "resume"} or pane_direct:
            if message in {"interrupt", "ctrlc", "enter", "restart", "resume"} or pane_direct:
                if not target:
                    return 400, {"ok": False, "error": "target is required"}
                control_targets = [item.strip() for item in target.split(",") if item.strip()]
                try:
                    for agent in control_targets:
                        if message == "restart":
                            ok, detail = self.restart_agent_pane(agent)
                            if not ok:
                                return 400, {"ok": False, "error": detail}
                            continue
                        if message == "resume":
                            ok, detail = self.resume_agent_pane(agent)
                            if not ok:
                                return 400, {"ok": False, "error": detail}
                            continue
                        pane_id = self.pane_id_for_agent(agent)
                        if not pane_id:
                            return 400, {"ok": False, "error": f"pane not found for {agent}"}
                        if pane_direct:
                            if pane_direct["name"] == "model":
                                subprocess.run(
                                    [*self.tmux_prefix, "send-keys", "-t", pane_id, "/", "m", "o", "d", "e", "l"],
                                    capture_output=True,
                                    check=False,
                                )
                                time.sleep(0.15)
                                subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, "Enter"], capture_output=True, check=False)
                            else:
                                tmux_key = {"up": "Up", "down": "Down"}[pane_direct["name"]]
                                for _ in range(pane_direct["repeat"]):
                                    subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, tmux_key], capture_output=True, check=False)
                            continue
                        tmux_key = {"interrupt": "Escape", "ctrlc": "C-c", "enter": "Enter"}[message]
                        subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, tmux_key], capture_output=True, check=False)
                except Exception as exc:
                    logging.error(f"Unexpected error: {exc}", exc_info=True)
                    return 500, {"ok": False, "error": str(exc)}
                if message in {"restart", "resume"} and control_targets:
                    action = "Restarted" if message == "restart" else "Resumed"
                    self.append_system_entry(
                        f"{action}: {', '.join(control_targets)}",
                        kind="agent-control",
                        command=message,
                        targets=control_targets,
                    )
                return 200, {"ok": True, "mode": pane_direct["name"] if pane_direct else message}
            command = [str(bin_dir / "multiagent"), message, "--session", self.session_name]
            if message == "brief" and target:
                command.extend(["--agent", target])
            try:
                if message == "brief":
                    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                    return 200, {"ok": True, "mode": message}
                result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                return 500, {"ok": False, "error": str(exc)}
            if result.returncode != 0:
                return 400, {"ok": False, "error": (result.stderr or result.stdout or f"{message} failed").strip()}
            return 200, {"ok": True, "mode": message}
        if not target:
            target = "user"
        targets = [item.strip() for item in target.split(",") if item.strip()]
        if not targets:
            return 400, {"ok": False, "error": "target is required"}
        if targets == ["user"]:
            entry = {
                "timestamp": dt_datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "session": self.session_name,
                "sender": "user",
                "targets": ["user"],
                "message": message,
                "msg_id": uuid.uuid4().hex[:12],
            }
            if reply_to:
                entry["reply_to"] = reply_to
                reply_preview = self._reply_preview_for(reply_to)
                if reply_preview:
                    entry["reply_preview"] = reply_preview
            append_jsonl_entry(self.index_path, entry)
            return 200, {"ok": True, "mode": "memo"}
        if "user" in targets:
            return 400, {"ok": False, "error": 'target "user" cannot be combined with other targets'}
        delivery_targets: list[str] = []
        seen_targets: set[str] = set()
        for agent in targets:
            if agent == "others":
                for expanded in self.active_agents():
                    if expanded not in seen_targets:
                        seen_targets.add(expanded)
                        delivery_targets.append(expanded)
                continue
            if agent not in seen_targets:
                seen_targets.add(agent)
                delivery_targets.append(agent)
        if not delivery_targets:
            return 400, {"ok": False, "error": "target is required"}
        base_target_counts: dict[str, int] = {}
        for agent in delivery_targets:
            base = _agent_base_name(agent)
            base_target_counts[base] = base_target_counts.get(base, 0) + 1
        if silent or raw:
            try:
                for agent in delivery_targets:
                    pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
                    res = subprocess.run(
                        [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    pane_id = res.stdout.strip().split("=", 1)[-1] if "=" in res.stdout else ""
                    if not pane_id:
                        return 400, {"ok": False, "error": f"pane not found for {agent}"}
                    self._wait_for_send_slot(agent)
                    if not self._wait_for_agent_prompt(pane_id, agent):
                        return 400, {"ok": False, "error": f"pane not ready for {agent}"}
                    typed_res = subprocess.run(
                        [*self.tmux_prefix, "send-keys", "-t", pane_id, "-l", message],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if typed_res.returncode != 0:
                        return 400, {"ok": False, "error": f"Failed to deliver to: {agent}"}
                    time.sleep(0.3)
                    enter_res = subprocess.run(
                        [*self.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"],
                        capture_output=True,
                        check=False,
                    )
                    if enter_res.returncode != 0:
                        return 400, {"ok": False, "error": f"Failed to deliver to: {agent}"}
                    self._mark_agent_sent(agent)
                    if base_target_counts.get(_agent_base_name(agent), 0) == 1:
                        self._handoff_shared_sync_claim(agent)
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                return 500, {"ok": False, "error": str(exc)}
            return 200, {"ok": True, "raw": bool(raw)}
        payload = f"[From: User]\n{message}"
        successful_targets: list[str] = []
        failed_targets: list[str] = []
        try:
            for agent in delivery_targets:
                pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
                pane_res = subprocess.run(
                    [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                pane_id = pane_res.stdout.strip().split("=", 1)[-1] if "=" in pane_res.stdout else ""
                if not pane_id:
                    failed_targets.append(agent)
                    continue
                self._wait_for_send_slot(agent)
                if not self._wait_for_agent_prompt(pane_id, agent):
                    failed_targets.append(agent)
                    continue
                type_res = subprocess.run(
                    [*self.tmux_prefix, "send-keys", "-t", pane_id, "-l", payload],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if type_res.returncode != 0:
                    failed_targets.append(agent)
                    continue
                time.sleep(0.3)
                enter_res = subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"], capture_output=True, check=False)
                if enter_res.returncode != 0:
                    failed_targets.append(agent)
                    continue
                self._mark_agent_sent(agent)
                if base_target_counts.get(_agent_base_name(agent), 0) == 1:
                    self._handoff_shared_sync_claim(agent)
                successful_targets.append(agent)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return 500, {"ok": False, "error": str(exc)}
        if not successful_targets:
            if failed_targets:
                return 400, {"ok": False, "error": f"Failed to deliver to: {failed_targets[0]}"}
            return 400, {"ok": False, "error": "No target panes resolved."}
        entry = {
            "timestamp": dt_datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session": self.session_name,
            "sender": "user",
            "targets": successful_targets,
            "message": payload,
            "msg_id": uuid.uuid4().hex[:12],
        }
        if reply_to:
            entry["reply_to"] = reply_to
            reply_preview = self._reply_preview_for(reply_to)
            if reply_preview:
                entry["reply_preview"] = reply_preview
        append_jsonl_entry(self.index_path, entry)
        if failed_targets:
            return 400, {"ok": False, "error": f"Failed to deliver to: {', '.join(failed_targets)}"}
        return 200, {"ok": True}

    @staticmethod
    def _parse_pane_direct_command(message: str) -> dict | None:
        normalized = (message or "").strip().lower()
        if normalized == "model":
            return {"name": "model", "repeat": 1}
        match = re.fullmatch(r"(up|down)(?:\s+(\d+))?", normalized)
        if not match:
            return None
        repeat = max(1, min(int(match.group(2) or "1"), 100))
        return {"name": match.group(1), "repeat": repeat}

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
