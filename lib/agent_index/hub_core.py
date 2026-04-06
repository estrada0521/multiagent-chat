from __future__ import annotations
import logging

import datetime as dt
import http.client
import json
import os
import re
import signal
import shutil
import ssl
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .instance_core import agents_from_tmux_env_output
from .instance_core import expected_instance_names as resolve_expected_instance_names
from .state_core import load_hub_settings as load_shared_hub_settings
from .state_core import load_hub_thinking_totals as load_shared_hub_thinking_totals
from .state_core import local_runtime_log_dir
from .state_core import port_is_bindable
from .state_core import resolve_chat_port
from .state_core import save_chat_port_override
from .state_core import local_state_dir
from .state_core import local_workspace_log_dir
from .state_core import save_hub_settings as save_shared_hub_settings
from .state_core import update_thinking_totals_from_statuses as update_shared_thinking_totals_from_statuses
from .state_core import delete_session_thinking_data


def parse_session_dir(name: str) -> str:
    parts = name.split("_")
    if len(parts) >= 3 and all(len(part) == 6 and part.isdigit() for part in parts[-2:]):
        return "_".join(parts[:-2]) or name
    return name


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except (FileNotFoundError, PermissionError):
        return 0
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return 0


def count_nonempty_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return 0


def parse_saved_time(value: str) -> float:
    if not value:
        return 0
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(value, fmt).timestamp()
        except ValueError:
            pass
    return 0


def format_epoch(epoch: float) -> str:
    if not epoch:
        return ""
    try:
        return dt.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return ""


def latest_message_preview(index_path: Path | None) -> dict[str, str]:
    if not index_path or not index_path.is_file():
        return {"sender": "", "text": ""}
    last_sender = ""
    last_text = ""
    try:
        with index_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception as exc:
                    logging.error(f"Unexpected error: {exc}", exc_info=True)
                    continue
                sender = (entry.get("sender") or "").strip()
                if sender == "system":
                    continue
                message = str(entry.get("message") or "").strip()
                if not message:
                    continue
                compact = re.sub(r"^\[From:\s*[^\]]+\]\s*", "", message, flags=re.IGNORECASE)
                compact = re.sub(r"^\[[^\]]*msg-id:[^\]]+\]\s*", "", compact, flags=re.IGNORECASE)
                compact = re.sub(r"\s+", " ", compact)
                compact = re.sub(r"\[Attached:\s*[^\]]+\]", "", compact).strip()
                compact = compact[:140].rstrip()
                if compact:
                    last_sender = sender
                    last_text = compact
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return {"sender": "", "text": ""}
    return {"sender": last_sender, "text": last_text}


def latest_message_preview_from_paths(index_paths: list[Path]) -> dict[str, str]:
    best_sender = ""
    best_text = ""
    best_epoch = -1.0
    for index_path in index_paths:
        preview = latest_message_preview(index_path)
        if not preview["text"]:
            continue
        epoch = safe_mtime(index_path)
        if epoch >= best_epoch:
            best_epoch = epoch
            best_sender = preview["sender"]
            best_text = preview["text"]
    return {"sender": best_sender, "text": best_text}


@dataclass(frozen=True)
class TmuxRunResult:
    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


@dataclass(frozen=True)
class SessionQueryResult:
    records: dict[str, dict]
    state: str  # "ok" | "unhealthy"
    detail: str = ""


@dataclass(frozen=True)
class RepoSessionsQueryResult:
    sessions: list[dict]
    state: str  # "ok" | "unhealthy"
    detail: str = ""


