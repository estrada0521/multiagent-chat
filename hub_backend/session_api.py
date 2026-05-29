from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from backend_core.access.settings import local_runtime_log_dir, port_is_bindable, save_chat_port_override


@dataclass(frozen=True)
class HubSessionApiContext:
    repo_root: Path
    hub: object
    hub_port: int
    all_agent_names: Sequence[str]
    active_session_records_query: Callable
    archived_session_records: Callable
    ensure_chat_server: Callable
    delete_archived_session: Callable


class HubSessionApi:
    def __init__(self, ctx: HubSessionApiContext):
        self.ctx = ctx

    def session_logs_dir(self, session_name: str) -> Path:
        return local_runtime_log_dir(self.ctx.repo_root) / str(session_name or "").strip()

    def read_json_file(self, path: Path) -> dict:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def resolve_session_chat_target(self, session_name: str) -> dict:
        query = self.ctx.active_session_records_query()
        if session_name in query.records:
            ok, chat_port, detail = self.ctx.ensure_chat_server(session_name)
            if not ok:
                return {"status": "error", "detail": detail}
            return {
                "status": "ok",
                "chat_port": chat_port,
                "session_record": query.records.get(session_name, {}),
            }
        if query.state == "unhealthy":
            return {"status": "unhealthy", "detail": query.detail}
        return {"status": "missing"}

    def format_session_timestamp(self, epoch: int | None = None) -> str:
        ts = int(epoch or time.time())
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))

    def unique_session_name_for_workspace(self, workspace: str) -> str:
        raw_name = Path(workspace).name or "session"
        base = re.sub(r"[^a-zA-Z0-9_.\-]", "-", raw_name).strip(".-")[:64] or "session"
        query = self.ctx.active_session_records_query()
        existing = set(query.records.keys())
        try:
            existing.update(self.ctx.archived_session_records(existing).keys())
        except Exception:
            pass
        candidate = base
        suffix = 2
        while candidate in existing or self.session_logs_dir(candidate).exists():
            suffix_text = f"-{suffix}"
            candidate = f"{base[:max(1, 64 - len(suffix_text))]}{suffix_text}"
            suffix += 1
        return candidate

    def write_session_metadata(self, session_name: str, workspace: str, agents: list[str]) -> dict:
        """Write .meta and .agent-index.jsonl (no .pending-launch.json)."""
        session_dir = self.session_logs_dir(session_name)
        session_dir.mkdir(parents=True, exist_ok=True)
        index_path = session_dir / ".agent-index.jsonl"
        index_path.touch(exist_ok=True)
        meta_path = session_dir / ".meta"
        existing_meta = self.read_json_file(meta_path) if meta_path.is_file() else {}
        created_at = str(existing_meta.get("created_at") or "").strip() or self.format_session_timestamp()
        updated_at = self.format_session_timestamp()
        meta_payload = {
            "session": session_name,
            "workspace": workspace,
            "agents": list(agents or []),
            "created_at": created_at,
            "updated_at": updated_at,
        }
        meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {
            "session_dir": session_dir,
            "index_path": index_path,
            "created_at": created_at,
            "updated_at": updated_at,
        }

    def build_active_session_record(
        self,
        session_name: str,
        workspace: str,
        *,
        created_at: str = "",
        updated_at: str = "",
    ) -> dict:
        """Build a minimal session record for a newly-started active session."""
        session_dir = self.session_logs_dir(session_name)
        index_path = session_dir / ".agent-index.jsonl"
        now_epoch = int(time.time())
        record = self.ctx.hub._build_session_record(
            name=session_name,
            workspace=workspace,
            agents=[],
            status="idle",
            attached=0,
            dead_panes=0,
            created_epoch=now_epoch,
            created_at=created_at or self.format_session_timestamp(now_epoch),
            updated_epoch=now_epoch,
            updated_at=updated_at or self.format_session_timestamp(now_epoch),
            preferred_index_path=index_path,
        )
        record["running_agents"] = []
        record["is_running"] = True
        return record

    def running_agents_from_session_state(self, session_state: dict | None) -> list[str]:
        if not isinstance(session_state, dict):
            return []
        statuses = session_state.get("statuses")
        if not isinstance(statuses, dict):
            return []
        running: list[str] = []
        for agent, status in statuses.items():
            agent_name = str(agent or "").strip()
            if not agent_name:
                continue
            if str(status or "").strip().lower() == "running":
                running.append(agent_name)
        return running

    def ensure_active_chat_server(self, session_name: str, workspace: str) -> tuple[bool, int, str]:
        """Start a chat server with SESSION_IS_ACTIVE=1 for a session whose tmux is already running."""
        lock = self.ctx.hub._get_launch_lock(session_name)
        with lock:
            chat_port = self.ctx.hub.chat_port_for_session(session_name)
            if self.ctx.hub.chat_ready(chat_port):
                state = self.ctx.hub.chat_server_state(chat_port)
                if state and str(state.get("session") or "").strip() == session_name:
                    return True, chat_port, ""
                stop_ok, stop_detail = self.ctx.hub.stop_chat_server(session_name)
                if not stop_ok:
                    return False, chat_port, stop_detail
            if not port_is_bindable(chat_port):
                for candidate in range(chat_port, chat_port + 10):
                    if self.ctx.hub.chat_ready(candidate):
                        state = self.ctx.hub.chat_server_state(candidate)
                        if state and str(state.get("session") or "").strip() == session_name:
                            save_chat_port_override(self.ctx.repo_root, session_name, candidate)
                            return True, candidate, ""
                    if port_is_bindable(candidate):
                        save_chat_port_override(self.ctx.repo_root, session_name, candidate)
                        chat_port = candidate
                        break
            session_dir = self.ctx.hub._chat_launch_session_dir(session_name, workspace, "")
            index_path = session_dir / ".agent-index.jsonl"
            index_path.touch(exist_ok=True)
            env = self.ctx.hub._chat_launch_env()
            env["MULTIAGENT_INDEX_PATH"] = str(index_path)
            env["SESSION_IS_ACTIVE"] = "1"
            try:
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "server.server",
                        str(index_path),
                        "2000",
                        session_name,
                        "1",
                        str(chat_port),
                        str(self.ctx.hub.agent_send_path),
                        workspace,
                        str(session_dir.parent),
                        "",
                        self.ctx.hub.tmux_socket,
                        str(self.ctx.hub_port),
                    ],
                    cwd=workspace or str(self.ctx.repo_root),
                    env=env,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                return False, chat_port, str(exc)
            for _ in range(80):
                if self.ctx.hub.chat_ready(chat_port):
                    state = self.ctx.hub.chat_server_state(chat_port)
                    if state and str(state.get("session") or "").strip() == session_name:
                        return True, chat_port, ""
                time.sleep(0.05)
            return False, chat_port, "active chat server did not become ready"
