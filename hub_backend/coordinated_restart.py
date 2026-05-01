"""Before restarting the Hub HTTP process, ask each known chat server to /new-chat.

Hub reload (POST /restart-hub) alone leaves per-session chat listeners running; the UI
expects the same effect as refreshing the chat process. Best-effort POST to each
active session's chat_port; ignore failures (no listener, wrong session, etc.).
"""

from __future__ import annotations

import http.client
import logging
from collections.abc import Callable
from typing import Any


def request_new_chat_on_active_session_ports(
    active_session_records_query_fn: Callable[[], Any],
) -> None:
    try:
        query = active_session_records_query_fn()
    except Exception as exc:
        logging.warning("active_session_records_query before hub restart failed: %s", exc)
        return
    records = getattr(query, "records", None) or {}
    if not isinstance(records, dict):
        return
    ports_seen: set[int] = set()
    for record in records.values():
        if not isinstance(record, dict):
            continue
        try:
            port = int(record.get("chat_port") or 0)
        except (TypeError, ValueError):
            continue
        if port <= 0 or port in ports_seen:
            continue
        ports_seen.add(port)
        _post_new_chat_best_effort(port)


def _post_new_chat_best_effort(port: int) -> None:
    try:
        conn = http.client.HTTPConnection("127.0.0.1", int(port), timeout=4)
        conn.request("POST", "/new-chat", body=b"", headers={"Content-Length": "0"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
    except Exception as exc:
        logging.debug("POST /new-chat on port %s before hub restart failed: %s", port, exc)
