from __future__ import annotations

import json
import logging
import time

from .agent_name_core import agent_base_name
from .state_core import update_thinking_totals_from_statuses as update_shared_thinking_totals_from_statuses


def session_agent_statuses(self, session_name: str, agents: list[str]) -> dict[str, str]:
    result = {}
    for agent in agents:
        pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
        try:
            pane_id = self.tmux_env(session_name, pane_var)
            if not pane_id:
                result[agent] = "offline"
                continue
            dead = self.tmux_run(["display-message", "-p", "-t", pane_id, "#{pane_dead}"]).stdout.strip()
            if dead == "1":
                result[agent] = "dead"
                self._pane_snapshots.pop(pane_id, None)
                self._pane_last_change.pop(pane_id, None)
                continue
            content = self.tmux_run(["capture-pane", "-p", "-S", "-20", "-t", pane_id]).stdout
            # Skip top 10 lines for copilot to avoid false running detection from animated UI
            agent_base = agent.split("-")[0] if "-" in agent else agent
            if agent_base == "copilot":
                content_lines = content.splitlines()
                content = "\n".join(content_lines[10:]) if len(content_lines) > 10 else ""
            now = time.monotonic()
            prev = self._pane_snapshots.get(pane_id)
            self._pane_snapshots[pane_id] = content
            if prev is not None and content != prev:
                self._pane_last_change[pane_id] = now
                result[agent] = "running"
            else:
                last_change = self._pane_last_change.get(pane_id, 0.0)
                result[agent] = "running" if (now - last_change) < self.running_grace_seconds else "idle"
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            result[agent] = "offline"
    return result


def compute_hub_stats(self, active_sessions: list[dict], archived_sessions_data: list[dict]) -> dict:
    for session in active_sessions:
        try:
            statuses = self.session_agent_statuses(session.get("name", ""), list(session.get("agents") or []))
            update_shared_thinking_totals_from_statuses(
                self.repo_root,
                session.get("name", ""),
                session.get("workspace", ""),
                statuses,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            pass
    all_sessions = [*active_sessions, *archived_sessions_data]
    total_messages = 0
    message_by_sender = {}
    message_by_session = {}
    commit_first_seen = {}
    daily_messages = {}
    daily_messages_user = {}
    daily_messages_agent = {}
    seen_paths = set()
    seen_message_keys = set()
    index_records = []
    for session in active_sessions:
        index_paths = self.session_index_paths(
            session.get("name", ""),
            session.get("workspace", ""),
            self.tmux_env(session.get("name", ""), "MULTIAGENT_LOG_DIR"),
        )
        for index_path in index_paths:
            if not index_path.is_file():
                continue
            key = str(index_path.resolve())
            if key not in seen_paths:
                seen_paths.add(key)
                index_records.append((session.get("name", ""), index_path))
    for session in archived_sessions_data:
        index_paths = self.session_index_paths(
            session.get("name", ""),
            session.get("workspace", ""),
            session.get("log_dir", ""),
            include_legacy=True,
        )
        for index_path in index_paths:
            if not index_path.is_file():
                continue
            key = str(index_path.resolve())
            if key not in seen_paths:
                seen_paths.add(key)
                index_records.append((session.get("name", ""), index_path))
    for session_name, index_path in index_records:
        try:
            with index_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception as exc:
                        logging.error(f"Unexpected error: {exc}", exc_info=True)
                        continue
                    msg_key = (
                        (entry.get("msg_id") or "").strip()
                        or "|".join(
                            [
                                session_name,
                                (entry.get("timestamp") or "").strip(),
                                (entry.get("sender") or "").strip(),
                                json.dumps(entry.get("targets") or [], ensure_ascii=False, sort_keys=True),
                                (entry.get("message") or "").strip(),
                            ]
                        )
                    )
                    if msg_key in seen_message_keys:
                        continue
                    seen_message_keys.add(msg_key)
                    sender = (entry.get("sender") or "").strip().lower()
                    if sender == "system":
                        if entry.get("kind") == "git-commit":
                            commit_key = (
                                (entry.get("commit_hash") or "").strip()
                                or f"{session_name}:{(entry.get('msg_id') or '').strip()}"
                            )
                            entry_timestamp = (entry.get("timestamp") or "").strip()
                            previous = commit_first_seen.get(commit_key)
                            if not previous or (
                                entry_timestamp and (not previous["timestamp"] or entry_timestamp < previous["timestamp"])
                            ):
                                commit_first_seen[commit_key] = {
                                    "timestamp": entry_timestamp,
                                    "session": session_name,
                                }
                        continue
                    total_messages += 1
                    message_by_session[session_name] = message_by_session.get(session_name, 0) + 1
                    if sender:
                        base_sender = agent_base_name(sender)
                        message_by_sender[base_sender] = message_by_sender.get(base_sender, 0) + 1
                    ts = (entry.get("timestamp") or "").strip()
                    if ts and len(ts) >= 10:
                        date_key = ts[:10]
                        daily_messages[date_key] = daily_messages.get(date_key, 0) + 1
                        if sender == "user":
                            daily_messages_user[date_key] = daily_messages_user.get(date_key, 0) + 1
                        else:
                            daily_messages_agent[date_key] = daily_messages_agent.get(date_key, 0) + 1
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            continue
    commits_by_session = {}
    daily_commits = {}
    for commit in commit_first_seen.values():
        commit_session = commit["session"]
        commits_by_session[commit_session] = commits_by_session.get(commit_session, 0) + 1
        ts = (commit.get("timestamp") or "").strip()
        if ts and len(ts) >= 10:
            date_key = ts[:10]
            daily_commits[date_key] = daily_commits.get(date_key, 0) + 1
    thinking_totals = self.load_hub_thinking_totals()
    daily_thinking = thinking_totals.get("daily_thinking", {})

    def cumulative_series(daily_source):
        total = 0
        series = []
        for date_key in sorted(daily_source):
            total += max(0, int(daily_source.get(date_key, 0) or 0))
            series.append({"date": date_key, "value": total})
        return series

    return {
        "active_sessions": len(active_sessions),
        "archived_sessions": len(archived_sessions_data),
        "total_sessions": len(all_sessions),
        "daily_messages": daily_messages,
        "daily_messages_user": daily_messages_user,
        "daily_messages_agent": daily_messages_agent,
        "total_messages": total_messages,
        "messages_by_sender": message_by_sender,
        "messages_by_session": message_by_session,
        "total_commits": len(commit_first_seen),
        "commits_by_session": commits_by_session,
        "total_thinking_seconds": thinking_totals["total_seconds"],
        "thinking_by_agent": thinking_totals["by_agent"],
        "thinking_by_session": thinking_totals["by_session"],
        "thinking_session_count": thinking_totals["session_count"],
        "daily_thinking": daily_thinking,
        "daily_commits": daily_commits,
        "cumulative_messages_all": cumulative_series(daily_messages),
        "cumulative_messages_user": cumulative_series(daily_messages_user),
        "cumulative_messages_agent": cumulative_series(daily_messages_agent),
        "cumulative_thinking": cumulative_series(daily_thinking),
        "cumulative_commits": cumulative_series(daily_commits),
    }
