from __future__ import annotations

import ctypes
import fcntl
import logging
import os
import sys
import threading
import time
from ctypes import c_double, c_uint32, c_uint64, c_void_p

from native_log_sync.io.state_paths import canonical_native_log_sync_lock_path
from native_log_sync.io.fsevents_stream import (
    FSEVENT_CREATE_FLAGS,
    FSEventCallback,
    KFSEVENTSTREAM_EVENT_ID_SINCE_NOW,
    cf_path_array,
    load_cf_cs,
)
from native_log_sync.watch.emit_events import emit_agent_updates

_DEBOUNCE_SEC = 0.15


class _DebouncedNativeSync:
    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._timer: threading.Timer | None = None

    def add_path(self, path: str) -> None:
        with self._lock:
            self._pending.add(path)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(_DEBOUNCE_SEC, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            paths = set(self._pending)
            self._pending.clear()
            self._timer = None
        if not paths:
            return

        lock_fd = None
        for _attempt in range(12):
            try:
                lock_fd = open(canonical_native_log_sync_lock_path(self._runtime.index_path.parent), "w")
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
            bindings = list(getattr(self._runtime, "_native_log_bindings_by_agent", {}).values())
            for binding in bindings:
                watch_roots = [root.rstrip("/") for root in binding.watch_roots]
                root_prefixes = [root.rstrip("/") + "/" for root in binding.watch_roots]
                if not any(
                    path == binding.path
                    or path in watch_roots
                    or any(path.startswith(prefix) for prefix in root_prefixes)
                    for path in paths
                ):
                    continue
                try:
                    emit_agent_updates(self._runtime, binding.agent, binding.path)
                except Exception as exc:
                    logging.error("Native FSEvents sync failed for %s: %s", binding.agent, exc)
        except Exception as exc:
            logging.error("Native FSEvents flush failed: %s", exc)
        finally:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass


def _native_watch_paths(runtime) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for root, _ in getattr(runtime, "_native_log_watch_roots", {}).items():
        if root not in seen:
            seen.add(root)
            out.append(root)
    return out


def start_native_log_fsevents_watcher(runtime) -> None:
    if sys.platform != "darwin":
        return

    debouncer = _DebouncedNativeSync(runtime)

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
            for index in range(num):
                try:
                    raw = paths[index]
                    if not raw:
                        continue
                    debouncer.add_path(raw.decode("utf-8"))
                except Exception:
                    continue

        callback = FSEventCallback(on_events)

        while True:
            try:
                if not runtime.session_is_active:
                    time.sleep(1.0)
                    continue
                watch_paths = _native_watch_paths(runtime)
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
                    name="native-fsevents-reconfigure",
                ).start()
                CFRunLoopRun()
                FSEventStreamStop(stream, run_loop_handle)
                FSEventStreamInvalidate(stream)
                FSEventStreamRelease(stream)
            except Exception as exc:
                logging.error("Native FSEvents watcher error: %s", exc)
                time.sleep(2.0)

    threading.Thread(target=run_loop, daemon=True, name="native-fsevents").start()
