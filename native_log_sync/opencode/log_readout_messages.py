from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path

from multiagent_chat.chat.runtime_format import _pane_runtime_with_occurrence_ids
from multiagent_chat.chat.sync.cursor import OpenCodeCursor
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.core.runtime_display import runtime_event
from native_log_sync.core.runtime_paths import display_path
from native_log_sync.opencode.log_location import opencode_db_path

def sync_opencode_assistant_messages(
    self,
    agent: str,
    *,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    try:
        db_path = opencode_db_path()
        if not db_path.exists():
            return

        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        claimed_session_ids = {
            c.session_id
            for other_agent, c in self._opencode_cursors.items()
            if other_agent != agent and c.session_id
        }

        prev_cursor = self._opencode_cursors.get(agent)
        prev_session_id = prev_cursor.session_id if prev_cursor else ""
        last_msg_id = prev_cursor.last_msg_id if prev_cursor else ""

        workspace_aliases = self._workspace_aliases(self.workspace or "")
        if not workspace_aliases:
            workspace_aliases = [str(self.workspace or "")]
        placeholders = ",".join("?" for _ in workspace_aliases)
        cur.execute(
            f"""
                SELECT s.id FROM session s
                WHERE s.directory IN ({placeholders})
                ORDER BY s.time_updated DESC
                """,
            workspace_aliases,
        )
        session_id = ""
        for (candidate_id,) in cur.fetchall():
            if candidate_id == prev_session_id:
                session_id = candidate_id
                break
            if candidate_id not in claimed_session_ids:
                session_id = candidate_id
                break

        if not session_id:
            conn.close()
            return

        if last_msg_id and prev_session_id == session_id:
            where_clause = "AND m.time_created > (SELECT time_created FROM message WHERE id = ?)"
            anchor_value = last_msg_id
        else:
            first_seen_ms = int(self._first_seen_for_agent(agent) * 1000)
            backfill_floor_ms = int((time.time() - _SYNC_BIND_BACKFILL_WINDOW_SECONDS) * 1000)
            where_clause = "AND m.time_created >= ?"
            anchor_value = min(first_seen_ms, backfill_floor_ms)

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

        for msg_id, ts_ms, msg_data in cur.fetchall():
            obj = json.loads(msg_data)
            if obj.get("role") != "assistant":
                continue

            cur2 = conn.cursor()
            cur2.execute(
                "SELECT p.data FROM part p WHERE p.message_id = ? ORDER BY p.time_created ASC",
                (msg_id,),
            )

            texts = []
            error_parts = []
            for (pd,) in cur2.fetchall():
                pdata = json.loads(pd)
                pt = pdata.get("type", "")
                if pt == "text":
                    t = pdata.get("text", "").strip()
                    if t:
                        texts.append(t)
                elif pt == "tool-result" and pdata.get("isError"):
                    err_name = pdata.get("name", "?")
                    err_content = str(pdata.get("content", ""))[:200]
                    error_parts.append(f"{err_name}: {err_content}")

            if not texts and not error_parts:
                continue

            display = "\n".join(texts) if texts else ""
            if error_parts:
                error_text = "Errors: " + " | ".join(error_parts)
                display = f"{display}\n\n{error_text}".strip() if display else error_text

            if not display:
                continue

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

        conn.close()

        if new_last_msg_id or prev_session_id != session_id:
            self._opencode_cursors[agent] = OpenCodeCursor(
                session_id=session_id,
                last_msg_id=new_last_msg_id or "",
            )
            self.save_sync_state()
    except Exception as exc:
        logging.error(f"Failed to sync OpenCode message for {agent}: {exc}", exc_info=True)
