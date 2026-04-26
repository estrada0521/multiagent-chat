"""macOS FSEvents watcher for Cursor ``agent-transcripts`` JSONL and ``store.db`` (CoreServices, ctypes)."""

from __future__ import annotations

import ctypes
import json
import logging
import os
import sqlite3
import sys
import threading
import time
from ctypes import (
    CFUNCTYPE,
    POINTER,
    byref,
    c_char_p,
    c_double,
    c_long,
    c_size_t,
    c_uint32,
    c_uint64,
    c_void_p,
)

from multiagent_chat.chat.sync.cursor_dispatch import (
    expand_fsevent_paths_to_transcript_jsonl,
    sync_cursor_transcript_paths,
)
from multiagent_chat.chat.sync.state import cursor_fsevent_watch_path_strings

_FSEVENTSTREAM_FILE_EVENTS = 0x00000010
_FSEVENTSTREAM_WATCH_ROOT = 0x00000004
_CREATE_FLAGS = _FSEVENTSTREAM_FILE_EVENTS | _FSEVENTSTREAM_WATCH_ROOT
_KFSEVENTSTREAM_EVENT_ID_SINCE_NOW = 0xFFFFFFFFFFFFFFFF
_KCF_STRING_ENCODING_UTF8 = 0x08000100
_DEBOUNCE_SEC = 0.15


class CFArrayCallBacks(ctypes.Structure):
    _fields_ = [
        ("version", c_long),
        ("retain", c_void_p),
        ("release", c_void_p),
        ("copyDescription", c_void_p),
        ("equal", c_void_p),
    ]


def _load_cf_cs():
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    cs = ctypes.CDLL("/System/Library/Frameworks/CoreServices.framework/CoreServices")
    return cf, cs


def _cf_string(cf, value: bytes) -> c_void_p:
    CFStringCreateWithCString = cf.CFStringCreateWithCString
    CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint32]
    CFStringCreateWithCString.restype = c_void_p
    return CFStringCreateWithCString(None, value, _KCF_STRING_ENCODING_UTF8)


def _cf_path_array(cf, paths: list[str]) -> c_void_p:
    kCFTypeArrayCallBacks = CFArrayCallBacks.in_dll(cf, "kCFTypeArrayCallBacks")
    CFArrayCreate = cf.CFArrayCreate
    CFArrayCreate.argtypes = [c_void_p, POINTER(c_void_p), c_long, POINTER(CFArrayCallBacks)]
    CFArrayCreate.restype = c_void_p
    cf_strings = [_cf_string(cf, p.encode("utf-8")) for p in paths]
    n = len(cf_strings)
    holder = (c_void_p * n)(*cf_strings)
    return CFArrayCreate(None, holder, n, byref(kCFTypeArrayCallBacks))


_FSEVENT_CALLBACK = CFUNCTYPE(
    None, c_void_p, c_void_p, c_size_t, POINTER(c_char_p), POINTER(c_uint32), POINTER(c_uint64)
)


def _read_store_db_agent_id(db_path: str) -> str:
    """store.db の meta テーブルから agentId を読む。失敗時は空文字列を返す。"""
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
    """transcript cursor の path から agentId に対応する cursor agent 名を返す。"""
    if not agent_id:
        return ""
    for agent, cursor in runtime._cursor_cursors.items():
        if cursor.path and agent_id in cursor.path:
            return agent
    return ""


def start_cursor_transcript_fsevents_watcher(runtime) -> None:
    """Start a daemon thread running an FSEventStream for Cursor transcript dirs."""
    if sys.platform != "darwin":
        return

    debouncer = _DebouncedCursorSync(runtime)

    def run_loop():
        cf, cs = _load_cf_cs()
        CFRelease = cf.CFRelease
        CFRelease.argtypes = [c_void_p]
        CFRelease.restype = None

        FSEventStreamCreate = cs.FSEventStreamCreate
        FSEventStreamCreate.restype = c_void_p
        FSEventStreamCreate.argtypes = [
            c_void_p,
            _FSEVENT_CALLBACK,
            c_void_p,
            c_void_p,
            c_uint64,
            c_double,
            c_uint32,
        ]
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
        kCFRunLoopDefaultMode = c_void_p.in_dll(cf, "kCFRunLoopDefaultMode")

        def on_events(_stream, _info, num, paths, _flags, _ids):
            if not num or not paths:
                return
            batch: list[str] = []
            for i in range(num):
                try:
                    raw = paths[i]
                    if not raw:
                        continue
                    batch.append(raw.decode("utf-8"))
                except Exception:
                    continue
            if batch:
                debouncer.add_paths(batch)

        callback = _FSEVENT_CALLBACK(on_events)

        while True:
            try:
                if not runtime.session_is_active:
                    time.sleep(1.0)
                    continue
                watch_paths = cursor_fsevent_watch_path_strings(runtime, runtime.workspace or "")
                if not watch_paths:
                    time.sleep(2.0)
                    continue
                cfarr = _cf_path_array(cf, watch_paths)
                if not cfarr:
                    time.sleep(2.0)
                    continue
                stream = FSEventStreamCreate(
                    None,
                    callback,
                    None,
                    cfarr,
                    c_uint64(_KFSEVENTSTREAM_EVENT_ID_SINCE_NOW),
                    0.05,
                    c_uint32(_CREATE_FLAGS),
                )
                CFRelease(cfarr)
                if not stream:
                    time.sleep(2.0)
                    continue
                rl = CFRunLoopGetCurrent()
                FSEventStreamScheduleWithRunLoop(stream, rl, kCFRunLoopDefaultMode)
                if not FSEventStreamStart(stream):
                    FSEventStreamInvalidate(stream)
                    FSEventStreamRelease(stream)
                    time.sleep(2.0)
                    continue
                CFRunLoopRun()
                FSEventStreamStop(stream, rl)
                FSEventStreamInvalidate(stream)
                FSEventStreamRelease(stream)
            except Exception as exc:
                logging.error("Cursor FSEvents watcher error: %s", exc)
                time.sleep(2.0)

    threading.Thread(target=run_loop, daemon=True, name="cursor-fsevents").start()


class _DebouncedCursorSync:
    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._timer: threading.Timer | None = None

    def add_paths(self, paths: list[str]) -> None:
        with self._lock:
            for p in paths:
                try:
                    self._pending.add(os.path.realpath(p))
                except OSError:
                    self._pending.add(p)
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
        import fcntl

        # store.db 更新を先に処理（lock 不要）
        for raw_path in to_sync:
            try:
                rp = os.path.realpath(raw_path)
            except OSError:
                continue
            if not rp.endswith("store.db") or not os.path.isfile(rp):
                # ディレクトリイベントの場合は glob して探す
                if os.path.isdir(rp):
                    import glob
                    for db in glob.glob(os.path.join(rp, "**/store.db"), recursive=True):
                        self._signal_store_db(db)
                continue
            self._signal_store_db(rp)

        jsonl_paths = expand_fsevent_paths_to_transcript_jsonl(self._runtime, to_sync)
        if not jsonl_paths:
            return

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
                sync_cursor_transcript_paths(self._runtime, jsonl_paths)
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
            ev = self._runtime._agent_turn_done_events.get(agent)
            if ev is not None:
                ev.set()
        except Exception as exc:
            logging.error("Cursor store.db signal failed: %s", exc)
