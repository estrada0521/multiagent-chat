"""macOS FSEvents watcher for Claude, Codex, Copilot, OpenCode, Qwen, and Gemini (CoreServices, ctypes)."""

from __future__ import annotations

import ctypes
import fcntl
import logging
import os
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
from pathlib import Path

from multiagent_chat.chat.sync.state import (
    claude_fsevent_watch_path_strings,
    codex_fsevent_watch_path_strings,
    copilot_fsevent_watch_path_strings,
    gemini_fsevent_watch_path_strings,
    opencode_fsevent_watch_path_strings,
    qwen_fsevent_watch_path_strings,
)

_FSEVENTSTREAM_FILE_EVENTS = 0x00000010
_FSEVENTSTREAM_WATCH_ROOT = 0x00000004
_CREATE_FLAGS = _FSEVENTSTREAM_FILE_EVENTS | _FSEVENTSTREAM_WATCH_ROOT
_KFSEVENTSTREAM_EVENT_ID_SINCE_NOW = 0xFFFFFFFFFFFFFFFF
_KCF_STRING_ENCODING_UTF8 = 0x08000100
_DEBOUNCE_SEC = 0.15

_WATCH_PATH_GETTERS = [
    ("claude", claude_fsevent_watch_path_strings),
    ("codex", codex_fsevent_watch_path_strings),
    ("copilot", copilot_fsevent_watch_path_strings),
    ("opencode", opencode_fsevent_watch_path_strings),
    ("qwen", qwen_fsevent_watch_path_strings),
    ("gemini", gemini_fsevent_watch_path_strings),
]


class _CFArrayCallBacks(ctypes.Structure):
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
    fn = cf.CFStringCreateWithCString
    fn.argtypes = [c_void_p, c_char_p, c_uint32]
    fn.restype = c_void_p
    return fn(None, value, _KCF_STRING_ENCODING_UTF8)


def _cf_path_array(cf, paths: list[str]) -> c_void_p:
    kCFTypeArrayCallBacks = _CFArrayCallBacks.in_dll(cf, "kCFTypeArrayCallBacks")
    fn = cf.CFArrayCreate
    fn.argtypes = [c_void_p, POINTER(c_void_p), c_long, POINTER(_CFArrayCallBacks)]
    fn.restype = c_void_p
    cf_strings = [_cf_string(cf, p.encode("utf-8")) for p in paths]
    n = len(cf_strings)
    holder = (c_void_p * n)(*cf_strings)
    return fn(None, holder, n, byref(kCFTypeArrayCallBacks))


_FSEVENT_CALLBACK = CFUNCTYPE(
    None, c_void_p, c_void_p, c_size_t, POINTER(c_char_p), POINTER(c_uint32), POINTER(c_uint64)
)


def _build_prefix_map() -> dict[str, str]:
    home = str(Path.home())
    result: dict[str, str] = {}
    for sub, base in (
        (os.path.join(home, ".claude", "projects"), "claude"),
        (os.path.join(home, ".codex", "sessions"), "codex"),
        (os.path.join(home, ".copilot", "session-state"), "copilot"),
        (os.path.join(home, ".local", "share", "opencode"), "opencode"),
        (os.path.join(home, ".qwen", "projects"), "qwen"),
        (os.path.join(home, ".gemini", "tmp"), "gemini"),
    ):
        try:
            result[os.path.realpath(sub)] = base
        except OSError:
            result[sub] = base
    return result


def _agent_base_for_path(prefix_map: dict[str, str], raw_path: str) -> str | None:
    try:
        rp = os.path.realpath(raw_path)
    except OSError:
        return None
    for prefix, base in prefix_map.items():
        if rp == prefix or rp.startswith(prefix + os.sep):
            return base
    return None


class _DebouncedNativeSync:
    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._timer: threading.Timer | None = None

    def add_base(self, base: str) -> None:
        with self._lock:
            self._pending.add(base)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(_DEBOUNCE_SEC, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            bases = set(self._pending)
            self._pending.clear()
            self._timer = None
        if not bases:
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
            active = self._runtime.active_agents()
            for agent in active:
                base = (agent or "").lower().split("-")[0]
                if base not in bases:
                    continue
                self._runtime._first_seen_for_agent(agent)
                sync_method = getattr(self._runtime, f"_sync_{base}_assistant_messages", None)
                if sync_method:
                    try:
                        sync_method(agent)
                    except Exception as exc:
                        logging.error("Native FSEvents sync failed for %s: %s", agent, exc)
        except Exception as exc:
            logging.error("Native FSEvents flush failed: %s", exc)
        finally:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass


def start_native_log_fsevents_watcher(runtime) -> None:
    """Start a daemon thread running FSEventStream for native assistant sources (see _WATCH_PATH_GETTERS)."""
    if sys.platform != "darwin":
        return

    debouncer = _DebouncedNativeSync(runtime)
    prefix_map = _build_prefix_map()

    def run_loop():
        cf, cs = _load_cf_cs()
        CFRelease = cf.CFRelease
        CFRelease.argtypes = [c_void_p]
        CFRelease.restype = None

        FSEventStreamCreate = cs.FSEventStreamCreate
        FSEventStreamCreate.restype = c_void_p
        FSEventStreamCreate.argtypes = [
            c_void_p, _FSEVENT_CALLBACK, c_void_p, c_void_p,
            c_uint64, c_double, c_uint32,
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
            triggered: set[str] = set()
            for i in range(num):
                try:
                    raw = paths[i]
                    if not raw:
                        continue
                    base = _agent_base_for_path(prefix_map, raw.decode("utf-8"))
                    if base:
                        triggered.add(base)
                except Exception:
                    continue
            for base in triggered:
                debouncer.add_base(base)

        callback = _FSEVENT_CALLBACK(on_events)

        while True:
            try:
                if not runtime.session_is_active:
                    time.sleep(1.0)
                    continue
                watch_paths: list[str] = []
                seen: set[str] = set()
                for _base, getter in _WATCH_PATH_GETTERS:
                    for p in getter(runtime, runtime.workspace or ""):
                        if p not in seen:
                            seen.add(p)
                            watch_paths.append(p)
                if not watch_paths:
                    time.sleep(2.0)
                    continue
                cfarr = _cf_path_array(cf, watch_paths)
                if not cfarr:
                    time.sleep(2.0)
                    continue
                stream = FSEventStreamCreate(
                    None, callback, None, cfarr,
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
                logging.error("Native FSEvents watcher error: %s", exc)
                time.sleep(2.0)

    threading.Thread(target=run_loop, daemon=True, name="native-fsevents").start()
