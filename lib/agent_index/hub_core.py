from __future__ import annotations

import datetime as dt
import json
import os
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

from .state_core import load_hub_settings as load_shared_hub_settings
from .state_core import load_hub_thinking_totals as load_shared_hub_thinking_totals
from .state_core import save_hub_settings as save_shared_hub_settings


def parse_session_dir(name: str) -> str:
    parts = name.split("_")
    if len(parts) >= 3 and all(len(part) == 6 and part.isdigit() for part in parts[-2:]):
        return "_".join(parts[:-2]) or name
    return name


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except Exception:
        return 0


def count_nonempty_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except Exception:
        return 0


def parse_saved_time(value: str) -> float:
    if not value:
        return 0
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(value, fmt).timestamp()
        except Exception:
            pass
    return 0


def format_epoch(epoch: float) -> str:
    if not epoch:
        return ""
    try:
        return dt.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


class HubRuntime:
    def __init__(self, repo_root: Path | str, script_path: Path | str, tmux_socket: str = ""):
        self.repo_root = Path(repo_root).resolve()
        self.script_path = Path(script_path).resolve()
        self.script_dir = self.script_path.parent
        self.multiagent_path = self.script_dir / "multiagent"
        self.central_log_dir = self.repo_root / "logs"
        self.tmux_socket = tmux_socket
        self.tmux_prefix = ["tmux"]
        if tmux_socket:
            self.tmux_prefix.extend(["-L", tmux_socket])

    def tmux_run(self, args, timeout=2):
        return subprocess.run([*self.tmux_prefix, *args], capture_output=True, text=True, timeout=timeout, check=False)

    def tmux_env(self, session_name: str, key: str) -> str:
        result = self.tmux_run(["show-environment", "-t", session_name, key])
        line = result.stdout.strip()
        if result.returncode == 0 and "=" in line:
            return line.split("=", 1)[1]
        return ""

    @staticmethod
    def chat_port_for_session(session_name: str) -> int:
        import hashlib

        digest = int(hashlib.md5(session_name.encode()).hexdigest(), 16)
        return 8200 + (digest % 700)

    def session_index_path(self, session_name: str, workspace: str = "", explicit_log_dir: str = ""):
        roots = []
        for candidate in (explicit_log_dir, str(Path(workspace) / "logs") if workspace else "", str(self.central_log_dir)):
            candidate = (candidate or "").strip()
            if not candidate:
                continue
            try:
                root = Path(candidate).resolve()
            except Exception:
                continue
            if root not in roots:
                roots.append(root)
        best_path = None
        best_epoch = -1
        for root in roots:
            if not root.is_dir():
                continue
            candidates = [root / session_name / ".agent-index.jsonl", *root.glob(f"{session_name}_*/.agent-index.jsonl")]
            for index_path in candidates:
                if not index_path.is_file():
                    continue
                epoch = safe_mtime(index_path)
                if epoch >= best_epoch:
                    best_path = index_path
                    best_epoch = epoch
        return best_path

    @staticmethod
    def host_without_port(host_header: str) -> str:
        host = (host_header or "").strip() or "127.0.0.1"
        if host.startswith("["):
            end = host.find("]")
            return host[: end + 1] if end != -1 else host
        return host.split(":", 1)[0]

    def repo_sessions(self):
        result = self.tmux_run(["list-sessions", "-F", "#{session_name}"])
        if result.returncode != 0:
            return []
        sessions = []
        for name in result.stdout.splitlines():
            if not name:
                continue
            bin_dir = self.tmux_env(name, "MULTIAGENT_BIN_DIR")
            if not bin_dir:
                continue
            try:
                if Path(bin_dir).resolve() != self.script_dir:
                    continue
            except Exception:
                continue
            workspace = self.tmux_env(name, "MULTIAGENT_WORKSPACE")
            explicit_log_dir = self.tmux_env(name, "MULTIAGENT_LOG_DIR")
            attached = self.tmux_run(["display-message", "-p", "-t", name, "#{session_attached}"]).stdout.strip() or "0"
            created_epoch = self.tmux_run(["display-message", "-p", "-t", name, "#{session_created}"]).stdout.strip() or "0"
            try:
                created_at = dt.datetime.fromtimestamp(int(created_epoch)).strftime("%Y-%m-%d %H:%M")
            except Exception:
                created_at = ""
            dead_result = self.tmux_run(["list-panes", "-t", name, "-F", "#{pane_dead}"])
            dead_panes = sum(1 for line in dead_result.stdout.splitlines() if line.strip() == "1")
            agents = []
            for agent in ("claude", "codex", "gemini", "copilot"):
                pane = self.tmux_env(name, f"MULTIAGENT_PANE_{agent.upper()}")
                if pane:
                    agents.append(agent)
            if dead_panes > 0:
                status = "degraded"
            elif attached != "0":
                status = "attached"
            else:
                status = "idle"
            index_path = self.session_index_path(name, workspace, explicit_log_dir)
            sessions.append({
                "name": name,
                "workspace": workspace,
                "created_at": created_at,
                "created_epoch": int(created_epoch) if created_epoch.isdigit() else 0,
                "attached": int(attached) if attached.isdigit() else 0,
                "dead_panes": dead_panes,
                "agents": agents,
                "status": status,
                "chat_port": self.chat_port_for_session(name),
                "chat_count": count_nonempty_lines(index_path) if index_path else 0,
            })
        sessions.sort(key=lambda item: item["created_epoch"], reverse=True)
        return sessions

    def archived_sessions(self, active_names=None):
        active_names = set(active_names or [])
        records = {}
        if not self.central_log_dir.is_dir():
            return []
        for entry in self.central_log_dir.iterdir():
            if not entry.is_dir():
                continue
            meta_path = entry / ".meta"
            index_path = entry / ".agent-index.jsonl"
            if not meta_path.exists() and not index_path.exists():
                continue
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
            session_name = (meta.get("session") or parse_session_dir(entry.name) or "").strip()
            if not session_name or session_name in active_names:
                continue
            workspace = (meta.get("workspace") or "").strip() or str(self.repo_root)
            created_epoch = parse_saved_time(meta.get("created_at", ""))
            updated_epoch = parse_saved_time(meta.get("updated_at", ""))
            updated_epoch = max(updated_epoch, safe_mtime(meta_path), safe_mtime(index_path))
            if not created_epoch:
                created_epoch = updated_epoch
            agents = [
                agent
                for agent in ("claude", "codex", "gemini", "copilot")
                if (entry / f"{agent}.log").exists() or (entry / f"{agent}.ans").exists()
            ]
            if not agents and index_path.exists():
                inferred = set()
                try:
                    with index_path.open("r", encoding="utf-8") as handle:
                        for line in handle:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                item = json.loads(line)
                            except Exception:
                                continue
                            sender = (item.get("sender") or "").strip().lower()
                            if sender in {"claude", "codex", "gemini", "copilot"}:
                                inferred.add(sender)
                            for target in item.get("targets") or []:
                                target = (target or "").strip().lower()
                                if target in {"claude", "codex", "gemini", "copilot"}:
                                    inferred.add(target)
                except Exception:
                    inferred = set()
                agents = [agent for agent in ("claude", "codex", "gemini", "copilot") if agent in inferred]
            record = {
                "name": session_name,
                "workspace": workspace,
                "created_at": meta.get("created_at") or format_epoch(created_epoch),
                "created_epoch": int(created_epoch or 0),
                "updated_at": meta.get("updated_at") or format_epoch(updated_epoch),
                "updated_epoch": int(updated_epoch or 0),
                "dead_panes": 0,
                "attached": 0,
                "agents": agents,
                "status": "archived",
                "chat_port": self.chat_port_for_session(session_name),
                "log_dir": str(entry),
                "chat_count": count_nonempty_lines(index_path) if index_path.exists() else 0,
            }
            existing = records.get(session_name)
            if existing is None or record["updated_epoch"] > existing["updated_epoch"]:
                records[session_name] = record
        sessions = list(records.values())
        sessions.sort(key=lambda item: item["updated_epoch"], reverse=True)
        return sessions

    def load_hub_thinking_totals(self):
        return load_shared_hub_thinking_totals(self.repo_root)

    def compute_hub_stats(self, active_sessions, archived_sessions_data):
        all_sessions = [*active_sessions, *archived_sessions_data]
        total_messages = 0
        message_by_sender = {"user": 0, "claude": 0, "codex": 0, "gemini": 0, "copilot": 0}
        message_by_session = {}
        commit_first_seen = {}
        seen_paths = set()
        index_records = []
        for session in active_sessions:
            index_path = self.session_index_path(
                session.get("name", ""),
                session.get("workspace", ""),
                self.tmux_env(session.get("name", ""), "MULTIAGENT_LOG_DIR"),
            )
            if index_path and index_path.is_file():
                key = str(index_path.resolve())
                if key not in seen_paths:
                    seen_paths.add(key)
                    index_records.append((session.get("name", ""), index_path))
        for session in archived_sessions_data:
            log_dir = (session.get("log_dir") or "").strip()
            if not log_dir:
                continue
            index_path = Path(log_dir) / ".agent-index.jsonl"
            if index_path.is_file():
                key = str(index_path.resolve())
                if key not in seen_paths:
                    seen_paths.add(key)
                    index_records.append((session.get("name", ""), index_path))
        for session_name, index_path in index_records:
            try:
                with index_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except Exception:
                            continue
                        sender = (entry.get("sender") or "").strip().lower()
                        if sender == "system":
                            if entry.get("kind") == "git-commit":
                                commit_key = (
                                    (entry.get("commit_hash") or "").strip()
                                    or f"{session_name}:{(entry.get('msg_id') or '').strip()}"
                                )
                                entry_timestamp = (entry.get("timestamp") or "").strip()
                                previous = commit_first_seen.get(commit_key)
                                if not previous or (
                                    entry_timestamp and (not previous["timestamp"] or entry_timestamp < previous["timestamp"])
                                ):
                                    commit_first_seen[commit_key] = {
                                        "timestamp": entry_timestamp,
                                        "session": session_name,
                                    }
                            continue
                        total_messages += 1
                        message_by_session[session_name] = message_by_session.get(session_name, 0) + 1
                        if sender in message_by_sender:
                            message_by_sender[sender] += 1
            except Exception:
                continue
        commits_by_session = {}
        for commit in commit_first_seen.values():
            commit_session = commit["session"]
            commits_by_session[commit_session] = commits_by_session.get(commit_session, 0) + 1
        thinking_totals = self.load_hub_thinking_totals()
        return {
            "active_sessions": len(active_sessions),
            "archived_sessions": len(archived_sessions_data),
            "total_sessions": len(all_sessions),
            "total_messages": total_messages,
            "messages_by_sender": message_by_sender,
            "messages_by_session": message_by_session,
            "total_commits": len(commit_first_seen),
            "commits_by_session": commits_by_session,
            "total_thinking_seconds": thinking_totals["total_seconds"],
            "thinking_by_agent": thinking_totals["by_agent"],
            "thinking_by_session": thinking_totals["by_session"],
            "thinking_session_count": thinking_totals["session_count"],
        }

    def load_hub_settings(self):
        return load_shared_hub_settings(self.repo_root)

    def save_hub_settings(self, raw):
        return save_shared_hub_settings(self.repo_root, raw)

    def chat_ready(self, chat_port: int) -> bool:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{chat_port}/messages", timeout=0.35) as response:
                return response.status == 200
        except Exception:
            return False

    def stop_chat_server(self, session_name: str):
        chat_port = self.chat_port_for_session(session_name)
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{chat_port}"],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            pids = [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
        except Exception:
            pids = []
        if not pids:
            return
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        for _ in range(15):
            if not self.chat_ready(chat_port):
                return
            time.sleep(0.1)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

    def ensure_chat_server(self, session_name: str):
        chat_port = self.chat_port_for_session(session_name)
        if self.chat_ready(chat_port):
            return True, chat_port, ""
        env = os.environ.copy()
        if self.tmux_socket:
            env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
        try:
            subprocess.Popen(
                [str(self.script_path), "--session", session_name, "--chat", "--follow", "--no-open"],
                cwd=str(self.repo_root),
                env=env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            return False, chat_port, str(exc)
        for _ in range(60):
            if self.chat_ready(chat_port):
                return True, chat_port, ""
            time.sleep(0.1)
        return False, chat_port, "chat server did not become ready"

    def revive_archived_session(self, session_name: str):
        active = {item["name"] for item in self.repo_sessions()}
        if session_name in active:
            return True, ""
        archived = {item["name"]: item for item in self.archived_sessions(active)}
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
        self.stop_chat_server(session_name)
        cmd = [
            str(self.multiagent_path),
            "--session", session_name,
            "--workspace", workspace,
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
            return False, str(exc)
        for _ in range(80):
            if session_name in {item["name"] for item in self.repo_sessions()}:
                return True, ""
            time.sleep(0.15)
        return False, f"Session {session_name} did not come up in time."

    def kill_repo_session(self, session_name: str):
        active = {item["name"] for item in self.repo_sessions()}
        if session_name not in active:
            return False, "That active session is not available in this repo."
        result = self.tmux_run(["kill-session", "-t", session_name], timeout=4)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip() or "tmux kill-session failed"
            return False, detail
        for _ in range(20):
            if session_name not in {item["name"] for item in self.repo_sessions()}:
                self.stop_chat_server(session_name)
                return True, ""
            time.sleep(0.1)
        return False, f"Session {session_name} did not go away in time."
