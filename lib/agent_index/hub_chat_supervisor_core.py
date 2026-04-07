from __future__ import annotations

import http.client
import json
import logging
import os
import shutil
import signal
import ssl
import subprocess
import sys
import time
from pathlib import Path

from .state_core import (
    delete_session_thinking_data,
    local_state_dir,
    port_is_bindable,
    save_chat_port_override,
)


def chat_ready(self, chat_port: int) -> bool:
    import socket as _sock

    try:
        with _sock.create_connection(("127.0.0.1", chat_port), timeout=0.35):
            return True
    except OSError:
        return False


def chat_server_state(self, chat_port: int) -> dict | None:
    for scheme in ("https", "http"):
        try:
            if scheme == "https":
                conn = http.client.HTTPSConnection(
                    "127.0.0.1",
                    chat_port,
                    timeout=0.6,
                    context=ssl._create_unverified_context(),
                )
            else:
                conn = http.client.HTTPConnection("127.0.0.1", chat_port, timeout=0.6)
            conn.request(
                "GET",
                f"/session-state?ts={int(time.time() * 1000)}",
                headers={"Host": f"127.0.0.1:{chat_port}"},
            )
            resp = conn.getresponse()
            body = resp.read()
            conn.close()
            if 200 <= resp.status < 300:
                data = json.loads(body.decode("utf-8", errors="replace"))
                if isinstance(data, dict):
                    return data
        except (OSError, http.client.HTTPException, json.JSONDecodeError):
            continue
    return None


def chat_server_matches(self, session_name: str, chat_port: int) -> bool:
    state = self.chat_server_state(chat_port)
    if not state:
        return False
    if (state.get("session") or "") != session_name:
        return False
    expected_agents = self.session_agents(session_name)
    reported_agents = [str(a).strip() for a in (state.get("targets") or []) if str(a).strip()]
    if expected_agents and reported_agents and set(expected_agents) != set(reported_agents):
        return False
    if expected_agents and not reported_agents:
        return False
    # Hub がエージェント一覧を読めていないのに chat 側だけ tmux 失敗時の argv targets で非空、
    # という不整合のときは再利用せず再起動して揃えを試みる。
    if reported_agents and not expected_agents:
        return False
    return True


