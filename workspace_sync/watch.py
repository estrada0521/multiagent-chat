from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from ctypes import c_double, c_uint32, c_uint64, c_void_p

from native_log_sync.io.fsevents_stream import (
    FSEVENT_CREATE_FLAGS,
    FSEventCallback,
    KFSEVENTSTREAM_EVENT_ID_SINCE_NOW,
    cf_path_array,
    load_cf_cs,
)

_DEBOUNCE_SEC = 0.25


class _DebouncedWorkspaceRefresh:
    def __init__(self, workspace_sync_api) -> None:
        self._api = workspace_sync_api
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._timer: threading.Timer | None = None

    def add_path(self, path: str) -> None:
        normalized = os.path.realpath(path)
        workspace = self._api.file_runtime.workspace
        if not normalized.startswith(workspace):
            return
        rel = os.path.relpath(normalized, workspace).replace("\\", "/")
        if rel == ".git" or rel.startswith(".git/"):
            return
        with self._lock:
            self._pending.add(normalized)
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
        try:
            self._api.refresh_file_index_cache()
        except Exception as exc:
            logging.error("Workspace file index refresh failed: %s", exc)


def start_workspace_fsevents_watcher(workspace_sync_api) -> None:
    if sys.platform != "darwin":
        return

    workspace_root = workspace_sync_api.file_runtime.workspace
    if not workspace_root or not os.path.isdir(workspace_root):
        return

    debouncer = _DebouncedWorkspaceRefresh(workspace_sync_api)

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
                watch_root = workspace_sync_api.file_runtime.workspace
                if not watch_root or not os.path.isdir(watch_root):
                    time.sleep(2.0)
                    continue
                cfarr = cf_path_array(cf, [watch_root])
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
                FSEventStreamScheduleWithRunLoop(stream, run_loop_handle, kCFRunLoopDefaultMode)
                if not FSEventStreamStart(stream):
                    FSEventStreamInvalidate(stream)
                    FSEventStreamRelease(stream)
                    time.sleep(2.0)
                    continue
                CFRunLoopRun()
                FSEventStreamStop(stream, run_loop_handle)
                FSEventStreamInvalidate(stream)
                FSEventStreamRelease(stream)
            except Exception as exc:
                logging.error("Workspace FSEvents watcher error: %s", exc)
                time.sleep(2.0)

    threading.Thread(target=run_loop, daemon=True, name="workspace-fsevents").start()
