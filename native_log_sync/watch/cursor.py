from __future__ import annotations

import ctypes
import fcntl
import glob
import json
import logging
import os
import sqlite3
import sys
import threading
import time
from ctypes import c_double, c_uint32, c_uint64, c_void_p

from native_log_sync.watch.darwin import (
    FSEVENT_CREATE_FLAGS,
    FSEventCallback,
    KFSEVENTSTREAM_EVENT_ID_SINCE_NOW,
    cf_path_array,
    load_cf_cs,
)

_DEBOUNCE_SEC = 0.15


def _run_cursor_transcript_sync_from_fs_paths(runtime, raw_paths: set[str]) -> None:
    from native_log_sync.cursor.log_location import (
        expand_fsevent_paths_to_transcript_jsonl,
        sync_cursor_transcript_paths,
    )

    jsonl_paths = expand_fsevent_paths_to_transcript_jsonl(runtime, raw_paths)
    if jsonl_paths:
        sync_cursor_transcript_paths(runtime, jsonl_paths)


def _read_store_db_agent_id(db_path: str) -> str:
    try:
        conn = sqlite3.connect(db_path, timeout=0.5)
        cur = conn.cursor()
        cur.execute("SELECT value FROM meta LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if not row:
            return ""
        meta = json.loads(bytes.fromhex(row[0]).decode("utf-8"))
        return str(meta.get("agentId") or "")
    except Exception:
        return ""


def _agent_for_cursor_agent_id(runtime, agent_id: str) -> str:
    if not agent_id:
        return ""
    for agent, cursor in runtime._cursor_cursors.items():
        if cursor.path and agent_id in cursor.path:
            return agent
    return ""


class _DebouncedCursorSync:
    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._timer: threading.Timer | None = None

    def add_paths(self, paths: list[str]) -> None:
        with self._lock:
            for path in paths:
                try:
                    self._pending.add(os.path.realpath(path))
                except OSError:
                    self._pending.add(path)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(_DEBOUNCE_SEC, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            to_sync = set(self._pending)
            self._pending.clear()
            self._timer = None
        if not to_sync:
            return
        for raw_path in to_sync:
            try:
                resolved = os.path.realpath(raw_path)
            except OSError:
                continue
            if not resolved.endswith("store.db") or not os.path.isfile(resolved):
                if os.path.isdir(resolved):
                    for db in glob.glob(os.path.join(resolved, "**/store.db"), recursive=True):
                        self._signal_store_db(db)
                continue
            self._signal_store_db(resolved)

        lock_fd = None
        for _attempt in range(12):
            try:
                lock_fd = open(self._runtime.sync_lock_path, "w")
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if lock_fd:
                    try:
                        lock_fd.close()
                    except Exception:
                        pass
                    lock_fd = None
                time.sleep(0.05)
        else:
            return
        try:
            try:
                active = self._runtime.active_agents()
                for agent in active:
                    if (agent or "").lower().split("-")[0] == "cursor":
                        self._runtime._first_seen_for_agent(agent)
                _run_cursor_transcript_sync_from_fs_paths(self._runtime, to_sync)
            except Exception as exc:
                logging.error("Cursor FSEvents debounced sync failed: %s", exc)
        finally:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass

    def _signal_store_db(self, db_path: str) -> None:
        try:
            agent_id = _read_store_db_agent_id(db_path)
            agent = _agent_for_cursor_agent_id(self._runtime, agent_id)
            if not agent:
                return
            self._runtime._agent_last_turn_done_ts[agent] = time.time()
            event = self._runtime._agent_turn_done_events.get(agent)
            if event is not None:
                event.set()
        except Exception as exc:
            logging.error("Cursor store.db signal failed: %s", exc)


def _cursor_watch_paths(runtime) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for root, agents in getattr(runtime, "_native_log_watch_roots", {}).items():
        if not any(str(agent).split("-", 1)[0] == "cursor" for agent in agents):
            continue
        if root not in seen:
            seen.add(root)
            out.append(root)
    return out


def start_cursor_transcript_fsevents_watcher(runtime) -> None:
    if sys.platform != "darwin":
        return

    debouncer = _DebouncedCursorSync(runtime)

    def run_loop():
        cf, cs = load_cf_cs()
        CFRelease = cf.CFRelease
        CFRelease.argtypes = [c_void_p]
        CFRelease.restype = None

        FSEventStreamCreate = cs.FSEventStreamCreate
        FSEventStreamCreate.restype = c_void_p
        FSEventStreamCreate.argtypes = [c_void_p, FSEventCallback, c_void_p, c_void_p, c_uint64, c_double, c_uint32]
        FSEventStreamScheduleWithRunLoop = cs.FSEventStreamScheduleWithRunLoop
        FSEventStreamScheduleWithRunLoop.argtypes = [c_void_p, c_void_p, c_void_p]
        FSEventStreamScheduleWithRunLoop.restype = None
        FSEventStreamStart = cs.FSEventStreamStart
        FSEventStreamStart.argtypes = [c_void_p]
        FSEventStreamStart.restype = ctypes.c_bool
        FSEventStreamStop = cs.FSEventStreamStop
        FSEventStreamStop.argtypes = [c_void_p, c_void_p]
        FSEventStreamStop.restype = None
        FSEventStreamInvalidate = cs.FSEventStreamInvalidate
        FSEventStreamInvalidate.argtypes = [c_void_p]
        FSEventStreamInvalidate.restype = None
        FSEventStreamRelease = cs.FSEventStreamRelease
        FSEventStreamRelease.argtypes = [c_void_p]
        FSEventStreamRelease.restype = None
        CFRunLoopGetCurrent = cf.CFRunLoopGetCurrent
        CFRunLoopGetCurrent.restype = c_void_p
        CFRunLoopGetCurrent.argtypes = []
        CFRunLoopRun = cf.CFRunLoopRun
        CFRunLoopRun.restype = None
        CFRunLoopRun.argtypes = []
        CFRunLoopStop = cf.CFRunLoopStop
        CFRunLoopStop.argtypes = [c_void_p]
        CFRunLoopStop.restype = None
        kCFRunLoopDefaultMode = c_void_p.in_dll(cf, "kCFRunLoopDefaultMode")

        def on_events(_stream, _info, num, paths, _flags, _ids):
            if not num or not paths:
                return
            batch: list[str] = []
            for index in range(num):
                try:
                    raw = paths[index]
                    if not raw:
                        continue
                    batch.append(raw.decode("utf-8"))
                except Exception:
                    continue
            if batch:
                debouncer.add_paths(batch)

        callback = FSEventCallback(on_events)

        while True:
            try:
                if not runtime.session_is_active:
                    time.sleep(1.0)
                    continue
                watch_paths = _cursor_watch_paths(runtime)
                if not watch_paths:
                    time.sleep(2.0)
                    continue
                cfarr = cf_path_array(cf, watch_paths)
                if not cfarr:
                    time.sleep(2.0)
                    continue
                stream = FSEventStreamCreate(
                    None,
                    callback,
                    None,
                    cfarr,
                    c_uint64(KFSEVENTSTREAM_EVENT_ID_SINCE_NOW),
                    0.05,
                    c_uint32(FSEVENT_CREATE_FLAGS),
                )
                CFRelease(cfarr)
                if not stream:
                    time.sleep(2.0)
                    continue
                run_loop_handle = CFRunLoopGetCurrent()
                runtime._native_log_watch_reconfigure.clear()
                FSEventStreamScheduleWithRunLoop(stream, run_loop_handle, kCFRunLoopDefaultMode)
                if not FSEventStreamStart(stream):
                    FSEventStreamInvalidate(stream)
                    FSEventStreamRelease(stream)
                    time.sleep(2.0)
                    continue
                threading.Thread(
                    target=lambda: (
                        runtime._native_log_watch_reconfigure.wait(),
                        CFRunLoopStop(run_loop_handle),
                    ),
                    daemon=True,
                    name="cursor-fsevents-reconfigure",
                ).start()
                CFRunLoopRun()
                FSEventStreamStop(stream, run_loop_handle)
                FSEventStreamInvalidate(stream)
                FSEventStreamRelease(stream)
            except Exception as exc:
                logging.error("Cursor FSEvents watcher error: %s", exc)
                time.sleep(2.0)

    threading.Thread(target=run_loop, daemon=True, name="cursor-fsevents").start()
