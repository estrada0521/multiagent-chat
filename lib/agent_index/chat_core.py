from __future__ import annotations
import fcntl
import hashlib
import logging

import json
import os
import re
import shlex
import subprocess
import time
import uuid
from collections import deque
from datetime import datetime as dt_datetime
from pathlib import Path
import shutil
from typing import NamedTuple
from urllib.parse import quote

from .agent_registry import AGENTS, ALL_AGENT_NAMES, generate_agent_message_selectors
from .instance_core import agents_from_tmux_env_output
from .instance_core import resolve_target_agents as resolve_target_agent_names
from .jsonl_append import append_jsonl_entry
from .redacted_placeholder import agent_index_entry_omit_for_redacted, normalize_cursor_plaintext_for_index
from .state_core import load_hub_settings as load_shared_hub_settings
from .state_core import load_session_thinking_totals as load_shared_session_thinking_totals



def _agent_base_name(agent: str) -> str:
    return re.sub(r"-\d+$", "", (agent or "").strip().lower())


class NativeLogCursor(NamedTuple):
    """Per-agent pointer into a native CLI log file.

    ``path`` is the absolute file path the cursor is bound to; ``offset`` is
    the number of bytes of that file already consumed. A cursor is *bound* to
    a specific file path: when the path changes for an agent (e.g. new CLI
    session or new instance claimed it), the caller must anchor the cursor
    to the new file's current end rather than re-reading from byte 0.
    """

    path: str
    offset: int


class OpenCodeCursor(NamedTuple):
    """OpenCode uses a SQLite DB, so we track session_id + last message id."""

    session_id: str
    last_msg_id: str


def _coerce_native_cursor(raw: object) -> NativeLogCursor | None:
    """Migrate a persisted cursor value to ``NativeLogCursor``.

    The sync-state file stores cursors as JSON. Historic versions stored:
      * a bare ``int`` (offset only; no path binding — unsafe to keep)
      * a 2-element list/tuple ``[path, offset]``

    Bare ints are discarded (returns ``None``) so the syncer will re-anchor
    on the next call instead of reading from a meaningless offset.
    """
    if isinstance(raw, NativeLogCursor):
        return raw
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        path, offset = raw
        if isinstance(path, str) and isinstance(offset, int):
            return NativeLogCursor(path=path, offset=offset)
    return None


def _coerce_opencode_cursor(raw: object) -> OpenCodeCursor | None:
    if isinstance(raw, OpenCodeCursor):
        return raw
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        session_id, msg_id = raw
        if isinstance(session_id, str) and isinstance(msg_id, str):
            return OpenCodeCursor(session_id=session_id, last_msg_id=msg_id)
    return None


def _load_cursor_dict(raw: object) -> dict[str, NativeLogCursor]:
    """Load a per-agent cursor dict from persisted state, discarding invalid entries."""
    result: dict[str, NativeLogCursor] = {}
    if isinstance(raw, dict):
        for agent, value in raw.items():
            if not isinstance(agent, str):
                continue
            cursor = _coerce_native_cursor(value)
            if cursor is not None:
                result[agent] = cursor
    return result


def _load_opencode_dict(raw: object) -> dict[str, OpenCodeCursor]:
    result: dict[str, OpenCodeCursor] = {}
    if isinstance(raw, dict):
        for agent, value in raw.items():
            if not isinstance(agent, str):
                continue
            cursor = _coerce_opencode_cursor(value)
            if cursor is not None:
                result[agent] = cursor
    return result


def _cursor_dict_to_json(cursors: dict[str, NativeLogCursor]) -> dict[str, list]:
    return {agent: [c.path, c.offset] for agent, c in cursors.items()}


def _opencode_dict_to_json(cursors: dict[str, OpenCodeCursor]) -> dict[str, list]:
    return {agent: [c.session_id, c.last_msg_id] for agent, c in cursors.items()}


def _dedup_cursor_claims(
    cursors: dict[str, NativeLogCursor],
) -> dict[str, NativeLogCursor]:
    """Remove duplicate path claims, keeping the alphabetically-first agent per path.

    When stale state or bugs cause two agents to point at the same file,
    messages from that file get attributed to whichever agent syncs first —
    causing the "qwen-1 messages show as qwen-2" bug.  This helper runs at
    load time and evicts the later-named duplicates so the displaced agents
    re-discover their own files on the next sync tick.
    """
    path_to_agent: dict[str, str] = {}
    out: dict[str, NativeLogCursor] = {}
    for agent in sorted(cursors):
        cursor = cursors[agent]
        if cursor.path in path_to_agent:
            continue  # drop duplicate — first (alphabetically) wins
        path_to_agent[cursor.path] = agent
        out[agent] = cursor
    return out


_FIRST_SEEN_GRACE_SECONDS = 120.0
_GLOBAL_LOG_CLAIM_TTL_SECONDS = 180.0
_GLOBAL_LOG_CLAIM_REFRESH_SECONDS = 5.0


def _pick_latest_unclaimed(
    candidates: list[Path],
    cursors: dict[str, NativeLogCursor],
    agent: str,
    min_mtime: float = 0.0,
    *,
    exclude_paths: set[str] | None = None,
) -> Path | None:
    """Return the most-recently-modified candidate not claimed by another agent.

    ``cursors`` maps agent name -> NativeLogCursor (may include the caller).
    Files already claimed by *other* agents in the same dict are skipped.
    ``min_mtime``: candidates with ``st_mtime < min_mtime`` are excluded.
    Pass the agent's ``first_seen_ts`` here so that pre-existing files
    (which may belong to some other CLI instance) don't get silently
    claimed before we can prove the agent actually wrote to them.

    Returns ``None`` when nothing qualifies. Callers should *not* retry
    with a relaxed filter — the right behavior in that case is to wait
    for the agent's CLI to touch a file, whose mtime will then exceed
    ``min_mtime`` and make it eligible on the next poll.
    """
    if not candidates:
        return None
    claimed: set[str] = set()
    if exclude_paths:
        normalize_exclude = {str(Path(p)) for p in exclude_paths}
    else:
        normalize_exclude = set()
    for other_agent, cursor in cursors.items():
        if other_agent == agent:
            continue
        claimed.add(cursor.path)
    eligible: list[tuple[float, Path]] = []
    for candidate in candidates:
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            continue
        if mtime < min_mtime:
            continue
        candidate_path = str(candidate)
        if candidate_path in claimed or candidate_path in normalize_exclude:
            continue
        eligible.append((mtime, candidate))
    if not eligible:
        return None
    eligible.sort(key=lambda item: item[0], reverse=True)
    return eligible[0][1]


def _pick_latest_unclaimed_for_agent(
    candidates: list[Path],
    cursors: dict[str, NativeLogCursor],
    agent: str,
    min_mtime: float,
    *,
    exclude_paths: set[str] | None = None,
) -> Path | None:
    """Pick a candidate, with a fallback for first-seen agents.

    Primary selection uses ``min_mtime`` to avoid claiming stale files on first
    call. If no file qualifies and this agent has never established a cursor yet,
    we retry with no mtime floor so the sync loop can still bind to a local log
    and report a stable ``log_path` without flooding history.
    """
    picked = _pick_latest_unclaimed(
        candidates,
        cursors,
        agent,
        min_mtime=min_mtime,
        exclude_paths=exclude_paths,
    )
    if picked is not None:
        return picked
    if agent in cursors:
        return None
    return _pick_latest_unclaimed(
        candidates,
        cursors,
        agent,
        min_mtime=0.0,
        exclude_paths=exclude_paths,
    )


