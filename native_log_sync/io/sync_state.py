from __future__ import annotations

import fcntl
import json
import logging
import os
import time
from datetime import datetime as dt_datetime
from pathlib import Path

from native_log_sync.io.state_claims import collect_global_native_log_claims
from native_log_sync.io.state_paths import legacy_agent_index_sync_state_path
from native_log_sync.io.cursor_state import (
    NativeLogCursor,
    _agent_base_name,
    _agent_instance_number,
    _cursor_dict_to_json,
    _native_path_claim_key,
    _opencode_dict_to_json,
)
from native_log_sync.agents._shared.resolve_path import pick_latest_unclaimed_for_agent


def load_sync_state(runtime) -> dict:
    canonical = runtime.sync_state_path
    legacy = legacy_agent_index_sync_state_path(canonical.parent)

    if canonical.exists():
        read_path = canonical
    elif legacy.exists():
        read_path = legacy
    else:
        return {}

    try:
        with read_path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            raw = handle.read().strip()
            if not raw:
                return {}
            data = json.loads(raw)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

    if read_path == legacy:
        try:
            legacy.rename(canonical)
        except OSError:
            try:
                canonical.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                legacy.unlink()
            except OSError:
                pass
    else:
        if legacy.exists():
            try:
                legacy.unlink()
            except OSError:
                pass

    return data


def is_globally_claimed_path(runtime, path: str) -> bool:
    candidate_key = _native_path_claim_key(path)
    for claimed_path in runtime._collect_global_native_log_claims().keys():
        if _native_path_claim_key(claimed_path) == candidate_key:
            return True
    return False


def first_seen_for_agent(runtime, agent: str, *, time_module=time) -> float:
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
    return pick_latest_unclaimed_for_agent(
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

            primary_numbered = f"{base}-1"
            if (
                primary_numbered in active
                and primary_numbered not in mapping
                and base in mapping
                and base not in active
            ):
                mapping[primary_numbered] = mapping.pop(base)
                changed = True

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
        if start > 0:
            newline_idx = text.find("\n")
            if newline_idx >= 0:
                text = text[newline_idx + 1:]
        for raw in text.splitlines():
            line = raw.strip()
            if line:
                raw_lines.append(line)
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