class HubRuntime:
    def __init__(self, repo_root: Path | str, script_path: Path | str, tmux_socket: str = "", hub_port: int = 0):
        self.repo_root = Path(repo_root).resolve()
        self.script_path = Path(script_path).resolve()
        self.script_dir = self.script_path.parent
        self.multiagent_path = self.script_dir / "multiagent"
        self.agent_send_path = self.script_dir / "agent-send"
        self.central_log_dir = local_runtime_log_dir(self.repo_root)
        self.legacy_log_dir = self.repo_root / "logs"
        self.tmux_socket = tmux_socket
        self.hub_port = int(hub_port or 0)
        self.tmux_prefix = ["tmux"]
        if tmux_socket:
            if "/" in tmux_socket:
                self.tmux_prefix.extend(["-S", tmux_socket])
            else:
                self.tmux_prefix.extend(["-L", tmux_socket])
        self._pane_snapshots = {}
        self._pane_last_change = {}
        self.running_grace_seconds = 2.0
        self._launch_locks = {}  # session_name -> threading.Lock
        self._launch_locks_master = threading.Lock()

    def _get_launch_lock(self, session_name: str) -> threading.Lock:
        with self._launch_locks_master:
            if session_name not in self._launch_locks:
                self._launch_locks[session_name] = threading.Lock()
            return self._launch_locks[session_name]

    def tmux_run(self, args, timeout=2) -> TmuxRunResult:
        try:
            res = subprocess.run(
                [*self.tmux_prefix, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return TmuxRunResult(
                args=list(args),
                returncode=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            return TmuxRunResult(
                args=list(args),
                returncode=124,  # Standard timeout exit code
                stdout=exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                stderr=f"tmux command timed out after {timeout} seconds",
                timed_out=True,
            )

    def tmux_env(self, session_name: str, key: str) -> str:
        result = self.tmux_run(["show-environment", "-t", session_name, key])
        line = result.stdout.strip()
        if result.returncode == 0 and "=" in line:
            return line.split("=", 1)[1]
        return ""

    def tmux_env_query(self, session_name: str, key: str) -> tuple[str, bool]:
        """Returns (value, timed_out)"""
        result = self.tmux_run(["show-environment", "-t", session_name, key])
        line = result.stdout.strip()
        if result.returncode == 0 and "=" in line:
            return line.split("=", 1)[1], result.timed_out
        return "", result.timed_out

    def session_agents(self, session_name: str) -> list[str]:
        agents, _ = self.session_agents_query(session_name)
        return agents

    def session_agents_query(self, session_name: str) -> tuple[list[str], bool]:
        """Returns (agents, timed_out)"""
        agents_str, timed_out = self.tmux_env_query(session_name, "MULTIAGENT_AGENTS")
        if timed_out:
            return [], True
        if agents_str:
            return [a.strip() for a in agents_str.split(",") if a.strip()], False

        result = self.tmux_run(["show-environment", "-t", session_name])
        if result.timed_out:
            return [], True
        if result.returncode == 0:
            agents = agents_from_tmux_env_output(result.stdout)
            if agents:
                return agents, False
        return [], False

    @staticmethod
    def expected_instance_names(base_agents: list[str]) -> list[str]:
        return resolve_expected_instance_names(base_agents)

    def session_has_expected_panes(self, session_name: str, expected_instances: list[str]) -> bool:
        if self.tmux_run(["has-session", "-t", f"={session_name}"], timeout=1).returncode != 0:
            return False
        for agent in expected_instances:
            pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
            if not self.tmux_env(session_name, pane_var):
                return False
        return True

    def wait_for_session_instances(self, session_name: str, base_agents: list[str], timeout_seconds: float = 12.0) -> bool:
        expected_instances = self.expected_instance_names(base_agents)
        deadline = time.time() + max(0.5, timeout_seconds)
        while time.time() < deadline:
            if self.session_has_expected_panes(session_name, expected_instances):
                return True
            time.sleep(0.15)
        return self.session_has_expected_panes(session_name, expected_instances)

    def chat_port_for_session(self, session_name: str) -> int:
        return resolve_chat_port(self.repo_root, session_name)

    def session_index_paths(
        self,
        session_name: str,
        workspace: str = "",
        explicit_log_dir: str = "",
        *,
        include_legacy: bool = False,
    ):
        roots = []
        workspace = (workspace or "").strip()
        workspace_candidates = []
        if workspace:
            workspace_path = Path(workspace)
            workspace_candidates.extend(
                [
                    str(local_workspace_log_dir(self.repo_root, workspace_path)),
                    str(workspace_path / "logs"),
                ]
            )
        root_candidates = [
            explicit_log_dir,
            *workspace_candidates,
            str(self.central_log_dir),
        ]
        if include_legacy:
            root_candidates.append(str(self.legacy_log_dir))
        for candidate in root_candidates:
            candidate = (candidate or "").strip()
            if not candidate:
                continue
            try:
                root = Path(candidate).resolve()
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                continue
            if root not in roots:
                roots.append(root)
        found = []
        seen = set()
        for root in roots:
            if not root.is_dir():
                continue
            candidates = [root / session_name / ".agent-index.jsonl", *root.glob(f"{session_name}_*/.agent-index.jsonl")]
            for index_path in candidates:
                if not index_path.is_file():
                    continue
                resolved = str(index_path.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                found.append(index_path)
        found.sort(key=lambda path: (safe_mtime(path), path.stat().st_size if path.exists() else 0), reverse=True)
        return found

    def session_index_path(
        self,
        session_name: str,
        workspace: str = "",
        explicit_log_dir: str = "",
        *,
        include_legacy: bool = False,
    ):
        paths = self.session_index_paths(session_name, workspace, explicit_log_dir, include_legacy=include_legacy)
        return paths[0] if paths else None

    @staticmethod
    def host_without_port(host_header: str) -> str:
        host = (host_header or "").strip() or "127.0.0.1"
        if host.startswith("["):
            end = host.find("]")
            return host[: end + 1] if end != -1 else host
        return host.split(":", 1)[0]

    def _build_session_record(
        self,
        *,
        name: str,
        workspace: str,
        agents: list[str],
        status: str,
        attached: int,
        dead_panes: int,
        created_epoch: int = 0,
        created_at: str = "",
        updated_epoch: int = 0,
        updated_at: str = "",
        explicit_log_dir: str = "",
        index_paths: list[Path] | None = None,
    ) -> dict:
        resolved_paths = list(index_paths or self.session_index_paths(name, workspace, explicit_log_dir))
        preview = latest_message_preview_from_paths(resolved_paths)
        primary_index = resolved_paths[0] if resolved_paths else None
        session_slug = quote(name, safe="")
        return {
            "name": name,
            "workspace": workspace,
            "created_at": created_at,
            "created_epoch": int(created_epoch or 0),
            "updated_at": updated_at,
            "updated_epoch": int(updated_epoch or 0),
            "attached": int(attached or 0),
            "dead_panes": int(dead_panes or 0),
            "agents": list(agents or []),
            "status": status,
            "chat_port": self.chat_port_for_session(name),
            "session_path": f"/session/{session_slug}/",
            "follow_path": f"/session/{session_slug}/?follow=1",
            "log_dir": explicit_log_dir or str(primary_index.parent if primary_index else ""),
            "index_path": str(primary_index) if primary_index else "",
            "chat_count": sum(count_nonempty_lines(path) for path in resolved_paths),
            "latest_message_sender": preview["sender"],
            "latest_message_preview": preview["text"],
        }

    def repo_sessions(self) -> list[dict]:
        res = self.repo_sessions_query()
        return res.sessions

    def repo_sessions_query(self) -> RepoSessionsQueryResult:
        result = self.tmux_run(["list-sessions", "-F", "#{session_name}"])
        if result.timed_out:
            return RepoSessionsQueryResult([], "unhealthy", "tmux list-sessions timed out")
        if result.returncode != 0:
            return RepoSessionsQueryResult([], "ok", "")

        sessions = []
        any_timeout = False
        timeout_detail = ""

        for name in result.stdout.splitlines():
            if not name or any_timeout:
                continue

            bin_dir, t1 = self.tmux_env_query(name, "MULTIAGENT_BIN_DIR")
            if t1:
                any_timeout, timeout_detail = True, f"tmux show-environment (BIN_DIR) timed out for {name}"
                break
            if not bin_dir:
                continue

            try:
                if Path(bin_dir).resolve() != self.script_dir:
                    continue
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                continue

            workspace, t2 = self.tmux_env_query(name, "MULTIAGENT_WORKSPACE")
            explicit_log_dir, t3 = self.tmux_env_query(name, "MULTIAGENT_LOG_DIR")
            r_attached = self.tmux_run(["display-message", "-p", "-t", name, "#{session_attached}"])
            r_created = self.tmux_run(["display-message", "-p", "-t", name, "#{session_created}"])
            r_dead = self.tmux_run(["list-panes", "-t", name, "-F", "#{pane_dead}"])
            agents, t4 = self.session_agents_query(name)

            if t2 or t3 or r_attached.timed_out or r_created.timed_out or r_dead.timed_out or t4:
                any_timeout = True
                timeout_detail = f"tmux query timed out during session scan for {name}"
                break

            attached = r_attached.stdout.strip() or "0"
            created_epoch = r_created.stdout.strip() or "0"
            try:
                created_at = dt.datetime.fromtimestamp(int(created_epoch)).strftime("%Y-%m-%d %H:%M")
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                created_at = ""

            dead_panes = sum(1 for line in r_dead.stdout.splitlines() if line.strip() == "1")

            if dead_panes > 0:
                status = "degraded"
            elif attached != "0":
                status = "attached"
            else:
                status = "idle"

            index_paths = self.session_index_paths(name, workspace, explicit_log_dir)
            sessions.append(
                self._build_session_record(
                    name=name,
                    workspace=workspace,
                    agents=agents,
                    status=status,
                    attached=int(attached) if attached.isdigit() else 0,
                    dead_panes=dead_panes,
                    created_epoch=int(created_epoch) if created_epoch.isdigit() else 0,
                    created_at=created_at,
                    explicit_log_dir=explicit_log_dir,
                    index_paths=index_paths,
                )
            )

        if any_timeout:
            return RepoSessionsQueryResult(sessions, "unhealthy", timeout_detail)

        sessions.sort(key=lambda item: item["created_epoch"], reverse=True)
        return RepoSessionsQueryResult(sessions, "ok", "")

    def archived_sessions(self, active_names: set[str] | list[str] | None = None) -> list[dict]:
        active_names = set(active_names or [])
        records = {}
        log_roots = []
        for candidate in (
            self.central_log_dir,
            self.legacy_log_dir,
            local_state_dir(self.repo_root) / "workspaces",
        ):
            if not candidate or not Path(candidate).is_dir():
                continue
            root = Path(candidate)
            if root not in log_roots:
                log_roots.append(root)
        if not log_roots:
            return []
        for log_root in log_roots:
            entry_iter = log_root.iterdir()
            if log_root.name == "workspaces":
                workspace_roots = [entry for entry in entry_iter if entry.is_dir()]
                entries = []
                for workspace_root in workspace_roots:
                    entries.extend(child for child in workspace_root.iterdir() if child.is_dir())
            else:
                entries = [entry for entry in entry_iter if entry.is_dir()]
            for entry in entries:
                meta_path = entry / ".meta"
                index_path = entry / ".agent-index.jsonl"
                try:
                    if not meta_path.exists() and not index_path.exists():
                        continue
                except OSError:
                    continue
                meta = {}
                if meta_path.exists():
                    try:
                        raw_meta = meta_path.read_text(encoding="utf-8")
                        meta = json.loads(raw_meta)
                    except json.JSONDecodeError:
                        try:
                            meta, _ = json.JSONDecoder().raw_decode(raw_meta)
                        except Exception:
                            meta = {}
                    except (OSError, FileNotFoundError):
                        meta = {}
                    except Exception as exc:
                        logging.error(f"Unexpected error: {exc}", exc_info=True)
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
                agents = []
                seen_agents = set()
                meta_agents = meta.get("agents")
                if isinstance(meta_agents, list) and meta_agents:
                    for a in meta_agents:
                        name = str(a).strip()
                        if name and name not in seen_agents:
                            seen_agents.add(name)
                            agents.append(name)
                if not agents:
                    # Collect candidate files with their mtimes so we can
                    # filter out stale files left behind by removed agents.
                    # The save hook writes all current agent logs at roughly
                    # the same time, so files from the latest save cluster
                    # together while old ones have much earlier mtimes.
                    _candidates = []
                    try:
                        for f in sorted(entry.iterdir()):
                            if f.suffix in (".log", ".ans") and not f.name.startswith("."):
                                try:
                                    _candidates.append((f.stem, f.stat().st_mtime))
                                except OSError:
                                    continue
                    except OSError:
                        pass
                    if _candidates:
                        _max_mt = max(mt for _, mt in _candidates)
                        for name_stem, mt in _candidates:
                            if _max_mt - mt <= 60 and name_stem not in seen_agents:
                                seen_agents.add(name_stem)
                                agents.append(name_stem)
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
                                if sender and sender not in ("user", "system"):
                                    inferred.add(sender)
                                for target in item.get("targets") or []:
                                    target = (target or "").strip().lower()
                                    if target and target not in ("user", "system"):
                                        inferred.add(target)
                    except (OSError, FileNotFoundError):
                        inferred = set()
                    except Exception as exc:
                        logging.error(f"Unexpected error: {exc}", exc_info=True)
                        inferred = set()
                    agents = sorted(inferred)
                record = self._build_session_record(
                    name=session_name,
                    workspace=workspace,
                    agents=agents,
                    status="archived",
                    attached=0,
                    dead_panes=0,
                    created_epoch=int(created_epoch or 0),
                    created_at=meta.get("created_at") or format_epoch(created_epoch),
                    updated_epoch=int(updated_epoch or 0),
                    updated_at=meta.get("updated_at") or format_epoch(updated_epoch),
                    explicit_log_dir=str(entry),
                    index_paths=[index_path] if index_path.exists() else [],
                )
                existing = records.get(session_name)
                if existing is None or record["updated_epoch"] > existing["updated_epoch"]:
                    records[session_name] = record
        sessions = list(records.values())
        sessions.sort(key=lambda item: item["updated_epoch"], reverse=True)
        return sessions

    def active_session_records(self) -> dict[str, dict]:
        res = self.active_session_records_query()
        return res.records

    def active_session_records_query(self) -> SessionQueryResult:
        res = self.repo_sessions_query()
        return SessionQueryResult(
            records={item["name"]: item for item in res.sessions},
            state=res.state,
            detail=res.detail,
        )

    def archived_session_records(self, active_names: set[str] | list[str] | None = None) -> dict[str, dict]:
        return {item["name"]: item for item in self.archived_sessions(active_names)}

    def load_hub_thinking_totals(self) -> dict:
        return load_shared_hub_thinking_totals(self.repo_root)

    def session_agent_statuses(self, session_name: str, agents: list[str]) -> dict[str, str]:
        result = {}
        for agent in agents:
            pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
            try:
                pane_id = self.tmux_env(session_name, pane_var)
                if not pane_id:
                    result[agent] = "offline"
                    continue
                dead = self.tmux_run(["display-message", "-p", "-t", pane_id, "#{pane_dead}"]).stdout.strip()
                if dead == "1":
                    result[agent] = "dead"
                    self._pane_snapshots.pop(pane_id, None)
                    self._pane_last_change.pop(pane_id, None)
                    continue
                content = self.tmux_run(["capture-pane", "-p", "-S", "-20", "-t", pane_id]).stdout
                # Skip top 10 lines for copilot to avoid false running detection from animated UI
                agent_base = agent.split("-")[0] if "-" in agent else agent
                if agent_base == "copilot":
                    content_lines = content.splitlines()
                    content = "\n".join(content_lines[10:]) if len(content_lines) > 10 else ""
                now = time.monotonic()
                prev = self._pane_snapshots.get(pane_id)
                self._pane_snapshots[pane_id] = content
                if prev is not None and content != prev:
                    self._pane_last_change[pane_id] = now
                    result[agent] = "running"
                else:
                    last_change = self._pane_last_change.get(pane_id, 0.0)
                    result[agent] = "running" if (now - last_change) < self.running_grace_seconds else "idle"
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                result[agent] = "offline"
        return result

    def compute_hub_stats(self, active_sessions: list[dict], archived_sessions_data: list[dict]) -> dict:
        for session in active_sessions:
            try:
                statuses = self.session_agent_statuses(session.get("name", ""), list(session.get("agents") or []))
                update_shared_thinking_totals_from_statuses(
                    self.repo_root,
                    session.get("name", ""),
                    session.get("workspace", ""),
                    statuses,
                )
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                pass
        all_sessions = [*active_sessions, *archived_sessions_data]
        total_messages = 0
        message_by_sender = {}
        message_by_session = {}
        commit_first_seen = {}
        daily_messages = {}
        daily_messages_user = {}
        daily_messages_agent = {}
        seen_paths = set()
        seen_message_keys = set()
        index_records = []
        for session in active_sessions:
            index_paths = self.session_index_paths(
                session.get("name", ""),
                session.get("workspace", ""),
                self.tmux_env(session.get("name", ""), "MULTIAGENT_LOG_DIR"),
            )
            for index_path in index_paths:
                if not index_path.is_file():
                    continue
                key = str(index_path.resolve())
                if key not in seen_paths:
                    seen_paths.add(key)
                    index_records.append((session.get("name", ""), index_path))
        for session in archived_sessions_data:
            index_paths = self.session_index_paths(
                session.get("name", ""),
                session.get("workspace", ""),
                session.get("log_dir", ""),
                include_legacy=True,
            )
            for index_path in index_paths:
                if not index_path.is_file():
                    continue
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
                        except Exception as exc:
                            logging.error(f"Unexpected error: {exc}", exc_info=True)
                            continue
                        msg_key = (
                            (entry.get("msg_id") or "").strip()
                            or "|".join(
                                [
                                    session_name,
                                    (entry.get("timestamp") or "").strip(),
                                    (entry.get("sender") or "").strip(),
                                    json.dumps(entry.get("targets") or [], ensure_ascii=False, sort_keys=True),
                                    (entry.get("message") or "").strip(),
                                ]
                            )
                        )
                        if msg_key in seen_message_keys:
                            continue
                        seen_message_keys.add(msg_key)
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
                        if sender:
                            base_sender = re.sub(r"-\d+$", "", sender)
                            message_by_sender[base_sender] = message_by_sender.get(base_sender, 0) + 1
                        ts = (entry.get("timestamp") or "").strip()
                        if ts and len(ts) >= 10:
                            date_key = ts[:10]
                            daily_messages[date_key] = daily_messages.get(date_key, 0) + 1
                            if sender == "user":
                                daily_messages_user[date_key] = daily_messages_user.get(date_key, 0) + 1
                            else:
                                daily_messages_agent[date_key] = daily_messages_agent.get(date_key, 0) + 1
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                continue
        commits_by_session = {}
        daily_commits = {}
        for commit in commit_first_seen.values():
            commit_session = commit["session"]
            commits_by_session[commit_session] = commits_by_session.get(commit_session, 0) + 1
            ts = (commit.get("timestamp") or "").strip()
            if ts and len(ts) >= 10:
                date_key = ts[:10]
                daily_commits[date_key] = daily_commits.get(date_key, 0) + 1
        thinking_totals = self.load_hub_thinking_totals()
        daily_thinking = thinking_totals.get("daily_thinking", {})

        def cumulative_series(daily_source):
            total = 0
            series = []
            for date_key in sorted(daily_source):
                total += max(0, int(daily_source.get(date_key, 0) or 0))
                series.append({"date": date_key, "value": total})
            return series

        return {
            "active_sessions": len(active_sessions),
            "archived_sessions": len(archived_sessions_data),
            "total_sessions": len(all_sessions),
            "daily_messages": daily_messages,
            "daily_messages_user": daily_messages_user,
            "daily_messages_agent": daily_messages_agent,
            "total_messages": total_messages,
            "messages_by_sender": message_by_sender,
            "messages_by_session": message_by_session,
            "total_commits": len(commit_first_seen),
            "commits_by_session": commits_by_session,
            "total_thinking_seconds": thinking_totals["total_seconds"],
            "thinking_by_agent": thinking_totals["by_agent"],
            "thinking_by_session": thinking_totals["by_session"],
            "thinking_session_count": thinking_totals["session_count"],
            "daily_thinking": daily_thinking,
            "daily_commits": daily_commits,
            "cumulative_messages_all": cumulative_series(daily_messages),
            "cumulative_messages_user": cumulative_series(daily_messages_user),
            "cumulative_messages_agent": cumulative_series(daily_messages_agent),
            "cumulative_thinking": cumulative_series(daily_thinking),
            "cumulative_commits": cumulative_series(daily_commits),
        }

    def load_hub_settings(self) -> dict:
        return load_shared_hub_settings(self.repo_root)

    def save_hub_settings(self, raw: dict) -> dict:
        return save_shared_hub_settings(self.repo_root, raw)

    def chat_ready(self, chat_port: int) -> bool:
        import socket as _sock
        try:
            with _sock.create_connection(('127.0.0.1', chat_port), timeout=0.35):
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
                conn.request("GET", f"/session-state?ts={int(time.time() * 1000)}", headers={"Host": f"127.0.0.1:{chat_port}"})
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
        return True

    def stop_chat_server(self, session_name: str) -> tuple[bool, str]:
        chat_port = self.chat_port_for_session(session_name)
        try:
            result = subprocess.run(
                ["lsof", "-nP", "-tiTCP", f":{chat_port}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            pids = [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"lsof failed: {exc}"
        if not pids:
            return True, ""
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError as exc:
                logging.warning("SIGTERM pid %d failed: %s", pid, exc)
        for _ in range(15):
            if not self.chat_ready(chat_port):
                return True, ""
            time.sleep(0.1)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as exc:
                logging.warning("SIGKILL pid %d failed: %s", pid, exc)
        if self.chat_ready(chat_port):
            return False, f"chat server on port {chat_port} still running after SIGKILL"
        return True, ""

    def _chat_launch_workspace(self, session_name: str) -> tuple[str, bool]:
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

    def _chat_launch_session_dir(self, session_name: str, workspace: str, explicit_log_dir: str) -> Path:
        repo_session_dir = self.repo_root / "logs" / session_name
        if repo_session_dir.is_dir():
            return repo_session_dir
        existing_index = self.session_index_path(
            session_name,
            workspace,
            explicit_log_dir,
            include_legacy=True,
        )
        if existing_index is not None:
            return existing_index.parent
        log_root = (explicit_log_dir or "").strip()
        if not log_root and workspace:
            log_root = str(Path(workspace) / "logs")
        if not log_root or log_root == "/logs":
            log_root = str(self.repo_root / "logs")
        return Path(log_root) / session_name

    def _chat_launch_env(self) -> dict[str, str]:
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

    def ensure_chat_server(self, session_name: str) -> tuple[bool, int, str]:
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
            if not port_is_bindable(chat_port):
                # Try to see if it's our server but matches() was wrong (race condition)
                if self.chat_ready(chat_port) and self.chat_server_matches(session_name, chat_port):
                    return True, chat_port, ""
                
                # Still busy? Try to find it or pick a new one, but be conservative
                for candidate in range(chat_port, chat_port + 10):
                    if self.chat_ready(candidate) and self.chat_server_matches(session_name, candidate):
                        save_chat_port_override(self.repo_root, session_name, candidate)
                        return True, candidate, ""
                    if port_is_bindable(candidate):
                        save_chat_port_override(self.repo_root, session_name, candidate)
                        chat_port = candidate
                        break

            workspace, workspace_timed_out = self._chat_launch_workspace(session_name)
            explicit_log_dir, log_dir_timed_out = self.tmux_env_query(session_name, "MULTIAGENT_LOG_DIR")
            targets, targets_timed_out = self.session_agents_query(session_name)
            if workspace_timed_out or log_dir_timed_out or targets_timed_out:
                return False, chat_port, "tmux query timed out while preparing chat server launch"
            session_dir = self._chat_launch_session_dir(session_name, workspace, explicit_log_dir)
            index_path = session_dir / ".agent-index.jsonl"
            env = self._chat_launch_env()
            try:
                subprocess.Popen(
                    [
                        sys.executable,
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
                time.sleep(0.1)
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