def _advance_native_cursor(
    cursors: dict[str, NativeLogCursor],
    agent: str,
    current_path: str,
    file_size: int,
) -> int | None:
    """Decide whether to read from ``current_path`` and return the start offset.

    Returns ``None`` when no processing is needed (first sight of this path,
    or no new bytes since last sync). Returns ``0`` on detected truncation.
    When a non-None offset is returned, the *caller* must persist the new
    cursor ``(current_path, file_size)`` after it finishes reading — this
    keeps cursor advance and the actual read coupled in the caller.
    """
    prev = cursors.get(agent)
    if prev is None or prev.path != current_path:
        # First sight of this path for this agent — anchor to the end so we
        # don't flood historical content. This is the critical guard that
        # prevents Reload/Add-Agent from replaying old messages when the
        # "latest file" selection jumps to a different file than before.
        cursors[agent] = NativeLogCursor(path=current_path, offset=file_size)
        return None
    if file_size < prev.offset:
        # Truncation / rotation detected. Reset and read from the start.
        return 0
    if file_size == prev.offset:
        return None
    return prev.offset


def _cursor_binding_changed(
    before: NativeLogCursor | None,
    after: NativeLogCursor | None,
) -> bool:
    if before is None and after is None:
        return False
    if before is None or after is None:
        return True
    return before.path != after.path or before.offset != after.offset



