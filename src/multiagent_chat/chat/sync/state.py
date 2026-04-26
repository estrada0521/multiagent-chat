from __future__ import annotations

import fcntl
import json
import logging
import os
import subprocess
import time
from collections import deque
from datetime import datetime as dt_datetime
from pathlib import Path

from .cursor import (
    NativeLogCursor,
    _agent_base_name,
    _agent_instance_number,
    _cursor_dict_to_json,
    _native_path_claim_key,
    _opencode_dict_to_json,
    _pick_latest_unclaimed_for_agent,
)


def load_sync_state(runtime) -> dict:
    if not runtime.sync_state_path.exists():
        return {}
    try:
        with runtime.sync_state_path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            raw = handle.read().strip()
            if not raw:
                return {}
            return json.loads(raw)
    except FileNotFoundError:
        return {}


def collect_global_native_log_claims(
    runtime,
    *,
    global_log_claim_refresh_seconds: float,
    global_log_claim_ttl_seconds: float,
    subprocess_module=subprocess,
    time_module=time,
    path_class=Path,
) -> dict[str, tuple[str, str]]:
    now = time_module.time()
    if now - runtime._global_log_claims_fetched_at < float(global_log_claim_refresh_seconds):
        return runtime._global_log_claims

    claims: dict[str, tuple[str, str]] = {}
    base = path_class(runtime.log_dir)
    if not base.exists():
        runtime._global_log_claims = claims
        runtime._global_log_claims_fetched_at = now
        return claims

    active_sessions: set[str] | None = None
    try:
        sessions_res = subprocess_module.run(
            [*runtime.tmux_prefix, "list-sessions", "-F", "#{session_name}"],
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
            if session_name == runtime.session_name:
                continue
            if active_sessions is not None and session_name not in active_sessions:
                continue
            if now - state_path.stat().st_mtime > float(global_log_claim_ttl_seconds):
                continue
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logging.warning("Skipping unreadable sync state %s: %s", state_path, exc)
            continue
        except OSError:
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
                claims[str(path_class(cursor_path))] = (session_name, claimant_agent)

    runtime._global_log_claims = claims
    runtime._global_log_claims_fetched_at = now
    return claims


def is_globally_claimed_path(runtime, path: str) -> bool:
    candidate_key = _native_path_claim_key(path)
    for claimed_path in runtime._collect_global_native_log_claims().keys():
        if _native_path_claim_key(claimed_path) == candidate_key:
            return True
    return False


def first_seen_for_agent(runtime, agent: str, *, time_module=time) -> float:
    """Return (and lazily initialize) the timestamp when this runtime first observed *agent*."""
    ts = runtime._agent_first_seen_ts.get(agent)
    if ts is None:
        ts = time_module.time()
        runtime._agent_first_seen_ts[agent] = ts
    return ts


def should_stick_to_existing_cursor(runtime, agent: str) -> bool:
    base = _agent_base_name(agent)
    peers = {
        name
        for name in runtime._agent_first_seen_ts.keys()
        if _agent_base_name(name) == base and name != agent
    }
    if peers:
        return True
    try:
        for name in runtime.active_agents():
            if _agent_base_name(name) == base and name != agent:
                return True
    except Exception:
        pass
    return False


def has_outbound_target_for_agent(runtime, agent: str, *, tail_bytes: int = 65536) -> bool:
    if not runtime.index_path.exists():
        return False
    try:
        with runtime.index_path.open("rb") as handle:
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


def workspace_git_root(runtime, workspace: str, *, subprocess_module=subprocess, path_class=Path) -> str:
    cached = runtime._workspace_git_root_cache.get(workspace)
    if cached is not None:
        return cached
    git_root = ""
    try:
        res = subprocess_module.run(
            ["git", "-C", workspace, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0:
            candidate = (res.stdout or "").strip()
            if candidate:
                git_root = str(path_class(candidate).resolve())
    except Exception:
        git_root = ""
    runtime._workspace_git_root_cache[workspace] = git_root
    return git_root


def workspace_aliases(runtime, workspace: str, *, path_class=Path) -> list[str]:
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
            return [item, item[len("/private") :]]
        return [item]

    for candidate in (workspace, runtime._workspace_git_root(workspace)):
        value = str(candidate or "").strip()
        if not value:
            continue
        variants = [value]
        try:
            variants.append(str(path_class(value).resolve()))
        except Exception:
            pass
        for variant in variants:
            for alias in _tmp_aliases(variant):
                _push_alias(alias)
    return aliases


def cursor_transcript_roots(runtime, workspace: str, *, path_class=Path) -> list[Path]:
    slug_candidates: list[str] = []
    seen_slugs: set[str] = set()

    def _append_slug_from_path(path_value: str) -> None:
        slug = str(path_value).replace("/", "-").lstrip("-")
        if slug and slug not in seen_slugs:
            seen_slugs.add(slug)
            slug_candidates.append(slug)

    for path_value in runtime._workspace_aliases(workspace):
        _append_slug_from_path(path_value)

    roots: list[Path] = []
    for slug in slug_candidates:
        root = path_class.home() / ".cursor" / "projects" / slug / "agent-transcripts"
        if root.exists():
            roots.append(root)
    return roots


def cursor_fsevent_watch_path_strings(runtime, workspace: str, *, path_class=Path) -> list[str]:
    """Absolute paths for FSEvents: per-workspace transcript trees, or ~/.cursor/projects when missing."""
    workspace_text = str(workspace or "").strip()
    if not workspace_text:
        return []
    home = path_class.home()
    projects_base = home / ".cursor" / "projects"
    paths: list[str] = []
    seen: set[str] = set()
    need_broad = False
    for path_value in runtime._workspace_aliases(workspace_text):
        slug = str(path_value).replace("/", "-").lstrip("-")
        if not slug:
            continue
        transcripts = home / ".cursor" / "projects" / slug / "agent-transcripts"
        proj = home / ".cursor" / "projects" / slug
        if transcripts.is_dir():
            candidate = transcripts
        elif proj.is_dir():
            candidate = proj
        else:
            need_broad = True
            continue
        resolved = str(candidate.resolve())
        if resolved not in seen:
            seen.add(resolved)
            paths.append(resolved)
    if need_broad and projects_base.is_dir():
        broad = str(projects_base.resolve())
        if broad not in seen:
            paths.append(broad)
    if not paths and workspace_text and projects_base.is_dir():
        paths.append(str(projects_base.resolve()))
    return paths


def codex_rollout_candidates(runtime, workspace: str, *, path_class=Path) -> list[Path]:
    workspace_text = str(workspace or "").strip()
    workspace_aliases_set: set[str] = set()
    if workspace_text:
        workspace_aliases_set.add(workspace_text)
        try:
            workspace_aliases_set.add(str(path_class(workspace_text).resolve()))
        except Exception:
            pass
    if not workspace_aliases_set:
        return []
    sessions_root = path_class.home() / ".codex" / "sessions"
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
            resolved_candidates.add(str(path_class(cwd).resolve()))
        except Exception:
            pass
        if resolved_candidates.isdisjoint(workspace_aliases_set):
            continue
        candidates.append(candidate)
    return candidates


def pick_codex_rollout_for_agent(runtime, agent: str, *, first_seen_grace_seconds: float) -> Path | None:
    workspace = str(runtime.workspace or "").strip()
    if not workspace:
        return None
    candidates = runtime._codex_rollout_candidates(workspace)
    if not candidates:
        return None
    min_mtime = runtime._first_seen_for_agent(agent) - float(first_seen_grace_seconds)
    return _pick_latest_unclaimed_for_agent(
        candidates,
        runtime._codex_cursors,
        agent,
        min_mtime=min_mtime,
        exclude_paths=set(runtime._collect_global_native_log_claims().keys()),
    )


def maybe_heartbeat_sync_state(runtime, *, interval_seconds: float = 30.0, time_module=time) -> None:
    interval = max(1.0, float(interval_seconds))
    now = time_module.time()
    if now - runtime._last_sync_state_heartbeat < interval:
        return
    runtime.save_sync_state()


def prune_sync_claims_to_active_agents(runtime, active_agents: list[str]) -> bool:
    """Drop stale per-agent sync cursors for agents no longer active."""
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

    _migrate_aliases(runtime._codex_cursors)
    _migrate_aliases(runtime._cursor_cursors)
    _migrate_aliases(runtime._copilot_cursors)
    _migrate_aliases(runtime._qwen_cursors)
    _migrate_aliases(runtime._claude_cursors)
    _migrate_aliases(runtime._gemini_cursors)
    _migrate_aliases(runtime._opencode_cursors)
    _migrate_aliases(runtime._agent_first_seen_ts)

    _prune(runtime._codex_cursors)
    _prune(runtime._cursor_cursors)
    _prune(runtime._copilot_cursors)
    _prune(runtime._qwen_cursors)
    _prune(runtime._claude_cursors)
    _prune(runtime._gemini_cursors)
    _prune(runtime._opencode_cursors)
    _prune(runtime._agent_first_seen_ts)

    if changed:
        runtime.save_sync_state()
    return changed


def recent_index_entries(runtime, *, max_lines: int = 160) -> list[dict]:
    if max_lines <= 0 or not runtime.index_path.exists():
        return []
    # Tail-read: seek near end to avoid scanning the full 15MB file every second.
    # Estimate ~1500 bytes per line to ensure we cover max_lines with margin.
    tail_bytes = max(max_lines * 1500, 65536)
    raw_lines: list[str] = []
    try:
        with runtime.index_path.open("rb") as handle:
            handle.seek(0, 2)
            file_size = handle.tell()
            start = max(0, file_size - tail_bytes)
            handle.seek(start)
            chunk = handle.read()
        text = chunk.decode("utf-8", errors="replace")
        # If we seeked mid-line, skip the first partial line
        if start > 0:
            newline_idx = text.find("\n")
            if newline_idx >= 0:
                text = text[newline_idx + 1:]
        for raw in text.splitlines():
            line = raw.strip()
            if line:
                raw_lines.append(line)
        # Keep only the last max_lines
        if len(raw_lines) > max_lines:
            raw_lines = raw_lines[-max_lines:]
    except Exception:
        return []
    entries: list[dict] = []
    for line in raw_lines:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            entries.append(item)
    return entries


def apply_recent_targeted_claim_handoffs(
    runtime,
    active_agents: list[str],
    *,
    lookback_seconds: float = 45.0,
    time_module=time,
    datetime_class=dt_datetime,
) -> bool:
    active = {str(agent).strip() for agent in (active_agents or []) if str(agent).strip()}
    if not active:
        return False
    recent_entries = runtime._recent_index_entries()
    if not recent_entries:
        return False
    cutoff = time_module.time() - max(1.0, float(lookback_seconds))
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
                ts_epoch = datetime_class.strptime(ts_raw, "%Y-%m-%d %H:%M:%S").timestamp()
                if ts_epoch < cutoff:
                    break
            except Exception:
                pass
        base = _agent_base_name(target)
        if base not in latest_target_by_base:
            latest_target_by_base[base] = target
    changed = False
    for target in latest_target_by_base.values():
        if runtime._handoff_shared_sync_claim(target):
            changed = True
    return changed


def save_sync_state(runtime, *, time_module=time) -> None:
    try:
        state = {
            "codex_cursors": _cursor_dict_to_json(runtime._codex_cursors),
            "cursor_cursors": _cursor_dict_to_json(runtime._cursor_cursors),
            "copilot_cursors": _cursor_dict_to_json(runtime._copilot_cursors),
            "qwen_cursors": _cursor_dict_to_json(runtime._qwen_cursors),
            "claude_cursors": _cursor_dict_to_json(runtime._claude_cursors),
            "gemini_cursors": _cursor_dict_to_json(runtime._gemini_cursors),
            "opencode_cursors": _opencode_dict_to_json(runtime._opencode_cursors),
            "agent_first_seen_ts": dict(runtime._agent_first_seen_ts),
            "synced_msg_ids": list(runtime._synced_msg_ids),
            "last_sync": time_module.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with runtime.sync_state_path.open("w", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(state, ensure_ascii=False))
            handle.flush()
            os.fsync(handle.fileno())
        runtime._last_sync_state_heartbeat = time_module.time()
    except Exception as exc:
        logging.error(f"Failed to save sync state: {exc}")


def sync_cursor_status(runtime, *, os_module=os) -> list[dict]:
    """Return per-agent sync cursor info for the debug UI."""
    agents = runtime.active_agents()
    result: list[dict] = []
    cursor_maps: list[tuple[str, dict[str, NativeLogCursor]]] = [
        ("codex", runtime._codex_cursors),
        ("cursor", runtime._cursor_cursors),
        ("copilot", runtime._copilot_cursors),
        ("qwen", runtime._qwen_cursors),
        ("claude", runtime._claude_cursors),
        ("gemini", runtime._gemini_cursors),
    ]
    for agent in agents:
        base = _agent_base_name(agent)
        entry: dict = {
            "agent": agent,
            "type": base,
            "log_path": None,
            "offset": None,
            "file_size": None,
            "session_id": None,
            "last_msg_id": None,
        }
        for _type, cmap in cursor_maps:
            if agent in cmap:
                c = cmap[agent]
                entry["log_path"] = c.path
                entry["offset"] = c.offset
                try:
                    entry["file_size"] = os_module.path.getsize(c.path)
                except OSError:
                    entry["file_size"] = None
                break
        if agent in runtime._opencode_cursors:
            oc = runtime._opencode_cursors[agent]
            entry["session_id"] = oc.session_id
            entry["last_msg_id"] = oc.last_msg_id
        entry["first_seen_ts"] = runtime._first_seen_for_agent(agent)
        result.append(entry)
    return result


def native_cursor_map_for_agent(runtime, agent_name: str) -> dict[str, NativeLogCursor] | None:
    base = _agent_base_name(agent_name)
    if base == "codex":
        return runtime._codex_cursors
    if base == "cursor":
        return runtime._cursor_cursors
    if base == "copilot":
        return runtime._copilot_cursors
    if base == "qwen":
        return runtime._qwen_cursors
    if base == "claude":
        return runtime._claude_cursors
    if base == "gemini":
        return runtime._gemini_cursors
    return None


def handoff_shared_sync_claim(runtime, agent_name: str) -> bool:
    """Move a shared same-base sync claim to an explicitly-targeted agent."""
    target = str(agent_name or "").strip()
    if not target:
        return False
    base = _agent_base_name(target)
    donor = ""
    moved = False
    if base == "opencode":
        if target in runtime._opencode_cursors:
            return False
        same_base_claimants = [
            name
            for name in sorted(runtime._opencode_cursors.keys())
            if _agent_base_name(name) == base and name != target
        ]
        if len(same_base_claimants) != 1:
            return False
        donor = same_base_claimants[0]
        donor_cursor = runtime._opencode_cursors.get(donor)
        if donor_cursor is None:
            return False
        runtime._opencode_cursors[target] = donor_cursor
        runtime._opencode_cursors.pop(donor, None)
        moved = True
    else:
        cmap = runtime._native_cursor_map_for_agent(target)
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
    donor_first_seen = runtime._agent_first_seen_ts.get(donor)
    if donor_first_seen is not None and target not in runtime._agent_first_seen_ts:
        runtime._agent_first_seen_ts[target] = donor_first_seen
    runtime.save_sync_state()
    return True
