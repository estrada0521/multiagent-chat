from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from multiagent_chat.chat.runtime_format import _pane_runtime_with_occurrence_ids

from native_log_sync.opencode.runtime_tools import runtime_tool_events


def parse_opencode_runtime(runtime, agent: str, limit: int) -> list[dict] | None:
    """OpenCode SQLite から直近ツールイベントをランタイム表示用に読む。"""
    try:
        db_path = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
        if not db_path.exists():
            return None
        oc = runtime._opencode_cursors.get(agent)
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
            events.extend(runtime_tool_events(tool_name, inp, workspace=runtime.workspace))
        conn.close()
        events.reverse()
        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error("Failed to parse OpenCode runtime for %s: %s", agent, e)
        return None