def _pane_runtime_tag_occurrences(events: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    normalized: list[dict] = []
    for event in events:
        source_id = str((event or {}).get("source_id") or "").strip()
        if not source_id:
            continue
        counts[source_id] = counts.get(source_id, 0) + 1
        normalized.append({
            **event,
            "source_id": f"{source_id}#{counts[source_id]}",
        })
    return normalized


def _pane_runtime_with_occurrence_ids(events: list[dict], *, limit: int) -> list[dict]:
    normalized = _pane_runtime_tag_occurrences(events)
    return normalized[-max(1, int(limit)) :]


def _deduplicate_consecutive_thought_blocks(text: str) -> str:
    """Remove consecutive [Thought: true] blocks, keeping only the last one.
    
    When Gemini outputs multiple [Thought: true] blocks in a row, only the final
    thought should be displayed. Intermediate thoughts are noise.
    """
    import re
    
    # Find all [Thought: true] blocks with their content
    # A block is: [Thought: true]\n<content until next [Thought: true] or end>
    pattern = r'\[Thought: true\](.*?)(?=\[Thought: true\]|$)'
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    # If less than 2 consecutive blocks, no deduplication needed
    if len(matches) < 2:
        return text
    
    # Check if they are truly consecutive (no non-thought content between them)
    # We need to remove all but the last [Thought: true] block in consecutive sequences
    result = text
    consecutive_start = None
    
    for i in range(len(matches)):
        if i == 0:
            consecutive_start = 0
        else:
            # Check if there's content between previous and current match
            prev_end = matches[i-1].end()
            curr_start = matches[i].start()
            between = text[prev_end:curr_start].strip()
            
            if between:
                # Not consecutive - process previous sequence
                if consecutive_start is not None and i - 1 > consecutive_start:
                    # Remove all but last in this sequence
                    result = _remove_all_but_last_thought(result, consecutive_start, i - 1)
                consecutive_start = i
            else:
                # Consecutive - continue sequence
                pass
    
    # Process the final sequence
    if consecutive_start is not None and len(matches) - 1 > consecutive_start:
        result = _remove_all_but_last_thought(result, consecutive_start, len(matches) - 1)
    
    return result


def _remove_all_but_last_thought(text: str, start_idx: int, end_idx: int) -> str:
    """Remove [Thought: true] blocks from start_idx to end_idx-1, keeping end_idx."""
    import re
    
    # Find all [Thought: true] blocks again in current text
    pattern = r'\[Thought: true\](.*?)(?=\[Thought: true\]|$)'
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    if start_idx >= len(matches) or end_idx >= len(matches):
        return text
    
    # Remove blocks from start_idx to end_idx-1
    blocks_to_remove = matches[start_idx:end_idx]
    
    result = text
    # Remove in reverse order to maintain indices
    for match in reversed(blocks_to_remove):
        result = result[:match.start()] + result[match.end():]
    
    return result


def _pane_runtime_gemini_with_occurrence_ids(events: list[dict], *, limit: int) -> list[dict]:
    """Like _pane_runtime_with_occurrence_ids, but keep a ✦ thought visible when possible.

    A long run of tool-only rows after the latest thought would otherwise push every ✦ event
    out of the tail window; ensure the most recent thought is always included in the returned list.
    """
    tagged = _pane_runtime_tag_occurrences(events)
    lim = max(1, int(limit))
    if len(tagged) <= lim:
        return tagged

    tail = tagged[-lim:]
    if any("✦" in str((e or {}).get("text") or "") for e in tail):
        return tail

    last_thought = None
    for i in range(len(tagged) - 1, -1, -1):
        if "✦" in str((tagged[i] or {}).get("text") or ""):
            last_thought = tagged[i]
            break

    if not last_thought:
        return tail

    # Return [latest_thought] + the last (lim - 1) items to keep window size consistent
    return [last_thought] + tagged[-(lim - 1) :]


def _get_process_tree(pid: str) -> set[str]:
    """Get all descendant PIDs for a given PID using `ps`."""
    try:
        out = subprocess.run(["ps", "-eo", "pid,ppid"], capture_output=True, text=True, check=True).stdout
        children_map = {}
        for line in out.splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2:
                c, p = parts[0], parts[1]
                children_map.setdefault(p, []).append(c)
        
        pids = {pid}
        q = [pid]
        while q:
            curr = q.pop(0)
            for c in children_map.get(curr, []):
                if c not in pids:
                    pids.add(c)
                    q.append(c)
        return pids
    except Exception:
        return {pid}

def _resolve_native_log_file(pane_pid: str, log_pattern: str, base_name: str = "") -> str | None:
    """Find an open file matching log_pattern that belongs to the given pane_pid or its descendants."""
    pids = _get_process_tree(str(pane_pid).strip())
    if not pids:
        return None
    
    # Special handling for Copilot: look for inuse.[PID].lock files
    if base_name == "copilot":
        for pid in pids:
            # Check ~/.copilot/session-state/*/inuse.[PID].lock
            state_dir = Path.home() / ".copilot" / "session-state"
            if state_dir.exists():
                for lock_file in state_dir.glob(f"*/inuse.{pid}.lock"):
                    session_dir = lock_file.parent
                    log_file = session_dir / "events.jsonl"
                    if log_file.exists():
                        return str(log_file)

    try:
        # -a: AND, -d ^txt,cwd,rtd: exclude non-files, -Fn: output filenames
        cmd = ["lsof", "-p", ",".join(pids), "-Fn"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
        for line in out.splitlines():
            if line.startswith("n"):
                path = line[1:]
                if re.search(log_pattern, path):
                    return path
    except Exception:
        pass
    return None

def _parse_native_codex_log(filepath: str, limit: int) -> list[dict] | None:
    """Parse Codex rollout JSONL file."""
    try:
        events = []
        with open(filepath, "r", encoding="utf-8") as f:
            # We don't need to read the whole file if it's huge, but typically rollouts are small enough for tail-like logic.
            # To be safe, we just read lines and keep the last `limit` + recent thoughts.
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            if data.get("type") == "response_item" and "payload" in data:
                payload = data["payload"]
                ptype = payload.get("type")
                
                if ptype == "message" and payload.get("role") == "assistant":
                    content = payload.get("content", [])
                    if content and content[0].get("type") == "output_text":
                        text = content[0].get("text", "").strip()
                        if text:
                            events.append({
                                "kind": "fixed",
                                "text": f"✦ {text}",
                                "source_id": f"thought:codex:✦ {text}"
                            })
                elif ptype == "custom_tool_call":
                    name = payload.get("name", "")
                    inp = payload.get("input", "")
                    if name:
                        events.append({
                            "kind": "fixed",
                            "text": f"Ran {name} {inp}",
                            "source_id": f"tool:codex:Ran {name} {inp}"
                        })
                elif ptype == "function_call":
                    name = payload.get("name", "")
                    args = payload.get("arguments", "")
                    if name:
                        events.append({
                            "kind": "fixed",
                            "text": f"Ran {name} {args}",
                            "source_id": f"tool:codex:Ran {name} {args}"
                        })
        return _pane_runtime_gemini_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native codex log {filepath}: {e}")
        return None


def _parse_cursor_jsonl_runtime(filepath: str, limit: int) -> list[dict] | None:
    """Extract recent tool_use events from a cursor-tracked JSONL for runtime display.

    Reads the tail of *filepath* (the same file the message syncer tracks)
    and returns tool-call events formatted for the thinking-indicator overlay.
    Works for Claude, Cursor, and Copilot JSONL formats.
    """
    try:
        tail_bytes = 32_768
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - tail_bytes)
            f.seek(start)
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        if start > 0 and lines:
            lines = lines[1:]  # first line likely truncated

        events: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # --- Claude format ---
            if entry.get("type") == "assistant":
                msg = entry.get("message")
                if not isinstance(msg, dict):
                    continue
                for c in (msg.get("content") or []):
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        name = c.get("name", "tool")
                        inp = c.get("input") or {}
                        # Build a short summary from the input
                        summary = ""
                        if isinstance(inp, dict):
                            for key in ("command", "file_path", "pattern", "query", "prompt", "description"):
                                v = inp.get(key)
                                if v and isinstance(v, str):
                                    summary = v[:80]
                                    break
                        display = f"{name}({summary})" if summary else name
                        events.append({
                            "kind": "fixed",
                            "text": display,
                            "source_id": f"tool:{name}:{summary[:40]}",
                        })

            # --- Copilot format ---
            if entry.get("type") == "tool.execution_start":
                data = entry.get("data") or {}
                name = data.get("toolName", "tool")
                args = data.get("arguments") or {}
                summary = ""
                if isinstance(args, dict):
                    for key in ("command", "path", "query", "pattern", "description"):
                        v = args.get(key)
                        if v and isinstance(v, str):
                            summary = v[:80]
                            break
                display = f"{name}({summary})" if summary else name
                events.append({
                    "kind": "fixed",
                    "text": display,
                    "source_id": f"tool:{name}:{summary[:40]}",
                })
            if entry.get("type") == "assistant.message":
                data = entry.get("data") or {}
                for tr in (data.get("toolRequests") or []):
                    if not isinstance(tr, dict):
                        continue
                    name = tr.get("name", "tool")
                    args = tr.get("arguments") or {}
                    summary = ""
                    if isinstance(args, dict):
                        for key in ("command", "path", "query", "pattern", "description"):
                            v = args.get(key)
                            if v and isinstance(v, str):
                                summary = v[:80]
                                break
                    display = f"{name}({summary})" if summary else name
                    events.append({
                        "kind": "fixed",
                        "text": display,
                        "source_id": f"tool:{name}:{summary[:40]}",
                    })

            # --- Cursor format (same as Claude but role-based) ---
            if entry.get("role") == "assistant":
                msg = entry.get("message")
                if not isinstance(msg, dict):
                    continue
                for c in (msg.get("content") or []):
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        name = c.get("name", "tool")
                        inp = c.get("input") or {}
                        summary = ""
                        if isinstance(inp, dict):
                            for key in ("command", "path", "query", "pattern", "description"):
                                v = inp.get(key)
                                if v and isinstance(v, str):
                                    summary = v[:80]
                                    break
                        display = f"{name}({summary})" if summary else name
                        events.append({
                            "kind": "fixed",
                            "text": display,
                            "source_id": f"tool:{name}:{summary[:40]}",
                        })

        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse cursor JSONL runtime {filepath}: {e}")
        return None


def _parse_native_claude_log(filepath: str, limit: int) -> list[dict] | None:
    """Parse Claude telemetry JSON log."""
    try:
        # Claude telemetry JSON files are a series of JSON objects, one per line.
        events = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                event_data = data.get("event_data", {})
                event_name = event_data.get("event_name", "")
                
                if event_name == "tengu_tool_call":
                    meta_str = event_data.get("additional_metadata", "{}")
                    try:
                        meta = json.loads(meta_str)
                    except:
                        meta = {}
                    tool_name = meta.get("tool_name", "tool")
                    tool_input = meta.get("tool_input", "")
                    events.append({
                        "kind": "fixed",
                        "text": f"Ran {tool_name} {tool_input}",
                        "source_id": f"tool:claude:Ran {tool_name} {tool_input}"
                    })
                # Note: Claude's thoughts are not usually in telemetry, they are in history.jsonl.
                # For pure tool tracking, telemetry works well. For thoughts, we might miss them here.
                # In this fallback, we just return the tool events.
        
        # Tag occurrences
        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native claude log {filepath}: {e}")
        return None

def _parse_native_gemini_log(session_name: str, repo_root: Path | str, agent: str, limit: int) -> list[dict] | None:
    """Parse Gemini wrapper normalized events."""
    try:
        log_dir = Path(repo_root) / "logs" / "multiagent" / "normalized-events" / "gemini-direct"
        if not log_dir.exists():
            return None

        candidates = sorted(log_dir.glob("*.jsonl"), key=os.path.getmtime)
        filepath = None
        for cand in reversed(candidates):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    first_line = f.readline()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("session") == session_name and data.get("sender") == agent:
                            filepath = cand
                            break
            except Exception:
                pass
            
        if not filepath:
            return None
            
        events = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "thought":
                    text = str(data.get("text") or "").strip()
                    events.append({
                        "kind": "fixed",
                        "text": f"✦ {text}",
                        "source_id": f"thought:gemini:✦ {text}"
                    })
                elif data.get("type") == "tool":
                    name = str(data.get("name") or "").strip()
                    args = str(data.get("args") or "").strip()
                    events.append({
                        "kind": "fixed",
                        "text": f"Ran {name} {args}",
                        "source_id": f"tool:gemini:Ran {name} {args}"
                    })
        return _pane_runtime_gemini_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native gemini log: {e}")
        return None



def _pane_runtime_new_events(previous: list[dict], current: list[dict]) -> list[dict]:
    if not current:
        return []
    prev_ids = [str((item or {}).get("source_id") or "") for item in (previous or [])]
    cur_ids = [str((item or {}).get("source_id") or "") for item in current]
    max_overlap = min(len(prev_ids), len(cur_ids))
    for overlap in range(max_overlap, 0, -1):
        if prev_ids[-overlap:] == cur_ids[:overlap]:
            return current[overlap:]
    return [] if prev_ids == cur_ids else current


def _agent_markdown_selectors(*suffixes: str, prefix: str = "") -> str:
    """Generate .message.{agent} .md-body selectors for the given suffixes."""
    parts = []
    suffix_list = suffixes or ("",)
    for name in ALL_AGENT_NAMES:
        base = f'    {prefix}.message.{name} .md-body'
        for suffix in suffix_list:
            parts.append(f"{base}{suffix}")
    return ",\n".join(parts)

# Viewport split for bold_mode_mobile (narrow) vs bold_mode_desktop (wide).
# Intentionally below typical tablet width so “mobile” bold applies to phone-sized viewports only.
BOLD_MODE_VIEWPORT_MAX_PX = 480


def _chat_bold_mode_rules_block() -> str:
    """CSS rules that make message / thinking text bold; wrapped in @media by caller."""
    return f"""
    .message.user .md-body,
    .message.user .md-body p,
    .message.user .md-body li,
    .message.user .md-body li p,
    .message.user .md-body blockquote,
    .message.user .md-body blockquote p,
    {_agent_markdown_selectors("", " p", " li", " li p", " blockquote", " blockquote p")} {{
      font-weight: 620 !important;
      font-variation-settings: normal !important;
      font-synthesis: weight !important;
      font-synthesis-weight: auto !important;
      -webkit-font-smoothing: antialiased;
    }}
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4,
    {_agent_markdown_selectors(" h1", " h2", " h3", " h4")} {{
      font-weight: 700 !important;
      font-variation-settings: normal !important;
      font-synthesis: weight !important;
      font-synthesis-weight: auto !important;
      -webkit-font-smoothing: antialiased;
    }}
    .message-thinking-container,
    .message-thinking-container .message-thinking-label,
    .message-thinking-container .message-thinking-label-primary,
    .message-thinking-container .message-thinking-runtime-line,
    .message-thinking-container .message-thinking-label-live,
    .message-thinking-container .message-thinking-label-preview,
    .camera-mode-thinking {{
      font-weight: 620 !important;
      font-variation-settings: normal !important;
      font-synthesis: weight !important;
      font-synthesis-weight: auto !important;
      -webkit-font-smoothing: antialiased;
    }}
    .message-thinking-runtime-keyword {{
      font-weight: 700 !important;
      font-variation-settings: normal !important;
      font-synthesis: weight !important;
      font-synthesis-weight: auto !important;
      -webkit-font-smoothing: antialiased;
    }}
    """


def _bh_agent_detail_selectors(prefix: str = "") -> str:
    """Generate .message.{agent} .md-body {p,li,h1..h4,blockquote} selectors."""
    return _agent_markdown_selectors(
        " p",
        " li",
        " h1",
        " h2",
        " h3",
        " h4",
        " blockquote",
        prefix=prefix,
    )
from .state_core import update_thinking_totals_from_statuses as update_shared_thinking_totals_from_statuses


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
        candidate = str(Path(path))
        return candidate in self._collect_global_native_log_claims()

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

    def _cursor_transcript_roots(self, workspace: str) -> list[Path]:
        slug_candidates: list[str] = []
        seen_slugs: set[str] = set()

        def _append_slug_from_path(path_value: str) -> None:
            slug = str(path_value).replace("/", "-").lstrip("-")
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                slug_candidates.append(slug)

        _append_slug_from_path(workspace)
        git_root = self._workspace_git_root(workspace)
        if git_root:
            _append_slug_from_path(git_root)

        roots: list[Path] = []
        for slug in slug_candidates:
            root = Path.home() / ".cursor" / "projects" / slug / "agent-transcripts"
            if root.exists():
                roots.append(root)
        return roots

    def maybe_heartbeat_sync_state(self, *, interval_seconds: float = 30.0) -> None:
        interval = max(1.0, float(interval_seconds))
        now = time.time()
        if now - self._last_sync_state_heartbeat < interval:
            return
        self.save_sync_state()

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
            entry["first_seen_ts"] = self._agent_first_seen_ts.get(agent)
            result.append(entry)
        return result

    def _parse_opencode_runtime(self, agent: str, limit: int) -> list[dict] | None:
        """Extract recent tool events from OpenCode's SQLite DB for runtime display."""
        try:
            import sqlite3 as _sqlite3
            db_path = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
            if not db_path.exists():
                return None
            oc = self._opencode_cursors.get(agent)
            if not oc or not oc.session_id:
                return None
            conn = _sqlite3.connect(str(db_path), timeout=1)
            cur = conn.cursor()
            cur.execute(
                "SELECT p.data FROM part p JOIN message m ON p.message_id = m.id "
                "WHERE m.session_id = ? ORDER BY p.time_created DESC LIMIT 30",
                (oc.session_id,),
            )
            events: list[dict] = []
            for (pd,) in cur.fetchall():
                pdata = json.loads(pd)
                if pdata.get("type") != "tool":
                    continue
                tool_name = pdata.get("tool", "tool")
                state = pdata.get("state") or {}
                inp = state.get("input") or {}
                summary = ""
                if isinstance(inp, dict):
                    for key in ("command", "path", "query", "pattern", "description"):
                        v = inp.get(key)
                        if v and isinstance(v, str):
                            summary = v[:80]
                            break
                display = f"{tool_name}({summary})" if summary else tool_name
                events.append({
                    "kind": "fixed",
                    "text": display,
                    "source_id": f"tool:{tool_name}:{summary[:40]}",
                })
            conn.close()
            events.reverse()  # oldest first
            return _pane_runtime_with_occurrence_ids(events, limit=limit)
        except Exception as e:
            logging.error(f"Failed to parse OpenCode runtime for {agent}: {e}")
            return None

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
        text = str(message or "")
        return [match.strip() for match in re.findall(r"\[Attached:\s*([^\]]+)\]", text)]

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
        summary = dict(entry)
        message = str(summary.get("message") or "")
        attached_paths = self.attachment_paths(message)
        if attached_paths:
            summary["attached_paths"] = attached_paths
        body_only = re.sub(r"(?:\n)?\[Attached:\s*[^\]]+\]", "", message).strip()
        heavy_code = "```" in body_only and len(body_only) > self.PUBLIC_LIGHT_CODE_THRESHOLD
        truncated = len(body_only) > self.PUBLIC_LIGHT_MESSAGE_CHAR_LIMIT
        if not truncated and not heavy_code:
            return summary
        preview = body_only[:self.PUBLIC_LIGHT_MESSAGE_CHAR_LIMIT].rstrip()
        notes = ["[Public preview truncated. Load full message.]"]
        if attached_paths:
            preview_paths = attached_paths[:self.PUBLIC_LIGHT_ATTACHMENT_PREVIEW_LIMIT]
            notes.extend([f"[Attached: {path}]" for path in preview_paths])
            remaining = len(attached_paths) - len(preview_paths)
            if remaining > 0:
                notes.append(f"(+{remaining} more attachments)")
        summary["message"] = (preview + ("\n\n" if preview else "") + "\n".join(notes)).strip()
        summary["deferred_body"] = True
        summary["message_length"] = len(message)
        return summary

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
        return json.dumps(
            {
                **meta,
                "filter": self.filter_agent or "all",
                "follow": self.follow_mode,
                "targets": self.active_agents(),
                "has_older": has_older,
                "light_mode": bool(light_mode),
                "entries": entries,
            },
            ensure_ascii=True,
        ).encode("utf-8")

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

    def agent_launch_cmd(self, agent_name: str) -> str:
        bin_dir = Path(self.agent_send_path).parent
        agent_exec_path = Path(self.resolve_agent_executable(agent_name))
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
        agent_exec_path = Path(self.resolve_agent_executable(agent_name))
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
            return self.agent_launch_cmd(agent_name)
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

    @staticmethod
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
        home = Path.home()
        # Explicit fallback paths from registry
        if adef:
            for p in adef.fallback_paths:
                candidate = Path(p).expanduser()
                if candidate.is_file():
                    return str(candidate)
        # NVM fallback for npm-installed agents
        if adef and adef.fallback_nvm:
            nvm_bin = Path(os.environ.get("NVM_BIN", "")).expanduser()
            nvm_candidates: list[Path] = []
            if nvm_bin.is_dir():
                nvm_candidates.append(nvm_bin / exe_name)
            nvm_candidates.extend(
                sorted(
                    (home / ".nvm" / "versions" / "node").glob(f"*/bin/{exe_name}"),
                    reverse=True,
                )
            )
            for candidate in nvm_candidates:
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
        subprocess.run([*self.tmux_prefix, "select-pane", "-t", pane_id, "-T", agent_name], capture_output=True, check=False)
        return True, pane_id

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
                try:
                    for agent in [item.strip() for item in target.split(",") if item.strip()]:
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
            return 400, {"ok": False, "error": "target is required"}
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
        if silent or raw:
            try:
                for idx, agent in enumerate(delivery_targets):
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
                    buf_name = f"direct_{agent}_{os.getpid()}_{idx}"
                    subprocess.run(
                        [*self.tmux_prefix, "load-buffer", "-b", buf_name, "-"],
                        input=message + "\n",
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    subprocess.run([*self.tmux_prefix, "paste-buffer", "-b", buf_name, "-d", "-t", pane_id], capture_output=True, check=False)
                    time.sleep(0.3)
                    subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"], capture_output=True, check=False)
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                return 500, {"ok": False, "error": str(exc)}
            return 200, {"ok": True, "raw": bool(raw)}
        payload = f"[From: User]\n{message}"
        successful_targets: list[str] = []
        failed_targets: list[str] = []
        try:
            for idx, agent in enumerate(delivery_targets):
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
                buf_name = f"user_send_{agent}_{os.getpid()}_{idx}"
                load_res = subprocess.run(
                    [*self.tmux_prefix, "load-buffer", "-b", buf_name, "-"],
                    input=payload + "\n",
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if load_res.returncode != 0:
                    failed_targets.append(agent)
                    continue
                paste_res = subprocess.run(
                    [*self.tmux_prefix, "paste-buffer", "-b", buf_name, "-d", "-t", pane_id],
                    capture_output=True,
                    check=False,
                )
                if paste_res.returncode != 0:
                    failed_targets.append(agent)
                    continue
                time.sleep(0.3)
                enter_res = subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"], capture_output=True, check=False)
                if enter_res.returncode != 0:
                    failed_targets.append(agent)
                    continue
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

    def _sync_codex_assistant_messages(self, agent: str, native_log_path: str) -> None:
        try:
            file_size = os.path.getsize(native_log_path)
            prev_cursor = self._codex_cursors.get(agent)
            offset = _advance_native_cursor(self._codex_cursors, agent, native_log_path, file_size)
            if offset is None:
                if _cursor_binding_changed(prev_cursor, self._codex_cursors.get(agent)):
                    self.save_sync_state()
                return

            with open(native_log_path, "r", encoding="utf-8") as f:
                f.seek(offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    display = ""
                    entry_type = entry.get("type", "")
                    if entry_type == "response_item":
                        payload = entry.get("payload", {})
                        if payload.get("role") != "assistant":
                            continue
                        content = payload.get("content", [])
                        texts = []
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict):
                                    t = c.get("text") or c.get("output_text", {}).get("text", "")
                                    if t and str(t).strip():
                                        texts.append(str(t).strip())
                        if not texts:
                            continue
                        display = "\n".join(texts)
                    elif entry_type == "event_msg":
                        payload = entry.get("payload", {})
                        if payload.get("type") != "error":
                            continue
                        display = str(payload.get("message") or "").strip()
                        if not display:
                            continue
                    else:
                        continue

                    src_ts = str(entry.get("timestamp") or "")
                    key = f"codex:{agent}:{src_ts}:{display}"
                    msg_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
                    if msg_id in self._synced_msg_ids:
                        continue

                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    jsonl_entry = {
                        "timestamp": timestamp,
                        "session": self.session_name,
                        "sender": agent,
                        "targets": ["user"],
                        "message": f"[From: {agent}]\n{display}",
                        "msg_id": msg_id,
                    }
                    append_jsonl_entry(self.index_path, jsonl_entry)
                    self._synced_msg_ids.add(msg_id)

            self._codex_cursors[agent] = NativeLogCursor(path=native_log_path, offset=file_size)
            self.save_sync_state()
        except Exception as exc:
            logging.error(f"Failed to sync Codex message for {agent}: {exc}")

    def _sync_cursor_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        try:
            workspace = self.workspace or ""
            if not workspace:
                return
            transcript_roots = self._cursor_transcript_roots(workspace)
            if not transcript_roots:
                return
            transcript_path = str(Path(native_log_path)) if native_log_path else ""
            if not transcript_path:
                jsonl_candidates: list[Path] = []
                for root in transcript_roots:
                    jsonl_candidates.extend(root.glob("*/*.jsonl"))
                min_mtime = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                picked = _pick_latest_unclaimed_for_agent(
                    jsonl_candidates,
                    self._cursor_cursors,
                    agent,
                    min_mtime=min_mtime,
                    exclude_paths=set(self._collect_global_native_log_claims().keys()),
                )
                if picked is None:
                    return
                transcript_path = str(picked)
            elif self._is_globally_claimed_path(transcript_path):
                return
            if not os.path.exists(transcript_path):
                return
            file_size = os.path.getsize(transcript_path)
            prev_cursor = self._cursor_cursors.get(agent)
            offset = _advance_native_cursor(self._cursor_cursors, agent, transcript_path, file_size)
            if offset is None:
                if _cursor_binding_changed(prev_cursor, self._cursor_cursors.get(agent)):
                    self.save_sync_state()
                return

            with open(transcript_path, "r", encoding="utf-8") as f:
                f.seek(offset)
                while True:
                    line_start = f.tell()
                    line = f.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    display = ""
                    role = entry.get("role", "")
                    if role == "assistant":
                        msg_obj = entry.get("message") if isinstance(entry, dict) else {}
                        if not isinstance(msg_obj, dict):
                            continue
                        content = msg_obj.get("content", [])
                        if isinstance(content, str) and content.strip():
                            display = content.strip()
                        elif isinstance(content, list):
                            texts = []
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    text = str(c.get("text") or "").strip()
                                    if text:
                                        texts.append(text)
                            if not texts:
                                continue
                            display = "\n".join(texts)
                    elif role == "system":
                        # Capture rate-limit, error, and other system messages
                        msg_obj = entry.get("message") if isinstance(entry, dict) else {}
                        if isinstance(msg_obj, dict):
                            content = msg_obj.get("content", "")
                            if isinstance(content, str) and content.strip():
                                display = content.strip()
                        elif isinstance(msg_obj, str) and msg_obj.strip():
                            display = msg_obj.strip()

                    if not display:
                        continue

                    display = normalize_cursor_plaintext_for_index(display)
                    if not display:
                        continue

                    key = f"cursor:{agent}:{transcript_path}:{line_start}:{display}"
                    msg_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
                    if msg_id in self._synced_msg_ids:
                        continue
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    jsonl_entry = {
                        "timestamp": timestamp,
                        "session": self.session_name,
                        "sender": agent,
                        "targets": ["user"],
                        "message": f"[From: {agent}]\n{display}",
                        "msg_id": msg_id,
                    }
                    append_jsonl_entry(self.index_path, jsonl_entry)
                    self._synced_msg_ids.add(msg_id)

            self._cursor_cursors[agent] = NativeLogCursor(path=transcript_path, offset=file_size)
            self.save_sync_state()
        except Exception as exc:
            logging.error(f"Failed to sync Cursor message for {agent}: {exc}")

    def _sync_copilot_assistant_messages(self, agent: str, native_log_path: str) -> None:
        try:
            file_size = os.path.getsize(native_log_path)
            prev_cursor = self._copilot_cursors.get(agent)
            offset = _advance_native_cursor(self._copilot_cursors, agent, native_log_path, file_size)
            if offset is None:
                if _cursor_binding_changed(prev_cursor, self._copilot_cursors.get(agent)):
                    self.save_sync_state()
                return

            with open(native_log_path, "r", encoding="utf-8") as f:
                f.seek(offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    etype = str(entry.get("type") or "").strip()
                    if etype != "assistant.message":
                        continue
                    data = entry.get("data") if isinstance(entry, dict) else {}
                    if not isinstance(data, dict):
                        data = {}
                    content = str(data.get("content") or "").strip()
                    if not content:
                        continue
                    msg_id = str(data.get("messageId") or entry.get("id") or "").strip()
                    if msg_id and msg_id in self._synced_msg_ids:
                        continue
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    jsonl_entry = {
                        "timestamp": timestamp,
                        "session": self.session_name,
                        "sender": agent,
                        "targets": ["user"],
                        "message": f"[From: {agent}]\n{content}",
                        "msg_id": msg_id or uuid.uuid4().hex[:12],
                    }
                    append_jsonl_entry(self.index_path, jsonl_entry)
                    if msg_id:
                        self._synced_msg_ids.add(msg_id)

            self._copilot_cursors[agent] = NativeLogCursor(path=native_log_path, offset=file_size)
            self.save_sync_state()
        except Exception as exc:
            logging.error(f"Failed to sync Copilot message for {agent}: {exc}", exc_info=True)

    def _sync_claude_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        try:
            workspace_escaped = "-" + self.workspace.replace("/", "-").lstrip("-")
            workspace_dir = Path.home() / ".claude" / "projects" / workspace_escaped
            if not workspace_dir.exists():
                return
            session_path_str = str(Path(native_log_path)) if native_log_path else ""
            if not session_path_str:
                jsonl_candidates = list(workspace_dir.glob("*.jsonl"))
                min_mtime = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                session_path = _pick_latest_unclaimed_for_agent(
                    jsonl_candidates,
                    self._claude_cursors,
                    agent,
                    min_mtime=min_mtime,
                    exclude_paths=set(self._collect_global_native_log_claims().keys()),
                )
                if session_path is None:
                    return
                session_path_str = str(session_path)
            elif self._is_globally_claimed_path(session_path_str):
                return
            if not os.path.exists(session_path_str):
                return
            file_size = os.path.getsize(session_path_str)
            prev_cursor = self._claude_cursors.get(agent)
            offset = _advance_native_cursor(self._claude_cursors, agent, session_path_str, file_size)
            if offset is None:
                if _cursor_binding_changed(prev_cursor, self._claude_cursors.get(agent)):
                    self.save_sync_state()
                return

            with open(session_path_str, "r", encoding="utf-8") as f:
                f.seek(offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("type") != "assistant":
                        continue
                    msg = entry.get("message") if isinstance(entry, dict) else {}
                    if not isinstance(msg, dict):
                        continue
                    content = msg.get("content", [])
                    if not isinstance(content, list):
                        continue
                    texts = []
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text = str(c.get("text") or "").strip()
                            if text:
                                texts.append(text)
                    if not texts:
                        continue
                    display = "\n".join(texts)
                    msg_id = str(entry.get("uuid") or entry.get("id") or "")[:12]
                    if not msg_id:
                        msg_id = uuid.uuid4().hex[:12]
                    if msg_id in self._synced_msg_ids:
                        continue
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    jsonl_entry = {
                        "timestamp": timestamp,
                        "session": self.session_name,
                        "sender": agent,
                        "targets": ["user"],
                        "message": f"[From: {agent}]\n{display}",
                        "msg_id": msg_id,
                    }
                    append_jsonl_entry(self.index_path, jsonl_entry)
                    self._synced_msg_ids.add(msg_id)

            self._claude_cursors[agent] = NativeLogCursor(path=session_path_str, offset=file_size)
            self.save_sync_state()
        except Exception as exc:
            logging.error(f"Failed to sync Claude message for {agent}: {exc}", exc_info=True)

    def _sync_qwen_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        """Append only the newly appended tail of the Qwen chat JSONL.

        The active chat file is picked via claim-aware latest-mtime selection
        so multiple qwen instances in the same workspace get bound to their
        own files rather than racing for the newest one.
        """
        try:
            workspace_slug = "-" + (self.workspace or "").replace("/", "-").lstrip("-")
            qwen_chats_dir = Path.home() / ".qwen" / "projects" / workspace_slug / "chats"
            if not qwen_chats_dir.exists():
                return
            chat_path_str = str(Path(native_log_path)) if native_log_path else ""
            if not chat_path_str:
                chat_candidates = list(qwen_chats_dir.glob("*.jsonl"))
                min_mtime = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                picked = _pick_latest_unclaimed_for_agent(
                    chat_candidates,
                    self._qwen_cursors,
                    agent,
                    min_mtime=min_mtime,
                    exclude_paths=set(self._collect_global_native_log_claims().keys()),
                )
                if picked is None:
                    return
                chat_path_str = str(picked)
            elif self._is_globally_claimed_path(chat_path_str):
                return
            if not os.path.exists(chat_path_str):
                return
            file_size = os.path.getsize(chat_path_str)
            prev_cursor = self._qwen_cursors.get(agent)
            offset = _advance_native_cursor(self._qwen_cursors, agent, chat_path_str, file_size)
            if offset is None:
                if _cursor_binding_changed(prev_cursor, self._qwen_cursors.get(agent)):
                    self.save_sync_state()
                return

            with open(chat_path_str, "r", encoding="utf-8") as f:
                f.seek(offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if str(entry.get("type") or "").strip() != "assistant":
                        continue
                    msg_obj = entry.get("message") if isinstance(entry, dict) else {}
                    if not isinstance(msg_obj, dict):
                        continue
                    parts = msg_obj.get("parts") or []
                    texts = []
                    for part in parts:
                        if isinstance(part, dict) and "text" in part and not part.get("thought"):
                            text = str(part.get("text") or "").strip()
                            if text:
                                texts.append(text)
                    if not texts:
                        continue
                    content = "\n".join(texts)
                    msg_id = str(entry.get("uuid") or "").strip()
                    if msg_id and msg_id in self._synced_msg_ids:
                        continue
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    jsonl_entry = {
                        "timestamp": timestamp,
                        "session": self.session_name,
                        "sender": agent,
                        "targets": ["user"],
                        "message": f"[From: {agent}]\n{content}",
                        "msg_id": msg_id or uuid.uuid4().hex[:12],
                    }
                    append_jsonl_entry(self.index_path, jsonl_entry)
                    if msg_id:
                        self._synced_msg_ids.add(msg_id)

            self._qwen_cursors[agent] = NativeLogCursor(path=chat_path_str, offset=file_size)
            self.save_sync_state()
        except Exception as exc:
            logging.error(f"Failed to sync Qwen message for {agent}: {exc}", exc_info=True)

    def _sync_gemini_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        """Append new Gemini assistant messages to the chat index.

        Unlike JSONL-based logs, Gemini rewrites the entire session file on
        each turn, so the cursor's ``offset`` is used only as a change
        detector: when the on-disk size differs from the cursor's recorded
        size, we re-parse the whole JSON and rely on ``_synced_msg_ids`` for
        deduplication. The path-binding logic still guards against flooding
        when the "latest" file switches (new session or another agent).
        """
        try:
            project_name = os.path.basename(self.workspace)
            chats_dir = Path.home() / ".gemini" / "tmp" / project_name / "chats"
            if not chats_dir.exists():
                return
            session_path_str = str(Path(native_log_path)) if native_log_path else ""
            picked = None
            if not session_path_str:
                candidates = list(chats_dir.glob("session-*.json"))
                min_mtime = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                picked = _pick_latest_unclaimed_for_agent(
                    candidates,
                    self._gemini_cursors,
                    agent,
                    min_mtime=min_mtime,
                    exclude_paths=set(self._collect_global_native_log_claims().keys()),
                )
                if picked is None:
                    return
                session_path_str = str(picked)
            elif self._is_globally_claimed_path(session_path_str):
                return
            if not picked:
                picked = Path(session_path_str)
            if not os.path.exists(session_path_str):
                return
            file_size = picked.stat().st_size
            prev_cursor = self._gemini_cursors.get(agent)
            offset = _advance_native_cursor(self._gemini_cursors, agent, session_path_str, file_size)
            if offset is None:
                if _cursor_binding_changed(prev_cursor, self._gemini_cursors.get(agent)):
                    self.save_sync_state()
                return

            with open(session_path_str, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    return

            messages = data.get("messages", []) if isinstance(data, dict) else []
            for m in messages:
                if m.get("type") != "gemini":
                    continue
                msg_id = str(m.get("id") or "")[:12]
                if not msg_id:
                    continue

                content = m.get("content", [])
                texts = []
                if isinstance(content, str):
                    # Simple text response (most common case)
                    if content.strip():
                        texts.append(content)
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("text"):
                            text = str(c.get("text")).strip()
                            if text:
                                texts.append(text)

                if not texts:
                    # Gemini writes empty placeholder first, updates later.
                    # Don't mark as synced so we pick it up on next poll.
                    continue

                if msg_id in self._synced_msg_ids:
                    continue

                display = "\n".join(texts)
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                jsonl_entry = {
                    "timestamp": timestamp,
                    "session": self.session_name,
                    "sender": agent,
                    "targets": ["user"],
                    "message": f"[From: {agent}]\n{display}",
                    "msg_id": msg_id,
                }
                append_jsonl_entry(self.index_path, jsonl_entry)
                self._synced_msg_ids.add(msg_id)

            self._gemini_cursors[agent] = NativeLogCursor(path=session_path_str, offset=file_size)
            self.save_sync_state()
        except Exception as exc:
            logging.error(f"Failed to sync Gemini message for {agent}: {exc}", exc_info=True)

    def _sync_opencode_assistant_messages(self, agent: str) -> None:
        """Sync OpenCode assistant messages from its SQLite DB to JSONL.

        OpenCode stores conversations in ``~/.local/share/opencode/opencode.db``
        with ``message`` and ``part`` tables. We find the most recent session
        matching the workspace directory, then sync new assistant messages
        (text parts) since the last synced message ID.
        """
        try:
            db_path = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
            if not db_path.exists():
                return

            import sqlite3

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            # Sessions already claimed by *other* opencode agents must not
            # be reassigned to this agent, otherwise two opencode instances
            # in the same workspace would double-sync the same conversation.
            claimed_session_ids = {
                c.session_id
                for other_agent, c in self._opencode_cursors.items()
                if other_agent != agent and c.session_id
            }

            prev_cursor = self._opencode_cursors.get(agent)
            prev_session_id = prev_cursor.session_id if prev_cursor else ""
            last_msg_id = prev_cursor.last_msg_id if prev_cursor else ""

            # Always pick the most-recently-updated workspace session that
            # isn't claimed by another agent. OpenCode bumps ``time_updated``
            # on every write, so the "active" session for this CLI naturally
            # floats to the top. If the CLI has moved on from ``prev_session_id``
            # (e.g. user started a new conversation) we want to follow it —
            # sticking to prev indefinitely caused the "agent replied but
            # nothing shows up in chat" bug.
            cur.execute(
                """
                SELECT s.id FROM session s
                WHERE s.directory = ?
                ORDER BY s.time_updated DESC
                """,
                (self.workspace,),
            )
            session_id = ""
            for (candidate_id,) in cur.fetchall():
                if candidate_id == prev_session_id:
                    # Our existing claim is still the most-recent unclaimed
                    # one (nothing newer has appeared) — keep it.
                    session_id = candidate_id
                    break
                if candidate_id not in claimed_session_ids:
                    session_id = candidate_id
                    break

            if not session_id:
                conn.close()
                return

            # Build WHERE clause for new messages
            if last_msg_id and prev_session_id == session_id:
                # Continuing the same session: pick up messages after the last
                # one we synced.
                where_clause = "AND m.time_created > (SELECT time_created FROM message WHERE id = ?)"
                anchor_value = last_msg_id
            else:
                # New/switched session, or same session but no messages synced
                # yet: use first_seen_ts as the boundary so pre-existing
                # history isn't re-ingested and the message that *triggered*
                # the session switch (e.g. the pong reply) is included.
                first_seen_ms = int(self._first_seen_for_agent(agent) * 1000)
                where_clause = "AND m.time_created >= ?"
                anchor_value = first_seen_ms

            # Get assistant messages with their parts
            query = f"""
                SELECT m.id, m.time_created, m.data
                FROM message m
                WHERE m.session_id = ? {where_clause}
                ORDER BY m.time_created ASC
            """
            params: list = [session_id]
            if where_clause and anchor_value:
                params.append(anchor_value)

            cur.execute(query, params)
            new_last_msg_id = last_msg_id
            synced_count = 0

            for msg_id, ts_ms, msg_data in cur.fetchall():
                obj = json.loads(msg_data)
                if obj.get("role") != "assistant":
                    continue
                finish = obj.get("finish", "")

                # Extract text from parts
                cur2 = conn.cursor()
                cur2.execute(
                    "SELECT p.data FROM part p WHERE p.message_id = ? ORDER BY p.time_created ASC",
                    (msg_id,),
                )

                texts = []
                tool_calls = []
                error_parts = []
                for (pd,) in cur2.fetchall():
                    pdata = json.loads(pd)
                    pt = pdata.get("type", "")
                    if pt == "text":
                        t = pdata.get("text", "").strip()
                        if t:
                            texts.append(t)
                    elif pt == "tool-call":
                        tool_calls.append(pdata.get("name", "?"))
                    elif pt == "tool-result" and pdata.get("isError"):
                        err_name = pdata.get("name", "?")
                        err_content = str(pdata.get("content", ""))[:200]
                        error_parts.append(f"{err_name}: {err_content}")

                # Skip messages with no text and no errors
                if not texts and not error_parts:
                    new_last_msg_id = msg_id
                    continue

                display = "\n".join(texts) if texts else ""
                if error_parts:
                    error_text = "Errors: " + " | ".join(error_parts)
                    display = f"{display}\n\n{error_text}".strip() if display else error_text

                if not display:
                    new_last_msg_id = msg_id
                    continue

                # Deduplicate
                sync_key = f"opencode:{agent}:{msg_id}:{display[:100]}"
                msg_id_hash = hashlib.sha256(sync_key.encode("utf-8")).hexdigest()[:12]
                if msg_id_hash in self._synced_msg_ids:
                    new_last_msg_id = msg_id
                    continue

                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                jsonl_entry = {
                    "timestamp": timestamp,
                    "session": self.session_name,
                    "sender": agent,
                    "targets": ["user"],
                    "message": f"[From: {agent}]\n{display}",
                    "msg_id": msg_id_hash,
                }
                append_jsonl_entry(self.index_path, jsonl_entry)
                self._synced_msg_ids.add(msg_id_hash)
                new_last_msg_id = msg_id
                synced_count += 1

            conn.close()

            # Always record the claim on the session_id (even when the session
            # has no messages yet) so another opencode agent added immediately
            # afterward picks a *different* session instead of double-syncing
            # this one.
            if new_last_msg_id or prev_session_id != session_id:
                self._opencode_cursors[agent] = OpenCodeCursor(
                    session_id=session_id,
                    last_msg_id=new_last_msg_id or "",
                )
                self.save_sync_state()
        except Exception as exc:
            logging.error(f"Failed to sync OpenCode message for {agent}: {exc}", exc_info=True)

    def agent_statuses(self) -> dict[str, str]:
        result = {}
        # Refresh target list from tmux environment to pick up newly added agents
        active_instances = self.active_agents()
        for agent in active_instances:
            pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
            try:
                r = subprocess.run(
                    [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                line = r.stdout.strip()
                if r.returncode != 0 or "=" not in line:
                    result[agent] = "offline"
                    self._pane_runtime_matches.pop(agent, None)
                    self._pane_runtime_state.pop(agent, None)
                    continue
                pane_id = line.split("=", 1)[1]
                dead = subprocess.run(
                    [*self.tmux_prefix, "display-message", "-p", "-t", pane_id, "#{pane_dead}"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                ).stdout.strip()
                if dead == "1":
                    result[agent] = "dead"
                    self._pane_snapshots.pop(pane_id, None)
                    self._pane_last_change.pop(pane_id, None)
                    self._pane_runtime_matches.pop(agent, None)
                    self._pane_runtime_state.pop(agent, None)
                    self._pane_native_log_paths.pop(pane_id, None)
                    continue

                base_name = _agent_base_name(agent)
                runtime_events = None

                # Use cursor-tracked JSONL files for runtime event display.
                # These are the same files the message syncer reads, so the
                # path is already resolved and kept up-to-date.
                cursor_maps: dict[str, dict[str, NativeLogCursor]] = {
                    "claude": self._claude_cursors,
                    "cursor": self._cursor_cursors,
                    "copilot": self._copilot_cursors,
                    "codex": self._codex_cursors,
                    "qwen": self._qwen_cursors,
                }
                cmap = cursor_maps.get(base_name)
                if cmap and agent in cmap:
                    cursor_path = cmap[agent].path
                    if cursor_path and os.path.exists(cursor_path):
                        runtime_events = _parse_cursor_jsonl_runtime(cursor_path, limit=12)

                if base_name == "gemini":
                    runtime_events = _parse_native_gemini_log(self.session_name, self.repo_root, agent, limit=12)

                if base_name == "opencode" and agent in self._opencode_cursors:
                    runtime_events = self._parse_opencode_runtime(agent, limit=12)

                content = subprocess.run(
                    [*self.tmux_prefix, "capture-pane", "-p", "-S", "-80", "-t", pane_id],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                ).stdout

                # Deduplicate consecutive [Thought: true] blocks for Gemini
                if base_name == "gemini":
                    content = _deduplicate_consecutive_thought_blocks(content)

                # Skip top 10 lines for copilot to avoid false running detection from animated UI
                if base_name == "copilot":
                    content_lines = content.splitlines()
                    content = "\n".join(content_lines[10:]) if len(content_lines) > 10 else ""

                if runtime_events is None:
                    # No native event log available: frontend shows the "thinking..." pulse.
                    runtime_events = []


                prev_runtime_events = self._pane_runtime_matches.get(agent, [])
                new_runtime_events = _pane_runtime_new_events(prev_runtime_events, runtime_events)
                self._pane_runtime_matches[agent] = runtime_events
                now = time.monotonic()
                prev = self._pane_snapshots.get(pane_id)
                self._pane_snapshots[pane_id] = content
                if prev is not None and content != prev:
                    self._pane_last_change[pane_id] = now
                    result[agent] = "running"
                else:
                    last_change = self._pane_last_change.get(pane_id, 0.0)
                    result[agent] = "running" if (now - last_change) < self.running_grace_seconds else "idle"
                if result[agent] == "running":
                    state = dict(self._pane_runtime_state.get(agent) or {})
                    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else None
                    current_source_id = str((current_event or {}).get("source_id") or "").strip()
                    if runtime_events:
                        # Only show the single newest event.
                        recent_events = runtime_events[-1:]
                        combined_text = str(recent_events[-1].get("text") or "").strip()
                        latest_event = recent_events[-1]
                        source_id = str(latest_event.get("source_id") or "").strip()
                        if not source_id or source_id != current_source_id:
                            self._pane_runtime_event_seq += 1
                            current_event = {
                                "id": f"{agent}:{self._pane_runtime_event_seq}",
                                "text": combined_text,
                                "source_id": source_id,
                            }
                        else:
                            if current_event:
                                current_event["text"] = combined_text
                    if current_event and str(current_event.get("text") or "").strip():
                        self._pane_runtime_state[agent] = {"current_event": current_event}
                    else:
                        # Keep last known state even when no current event (for idle agents)
                        pass
                else:
                    # Keep last known state for idle agents so the frontend still shows it
                    pass
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                result[agent] = "offline"
        try:
            update_shared_thinking_totals_from_statuses(
                self.repo_root,
                self.session_name,
                self.workspace,
                result,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            pass
        return result

    def agent_runtime_state(self) -> dict[str, dict]:
        result = {}
        for agent, payload in self._pane_runtime_state.items():
            raw_event = (payload or {}).get("current_event")
            if not isinstance(raw_event, dict):
                continue
            event_id = str(raw_event.get("id") or "").strip()
            text = str(raw_event.get("text") or "").rstrip()
            if not event_id or not text:
                continue
            result[agent] = {"current_event": {"id": event_id, "text": text}}
        return result

    def trace_content(self, agent: str, *, tail_lines: int | None = None) -> str:
        """Return tmux pane text. tail_lines: last N rows only (fast); None = full scrollback (heavy)."""
        pane_var = f"MULTIAGENT_PANE_{(agent or '').upper().replace('-', '_')}"
        content_str = ""
        try:
            r = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            line = r.stdout.strip()
            if r.returncode == 0 and "=" in line:
                pane_id = line.split("=", 1)[1]
                if tail_lines is not None:
                    n = max(1, min(int(tail_lines), 10_000))
                    start = f"-{n}"
                    cap_timeout = 3
                else:
                    # Large scrollback (tmux retains up to history-limit lines; see set -g history-limit).
                    start = "-500000"
                    cap_timeout = 8
                raw = subprocess.run(
                    [
                        *self.tmux_prefix,
                        "capture-pane",
                        "-p",
                        "-e",
                        "-S",
                        start,
                        "-t",
                        pane_id,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=cap_timeout,
                    check=False,
                ).stdout
                content_str = "\n".join(l.rstrip() for l in raw.splitlines())
                
                # Deduplicate consecutive [Thought: true] blocks for Gemini
                base_name = _agent_base_name(agent)
                if base_name == "gemini":
                    content_str = _deduplicate_consecutive_thought_blocks(content_str)
            else:
                content_str = "Offline"
        except Exception as e:
            logging.error(f"Unexpected error: {e}", exc_info=True)
            content_str = f"Error: {e}"
        return content_str
