from __future__ import annotations

import json
import logging


def compute_hub_stats(self, active_sessions: list[dict], archived_sessions_data: list[dict]) -> dict:
    all_sessions = [*active_sessions, *archived_sessions_data]
    total_messages = 0
    daily_messages = {}
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
            if key in seen_paths:
                continue
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
            if key in seen_paths:
                continue
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
                        logging.error("Unexpected error: %s", exc, exc_info=True)
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
                        continue

                    total_messages += 1
                    ts = (entry.get("timestamp") or "").strip()
                    if ts and len(ts) >= 10:
                        date_key = ts[:10]
                        daily_messages[date_key] = daily_messages.get(date_key, 0) + 1
        except Exception as exc:
            logging.error("Unexpected error: %s", exc, exc_info=True)
            continue

    return {
        "active_sessions": len(active_sessions),
        "archived_sessions": len(archived_sessions_data),
        "total_sessions": len(all_sessions),
        "total_messages": total_messages,
        "daily_messages": daily_messages,
    }