def stop_chat_server(
    self,
    session_name: str,
    *,
    subprocess_module=subprocess,
    os_module=os,
    signal_module=signal,
    time_module=time,
) -> tuple[bool, str]:
    chat_port = self.chat_port_for_session(session_name)
    try:
        result = subprocess_module.run(
            ["lsof", "-nP", f"-tiTCP:{chat_port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        pids = [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
    except (OSError, subprocess_module.TimeoutExpired) as exc:
        return False, f"lsof failed: {exc}"
    if not pids:
        return True, ""
    for pid in pids:
        try:
            os_module.kill(pid, signal_module.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError as exc:
            logging.warning("SIGTERM pid %d failed: %s", pid, exc)
    for _ in range(15):
        if not self.chat_ready(chat_port):
            return True, ""
        time_module.sleep(0.1)
    for pid in pids:
        try:
            os_module.kill(pid, signal_module.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as exc:
            logging.warning("SIGKILL pid %d failed: %s", pid, exc)
    if self.chat_ready(chat_port):
        return False, f"chat server on port {chat_port} still running after SIGKILL"
    return True, ""


def chat_launch_workspace(self, session_name: str) -> tuple[str, bool]:
    workspace, timed_out = self.tmux_env_query(session_name, "MULTIAGENT_WORKSPACE")
    if timed_out:
        return "", True
    workspace = (workspace or "").strip()
    if workspace:
        return workspace, False
    query = self.active_session_records_query()
    if query.state == "ok":
        workspace = str((query.records.get(session_name) or {}).get("workspace") or "").strip()
    return workspace or str(self.repo_root), False


def chat_launch_session_dir(self, session_name: str, workspace: str, explicit_log_dir: str) -> Path:
    repo_session_dir = self.repo_root / "logs" / session_name
    repo_session_dir.mkdir(parents=True, exist_ok=True)
    canonical_index = repo_session_dir / ".agent-index.jsonl"
    if canonical_index.is_file():
        return repo_session_dir
    existing_index = self.session_index_path(
        session_name,
        workspace,
        explicit_log_dir,
        include_legacy=True,
    )
    if (
        existing_index is not None
        and existing_index.is_file()
        and existing_index.parent != repo_session_dir
    ):
        try:
            shutil.copy2(existing_index, canonical_index)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
    return repo_session_dir


def chat_launch_env(self) -> dict[str, str]:
    env = os.environ.copy()
    env["MULTIAGENT_AGENT_NAME"] = "user"
    if self.tmux_socket:
        env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
    env["SESSION_IS_ACTIVE"] = "1"
    pythonpath_parts = [str(self.repo_root / "lib"), str(self.repo_root)]
    existing_pythonpath = (env.get("PYTHONPATH") or "").strip()
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def ensure_chat_server(
    self,
    session_name: str,
    *,
    port_is_bindable_fn=port_is_bindable,
    save_chat_port_override_fn=save_chat_port_override,
    subprocess_module=subprocess,
    sys_module=sys,
    time_module=time,
) -> tuple[bool, int, str]:
    lock = self._get_launch_lock(session_name)
    with lock:
        chat_port = self.chat_port_for_session(session_name)
        if self.chat_ready(chat_port):
            if self.chat_server_matches(session_name, chat_port):
                return True, chat_port, ""
            # Mismatch (e.g. agent list changed). Kill and restart.
            stop_ok, stop_detail = self.stop_chat_server(session_name)
            if not stop_ok:
                logging.warning("stop_chat_server failed before relaunch: %s", stop_detail)

        # Port might still be in use by a dying process or something else
        if not port_is_bindable_fn(chat_port):
            # Try to see if it's our server but matches() was wrong (race condition)
            if self.chat_ready(chat_port) and self.chat_server_matches(session_name, chat_port):
                return True, chat_port, ""

            # Still busy? Try to find it or pick a new one, but be conservative
            for candidate in range(chat_port, chat_port + 10):
                if self.chat_ready(candidate) and self.chat_server_matches(session_name, candidate):
                    save_chat_port_override_fn(self.repo_root, session_name, candidate)
                    return True, candidate, ""
                if port_is_bindable_fn(candidate):
                    save_chat_port_override_fn(self.repo_root, session_name, candidate)
                    chat_port = candidate
                    break

        workspace, workspace_timed_out = self._chat_launch_workspace(session_name)
        explicit_log_dir, log_dir_timed_out = self.tmux_env_query(session_name, "MULTIAGENT_LOG_DIR")
        targets, targets_timed_out = self.session_agents_query(session_name)
        if workspace_timed_out or log_dir_timed_out or targets_timed_out:
            return False, chat_port, "tmux query timed out while preparing chat server launch"
        session_dir = self._chat_launch_session_dir(session_name, workspace, explicit_log_dir)
        index_path = session_dir / ".agent-index.jsonl"
        try:
            self.tmux_run(["set-environment", "-t", session_name, "MULTIAGENT_INDEX_PATH", str(index_path)], timeout=2)
        except Exception:
            pass
        env = self._chat_launch_env()
        env["MULTIAGENT_INDEX_PATH"] = str(index_path)
        try:
            subprocess_module.Popen(
                [
                    sys_module.executable,
                    "-m",
                    "agent_index.chat_server",
                    str(index_path),
                    "2000",
                    "",
                    session_name,
                    "1",
                    str(chat_port),
                    str(self.agent_send_path),
                    workspace,
                    str(session_dir.parent),
                    ",".join(targets),
                    self.tmux_socket,
                    str(self.hub_port),
                ],
                cwd=workspace or str(self.repo_root),
                env=env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return False, chat_port, str(exc)
        for _ in range(60):
            if self.chat_ready(chat_port):
                return True, chat_port, ""
            time_module.sleep(0.1)
        return False, chat_port, "chat server did not become ready"


def revive_archived_session(self, session_name: str) -> tuple[bool, str]:
    query = self.active_session_records_query()
    if query.state == "unhealthy":
        return False, f"tmux is currently unresponsive ({query.detail})"
    active_records = query.records
    if session_name in active_records:
        return True, ""
    archived = self.archived_session_records(active_records.keys())
    record = archived.get(session_name)
    if not record:
        return False, "That archived session is not available in this repo."
    workspace = (record.get("workspace") or "").strip()
    if not workspace or not Path(workspace).is_dir():
        return False, f"Saved workspace is unavailable: {workspace or 'unknown'}"
    env = os.environ.copy()
    if self.tmux_socket:
        env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
    env["MULTIAGENT_SKIP_USER_CHAT"] = "1"
    stop_ok, stop_detail = self.stop_chat_server(session_name)
    if not stop_ok:
        logging.warning("stop_chat_server failed during revive: %s", stop_detail)
    cmd = [
        str(self.multiagent_path),
        "--session",
        session_name,
        "--workspace",
        workspace,
        "--detach",
    ]
    agents = record.get("agents") or []
    if agents:
        cmd.extend(["--agents", ",".join(agents)])
    try:
        subprocess.Popen(
            cmd,
            cwd=workspace,
            env=env,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return False, str(exc)
    for _ in range(80):
        query = self.active_session_records_query()
        if session_name in query.records:
            return True, ""
        if query.state == "unhealthy":
            return False, f"tmux became unresponsive during session startup ({query.detail})"
        time.sleep(0.15)
    return False, f"Session {session_name} did not come up in time."


def kill_repo_session(self, session_name: str) -> tuple[bool, str]:
    query = self.active_session_records_query()
    if query.state == "unhealthy":
        return False, f"tmux is unresponsive, cannot confirm session state ({query.detail})"

    active = query.records
    if session_name not in active:
        return False, "That active session is not available in this repo."

    result = self.tmux_run(["kill-session", "-t", session_name], timeout=4)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or "tmux kill-session failed"
        return False, detail

    for _ in range(20):
        query = self.active_session_records_query()
        if session_name not in query.records:
            stop_ok, stop_detail = self.stop_chat_server(session_name)
            if not stop_ok:
                return True, f"session killed but chat server cleanup failed: {stop_detail}"
            return True, ""
        if query.state == "unhealthy":
            return False, f"tmux became unresponsive while killing session ({query.detail})"
        time.sleep(0.1)
    return False, f"Session {session_name} did not go away in time."


def delete_archived_session(self, session_name: str) -> tuple[bool, str]:
    query = self.active_session_records_query()
    if query.state == "unhealthy":
        return False, f"tmux is unresponsive, cannot safely delete archived session ({query.detail})"

    active = query.records
    archived = self.archived_session_records(active.keys())
    record = archived.get(session_name)
    if not record:
        return False, "That archived session is not available in this repo."
    log_dir = Path((record.get("log_dir") or "").strip())
    if not log_dir.exists():
        return False, "Archived log directory no longer exists."
    allowed_roots = [
        self.central_log_dir.resolve(),
        self.legacy_log_dir.resolve(),
        (local_state_dir(self.repo_root) / "workspaces").resolve(),
    ]
    try:
        resolved = log_dir.resolve()
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return False, "Archived log directory could not be resolved."
    if not any(root == resolved or root in resolved.parents for root in allowed_roots):
        return False, "Refusing to delete a path outside multiagent log roots."
    try:
        shutil.rmtree(resolved)
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return False, str(exc)
    workspace = record.get("workspace", "")
    delete_session_thinking_data(self.repo_root, session_name, workspace)
    return True, ""
