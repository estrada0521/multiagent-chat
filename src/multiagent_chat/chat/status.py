from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import time
from pathlib import Path

from .runtime_format import (
    _deduplicate_consecutive_thought_blocks,
    _pane_runtime_with_occurrence_ids,
)
from .runtime_parse import (
    _parse_cursor_jsonl_runtime,
    _parse_native_codex_log,
    _parse_native_gemini_log,
    _pane_runtime_new_events,
    _runtime_tool_events,
)
from .sync.cursor import NativeLogCursor, _agent_base_name


def parse_opencode_runtime(self, agent: str, limit: int) -> list[dict] | None:
    """Extract recent tool events from OpenCode's SQLite DB for runtime display."""
    try:
        db_path = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
        if not db_path.exists():
            return None
        oc = self._opencode_cursors.get(agent)
        if not oc or not oc.session_id:
            return None
        conn = sqlite3.connect(str(db_path), timeout=1)
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
            events.extend(_runtime_tool_events(tool_name, inp, workspace=self.workspace))
        conn.close()
        events.reverse()  # oldest first
        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse OpenCode runtime for {agent}: {e}")
        return None


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
                self._pane_runtime_run_start_tail.pop(agent, None)
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
                self._pane_runtime_run_start_tail.pop(agent, None)
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
                "qwen": self._qwen_cursors,
            }
            if base_name == "codex" and agent in self._codex_cursors:
                cursor_path = self._codex_cursors[agent].path
                if cursor_path and os.path.exists(cursor_path):
                    runtime_events = _parse_native_codex_log(cursor_path, limit=12, workspace=self.workspace)
            if base_name == "gemini" and agent in self._gemini_cursors:
                cursor_path = self._gemini_cursors[agent].path
                if cursor_path and os.path.exists(cursor_path):
                    runtime_events = _parse_native_gemini_log(cursor_path, limit=12, workspace=self.workspace)
            cmap = cursor_maps.get(base_name)
            if runtime_events is None and cmap and agent in cmap:
                cursor_path = cmap[agent].path
                if cursor_path and os.path.exists(cursor_path):
                    runtime_events = _parse_cursor_jsonl_runtime(cursor_path, limit=12, workspace=self.workspace)

            if base_name == "opencode" and agent in self._opencode_cursors:
                runtime_events = self._parse_opencode_runtime(agent, limit=12)

            if runtime_events is None:
                # No native event log available: frontend shows the "thinking..." pulse.
                runtime_events = []

            prev_runtime_events = self._pane_runtime_matches.get(agent, [])
            new_runtime_events = _pane_runtime_new_events(prev_runtime_events, runtime_events)
            self._pane_runtime_matches[agent] = runtime_events
            now = time.monotonic()

            if base_name in {"claude", "cursor"}:
                last_send = float(self._agent_last_send_ts.get(agent) or 0.0)
                last_done = float(self._agent_last_turn_done_ts.get(agent) or 0.0)
                if last_send > 0.0 and last_done < last_send:
                    result[agent] = "running"
                else:
                    result[agent] = "idle"
            else:
                content = subprocess.run(
                    [*self.tmux_prefix, "capture-pane", "-p", "-S", "-80", "-t", pane_id],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                ).stdout

                if base_name == "gemini":
                    content = _deduplicate_consecutive_thought_blocks(content)

                if base_name == "copilot":
                    content_lines = content.splitlines()
                    content = "\n".join(content_lines[10:]) if len(content_lines) > 10 else ""

                prev = self._pane_snapshots.get(pane_id)
                self._pane_snapshots[pane_id] = content
                if prev is not None and content != prev:
                    self._pane_last_change[pane_id] = now
                    result[agent] = "running"
                else:
                    last_change = self._pane_last_change.get(pane_id, 0.0)
                    result[agent] = "running" if (now - last_change) < self.running_grace_seconds else "idle"

            if result[agent] == "running" and self._pane_last_status.get(agent) != "running":
                self._pane_runtime_state.pop(agent, None)
                if runtime_events:
                    ev = runtime_events[-1]
                    self._pane_runtime_run_start_tail[agent] = (
                        str(ev.get("source_id") or "").strip(),
                        str(ev.get("text") or "").strip(),
                    )
                else:
                    self._pane_runtime_run_start_tail.pop(agent, None)
            self._pane_last_status[agent] = result[agent]

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
                    stale_tail = self._pane_runtime_run_start_tail.get(agent)
                    if stale_tail is not None and (source_id, combined_text) == stale_tail:
                        current_event = None
                    else:
                        if stale_tail is not None:
                            self._pane_runtime_run_start_tail.pop(agent, None)
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
                self._pane_runtime_run_start_tail.pop(agent, None)
                # Keep last known state for idle agents so the frontend still shows it
                pass
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            result[agent] = "offline"
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
