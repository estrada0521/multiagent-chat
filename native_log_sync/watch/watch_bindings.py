from __future__ import annotations

import logging
import os
import select
import sys
import threading
import time

from native_log_sync.watch.emit_events import emit_agent_updates


class _VnodeNativeSync:
    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self._lock = threading.Lock()
        self._kq = select.kqueue()
        self._fd_by_agent: dict[str, int] = {}
        self._path_by_agent: dict[str, str] = {}
        self._agent_by_fd: dict[int, str] = {}

    def _sync_bindings(self) -> None:
        bindings: dict = dict(getattr(self._runtime, "_native_log_bindings_by_agent", {}))
        with self._lock:
            for agent in list(self._fd_by_agent):
                if agent not in bindings:
                    self._close_locked(agent)
            for agent, binding in bindings.items():
                if self._path_by_agent.get(agent) != binding.path:
                    if agent in self._fd_by_agent:
                        self._close_locked(agent)
                    self._open_locked(agent, binding.path)

    def _close_locked(self, agent: str) -> None:
        fd = self._fd_by_agent.pop(agent, None)
        self._path_by_agent.pop(agent, None)
        if fd is not None:
            self._agent_by_fd.pop(fd, None)
            try:
                os.close(fd)
            except OSError:
                pass

    def _open_locked(self, agent: str, path: str) -> None:
        try:
            fd = os.open(path, os.O_RDONLY)
            ev = select.kevent(
                fd,
                filter=select.KQ_FILTER_VNODE,
                flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                fflags=select.KQ_NOTE_WRITE | select.KQ_NOTE_EXTEND,
            )
            self._kq.control([ev], 0)
            self._fd_by_agent[agent] = fd
            self._path_by_agent[agent] = path
            self._agent_by_fd[fd] = agent
        except OSError as exc:
            logging.warning("vnode register failed for %s (%s): %s", agent, path, exc)

    def get_watched_paths(self) -> dict[str, str]:
        with self._lock:
            return dict(self._path_by_agent)

    def run(self) -> None:
        reconfigure = getattr(self._runtime, "_native_log_watch_reconfigure", None)
        self._sync_bindings()
        if reconfigure:
            reconfigure.clear()
        while True:
            try:
                if not self._runtime.session_is_active:
                    time.sleep(1.0)
                    continue
                events = self._kq.control(None, 16, 1.0)
                for event in events:
                    if event.fflags & (select.KQ_NOTE_WRITE | select.KQ_NOTE_EXTEND):
                        with self._lock:
                            agent = self._agent_by_fd.get(event.ident)
                            path = self._path_by_agent.get(agent) if agent else None
                        if agent and path:
                            try:
                                emit_agent_updates(self._runtime, agent, path)
                            except Exception as exc:
                                logging.error("Native vnode emit failed for %s: %s", agent, exc)
                if reconfigure and reconfigure.is_set():
                    reconfigure.clear()
                    self._sync_bindings()
            except Exception as exc:
                logging.error("Native vnode watcher error: %s", exc)
                time.sleep(1.0)


def start_native_log_vnode_watcher(runtime) -> None:
    if sys.platform != "darwin":
        return
    watcher = _VnodeNativeSync(runtime)
    runtime._native_log_vnode_watcher = watcher
    threading.Thread(target=watcher.run, daemon=True, name="native-vnode").start()
