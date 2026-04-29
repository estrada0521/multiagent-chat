import logging
import os
import select
import sys
import threading
import time

_WATCH_THREAD_STARTED = False
_WATCHER_LOCK = threading.Lock()
_WATCHED_PATHS: dict[int, str] = {}  # fd -> path
_AGENT_BY_PATH: dict[str, str] = {}  # path -> agent
_KQ = None
_RUNTIME = None


def _run_kqueue():
    global _KQ, _RUNTIME
    while True:
        try:
            if _KQ is None:
                time.sleep(1)
                continue

            events = _KQ.control(None, 10, 1.0)
            for event in events:
                if event.fflags & (select.KQ_NOTE_WRITE | select.KQ_NOTE_EXTEND):
                    with _WATCHER_LOCK:
                        path = _WATCHED_PATHS.get(event.ident)
                        agent = _AGENT_BY_PATH.get(path) if path else None
                    if agent and _RUNTIME:
                        try:
                            from native_log_sync.watch.emit_events import emit_agent_updates
                            emit_agent_updates(_RUNTIME, agent, path)
                        except Exception as exc:
                            logging.error(f"Codex kqueue emit failed: {exc}")
        except Exception as exc:
            logging.error(f"Codex kqueue loop error: {exc}")
            time.sleep(1.0)


def ensure_codex_kqueue_watcher(runtime, agent: str, path: str):
    if sys.platform != "darwin":
        return
    
    global _WATCH_THREAD_STARTED, _KQ, _RUNTIME
    with _WATCHER_LOCK:
        _RUNTIME = runtime
        if not _WATCH_THREAD_STARTED:
            try:
                _KQ = select.kqueue()
                threading.Thread(target=_run_kqueue, daemon=True, name="codex-kqueue").start()
                _WATCH_THREAD_STARTED = True
            except Exception as exc:
                logging.error(f"Codex kqueue init failed: {exc}")
                return
        
        if path not in _AGENT_BY_PATH:
            try:
                fd = os.open(path, os.O_RDONLY)
                ev = select.kevent(
                    fd, 
                    filter=select.KQ_FILTER_VNODE, 
                    flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR, 
                    fflags=select.KQ_NOTE_WRITE | select.KQ_NOTE_EXTEND
                )
                _KQ.control([ev], 0)
                _WATCHED_PATHS[fd] = path
                _AGENT_BY_PATH[path] = agent
            except Exception as exc:
                logging.error(f"Codex kqueue register failed for {path}: {exc}")
