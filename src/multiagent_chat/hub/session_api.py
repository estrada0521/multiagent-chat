from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from ..runtime.state import local_runtime_log_dir, port_is_bindable, save_chat_port_override


_PENDING_LAUNCH_FILE = ".pending-launch.json"


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

    def pending_launch_path(self, session_name: str) -> Path:
        return self.session_logs_dir(session_name) / _PENDING_LAUNCH_FILE

    def read_json_file(self, path: Path) -> dict:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def read_pending_launch(self, session_name: str) -> dict:
        path = self.pending_launch_path(session_name)
        if not path.is_file():
            return {}
        data = self.read_json_file(path)
        if not data:
            return {}
        pending_session = str(data.get("session") or "").strip()
        if pending_session and pending_session != session_name:
            return {}
        return data

    def is_pending_launch_session(self, session_name: str) -> bool:
        return bool(self.read_pending_launch(session_name))

    def pending_session_record(self, session_name: str) -> dict | None:
        pending_cfg = self.read_pending_launch(session_name)
        if not pending_cfg:
            return None
        workspace = str(pending_cfg.get("workspace") or "").strip()
        if not workspace:
            return None
        targets = [
            str(item).strip()
            for item in (pending_cfg.get("available_agents") or self.ctx.all_agent_names)
            if str(item).strip()
        ]
        return self.build_pending_session_record(
            session_name,
            workspace,
            targets,
            created_at=str(pending_cfg.get("created_at") or ""),
            updated_at=str(pending_cfg.get("updated_at") or ""),
        )

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

        pending_record = self.pending_session_record(session_name)
        if pending_record is not None:
            workspace = str(pending_record.get("workspace") or "").strip()
            targets = [str(item).strip() for item in (pending_record.get("agents") or []) if str(item).strip()]
            ok, chat_port, detail = self.ensure_pending_chat_server(session_name, workspace, targets)
            if not ok:
                return {"status": "error", "detail": detail}
            return {
                "status": "ok",
                "chat_port": chat_port,
                "session_record": pending_record,
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

    def write_pending_session_files(self, session_name: str, workspace: str, agents: list[str]) -> dict:
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
        pending_payload = {
            "session": session_name,
            "workspace": workspace,
            "available_agents": list(agents or []),
            "created_at": created_at,
            "updated_at": updated_at,
        }
        self.pending_launch_path(session_name).write_text(
            json.dumps(pending_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "session_dir": session_dir,
            "index_path": index_path,
            "created_at": created_at,
            "updated_at": updated_at,
        }

    def build_pending_session_record(
        self,
        session_name: str,
        workspace: str,
        agents: list[str],
        *,
        created_at: str = "",
        updated_at: str = "",
    ) -> dict:
        session_dir = self.session_logs_dir(session_name)
        index_path = session_dir / ".agent-index.jsonl"
        now_epoch = int(time.time())
        record = self.ctx.hub._build_session_record(
            name=session_name,
            workspace=workspace,
            agents=list(agents or []),
            status="pending",
            attached=0,
            dead_panes=0,
            created_epoch=now_epoch,
            created_at=created_at or self.format_session_timestamp(now_epoch),
            updated_epoch=now_epoch,
            updated_at=updated_at or self.format_session_timestamp(now_epoch),
            preferred_index_path=index_path,
        )
        record["launch_pending"] = True
        record["running_agents"] = []
        record["is_running"] = False
        return record

    def pending_chat_server_matches(self, session_name: str, chat_port: int) -> bool:
        state = self.ctx.hub.chat_server_state(chat_port)
        if not state:
            return False
        return str(state.get("session") or "").strip() == session_name

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

    def ensure_pending_chat_server(self, session_name: str, workspace: str, targets: list[str]) -> tuple[bool, int, str]:
        lock = self.ctx.hub._get_launch_lock(session_name)
        with lock:
            chat_port = self.ctx.hub.chat_port_for_session(session_name)
            if self.ctx.hub.chat_ready(chat_port) and self.pending_chat_server_matches(session_name, chat_port):
                return True, chat_port, ""
            if self.ctx.hub.chat_ready(chat_port):
                stop_ok, stop_detail = self.ctx.hub.stop_chat_server(session_name)
                if not stop_ok:
                    return False, chat_port, stop_detail
            if not port_is_bindable(chat_port):
                for candidate in range(chat_port, chat_port + 10):
                    if self.ctx.hub.chat_ready(candidate) and self.pending_chat_server_matches(session_name, candidate):
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
            env["SESSION_IS_ACTIVE"] = "0"
            try:
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "multiagent_chat.chat.server",
                        str(index_path),
                        "2000",
                        "",
                        session_name,
                        "1",
                        str(chat_port),
                        str(self.ctx.hub.agent_send_path),
                        workspace,
                        str(session_dir.parent),
                        ",".join(targets or []),
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
                if self.ctx.hub.chat_ready(chat_port) and self.pending_chat_server_matches(session_name, chat_port):
                    return True, chat_port, ""
                time.sleep(0.05)
            return False, chat_port, "pending chat server did not become ready"

    def delete_pending_draft_session(self, session_name: str) -> tuple[bool, str]:
        try:
            stop_ok, stop_detail = self.ctx.hub.stop_chat_server(session_name)
        except Exception as exc:
            stop_ok, stop_detail = False, str(exc)
        if not stop_ok:
            chat_port = self.ctx.hub.chat_port_for_session(session_name)
            if self.ctx.hub.chat_ready(chat_port):
                return False, stop_detail or "pending chat server cleanup failed"
        ok, detail = self.ctx.delete_archived_session(session_name)
        if not ok:
            return False, detail
        return True, ""
