from __future__ import annotations

import logging
import os
import threading
import time

from native_log_sync.refresh.binding_models import binding_for_path
from .resolve_path import resolve_cursor_session_jsonl_path

_monitor_started = False
_monitor_lock = threading.Lock()


def _cursor_usage_monitor_loop(runtime):
    while True:
        try:
            if not getattr(runtime, "session_is_active", False):
                time.sleep(2.0)
                continue

            running_agents = getattr(runtime, "_agent_running", set())
            running_cursors = [
                a for a in running_agents
                if str(a or "").split("-", 1)[0] == "cursor"
            ]

            if not running_cursors:
                time.sleep(2.0)
                continue

            for agent in running_cursors:
                pane_id = runtime.pane_id_for_agent(agent)
                if not pane_id:
                    continue

                safe_pane = pane_id.replace("%", "_")
                signal_file = f"/tmp/multiagent_cursor_usage_limit_{safe_pane}"
                
                if os.path.exists(signal_file):
                    try:
                        os.remove(signal_file)
                    except OSError:
                        pass
                    
                    logging.warning("Cursor usage limit detected via auto-mode signal for %s, marking as idle.", agent)
                    runtime._mark_idle(agent)
            time.sleep(1.0)
        except Exception as exc:
            logging.error("Cursor usage monitor error: %s", exc)
            time.sleep(2.0)


def _ensure_monitor_started(runtime):
    global _monitor_started
    with _monitor_lock:
        if _monitor_started:
            return
        _monitor_started = True
        threading.Thread(
            target=_cursor_usage_monitor_loop,
            args=(runtime,),
            daemon=True,
            name="cursor-usage-monitor",
        ).start()


def resolve_native_log_binding(runtime, request):
    _ensure_monitor_started(runtime)
    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=resolve_cursor_session_jsonl_path(
            runtime,
            request.pane_pid,
        ),
        source="cursor-session",
    )
