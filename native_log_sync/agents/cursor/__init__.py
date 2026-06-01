from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import threading
import time

from backend_core.access.settings import agent_window_run_dir
from backend_core.access.files import append_jsonl_entry
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

            running_agents = runtime.running_agents()
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
                run_dir = Path(
                    os.environ.get("AGENT_WINDOW_RUN_DIR")
                    or agent_window_run_dir(getattr(runtime, "repo_root", Path.cwd()))
                )
                signal_file = run_dir / "cursor-usage-limits" / safe_pane
                
                if signal_file.exists():
                    try:
                        signal_file.unlink()
                    except OSError:
                        pass
                    
                    logging.warning("Cursor usage limit detected via auto-mode signal for %s, marking as idle.", agent)
                    
                    # Inject message into chat
                    display = "You've hit your usage limit"
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    msg_id_key = f"cursor-usage-limit:{agent}:{runtime.session_name}:{timestamp}"
                    msg_id = hashlib.sha256(msg_id_key.encode("utf-8")).hexdigest()[:12]
                    
                    jsonl_entry = {
                        "timestamp": timestamp,
                        "session": runtime.session_name,
                        "sender": agent,
                        "targets": ["user"],
                        "message": display,
                        "msg_id": msg_id,
                    }
                    append_jsonl_entry(runtime.index_path, jsonl_entry)
                    
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


def on_pane_restart(runtime, agent: str) -> None:
    # Path resolves dynamically via lsof on the new PID tree after Workspace Trust.
    pass


def on_pane_add(runtime, agent: str) -> None:
    pass
