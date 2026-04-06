from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import subprocess
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

from .jsonl_append import append_jsonl_entry
from .redacted_placeholder import agent_index_entry_omit_for_redacted
from .state_core import local_state_dir

CRON_JOBS_FILENAME = ".cron-jobs.json"
DEFAULT_REPLY_TIMEOUT_SEC = 10 * 60
DEFAULT_REMINDER_GRACE_SEC = 5 * 60
SCHEDULER_POLL_SEC = 15


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _now_ts() -> str:
    return _now_local().strftime("%Y-%m-%d %H:%M:%S")


def cron_jobs_path(repo_root: Path | str) -> Path:
    path = local_state_dir(repo_root) / CRON_JOBS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _cron_lock_path(repo_root: Path | str) -> Path:
    path = local_state_dir(repo_root) / ".cron-jobs.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextlib.contextmanager
def _cron_lock(repo_root: Path | str):
    lock_path = _cron_lock_path(repo_root)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _write_json_atomic(path: Path, payload: dict):
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex[:8]}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _normalize_bool(value, default=False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_time(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) != 5 or raw[2] != ":":
        return ""
    hh = raw[:2]
    mm = raw[3:]
    if not (hh.isdigit() and mm.isdigit()):
        return ""
    hour = int(hh)
    minute = int(mm)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return ""
    return f"{hour:02d}:{minute:02d}"


def _normalize_job(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    job_id = str(raw.get("id") or "").strip()
    if not job_id:
        return None
    time_str = _normalize_time(raw.get("time"))
    session_name = str(raw.get("session") or "").strip()
    agent = str(raw.get("agent") or "").strip()
    prompt = str(raw.get("prompt") or "").replace("\r\n", "\n").strip()
    name = str(raw.get("name") or "").strip()
    if not name:
        parts = [session_name, agent, time_str]
        name = " / ".join(part for part in parts if part) or f"cron-{job_id[:6]}"
    return {
        "id": job_id,
        "name": name,
        "session": session_name,
        "agent": agent,
        "time": time_str,
        "prompt": prompt,
        "enabled": _normalize_bool(raw.get("enabled"), True),
        "created_at": str(raw.get("created_at") or "").strip(),
        "updated_at": str(raw.get("updated_at") or "").strip(),
        "last_run_at": str(raw.get("last_run_at") or "").strip(),
        "last_run_slot": str(raw.get("last_run_slot") or "").strip(),
        "last_status": str(raw.get("last_status") or "").strip(),
        "last_status_detail": str(raw.get("last_status_detail") or "").strip(),
        "last_reply_at": str(raw.get("last_reply_at") or "").strip(),
        "last_reminded_at": str(raw.get("last_reminded_at") or "").strip(),
        "pending_run_id": str(raw.get("pending_run_id") or "").strip(),
        "pending_started_at": str(raw.get("pending_started_at") or "").strip(),
        "last_trigger": str(raw.get("last_trigger") or "").strip(),
    }


def _load_jobs_unlocked(repo_root: Path | str) -> list[dict]:
    path = cron_jobs_path(repo_root)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return []
    jobs = payload.get("jobs") if isinstance(payload, dict) else []
    if not isinstance(jobs, list):
        return []
    normalized = []
    for raw in jobs:
        item = _normalize_job(raw)
        if item is not None:
            normalized.append(item)
    return normalized


def _save_jobs_unlocked(repo_root: Path | str, jobs: list[dict]):
    path = cron_jobs_path(repo_root)
    _write_json_atomic(path, {"jobs": jobs})


def load_cron_jobs(repo_root: Path | str) -> list[dict]:
    with _cron_lock(repo_root):
        return _load_jobs_unlocked(repo_root)


def _job_next_run_dt(job: dict, now: datetime | None = None) -> datetime | None:
    time_str = _normalize_time(job.get("time"))
    if not time_str:
        return None
    now = (now or _now_local()).astimezone()
    hour, minute = (int(part) for part in time_str.split(":", 1))
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _current_slot_key(job: dict, now: datetime | None = None) -> str:
    time_str = _normalize_time(job.get("time"))
    if not time_str:
        return ""
    now = (now or _now_local()).astimezone()
    hour, minute = (int(part) for part in time_str.split(":", 1))
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now < candidate:
        return ""
    return candidate.strftime("%Y-%m-%d %H:%M")


def _job_display(job: dict, now: datetime | None = None) -> dict:
    item = dict(job)
    next_dt = _job_next_run_dt(item, now=now)
    item["next_run_at"] = next_dt.strftime("%Y-%m-%d %H:%M") if next_dt else ""
    item["schedule_label"] = f"Daily {item.get('time') or '--:--'}"
    return item


def list_cron_jobs(repo_root: Path | str, *, now: datetime | None = None) -> list[dict]:
    jobs = load_cron_jobs(repo_root)
    rendered = [_job_display(job, now=now) for job in jobs]
    rendered.sort(key=lambda item: (item.get("time") or "99:99", item.get("name") or "", item.get("id") or ""))
    return rendered


def save_cron_job(repo_root: Path | str, raw: dict) -> dict:
    session_name = str(raw.get("session") or "").strip()
    agent = str(raw.get("agent") or "").strip()
    prompt = str(raw.get("prompt") or "").replace("\r\n", "\n").strip()
    time_str = _normalize_time(raw.get("time"))
    if not session_name:
        raise ValueError("session required")
    if not agent:
        raise ValueError("agent required")
    if not time_str:
        raise ValueError("daily time required")
    if not prompt:
        raise ValueError("prompt required")

    now_ts = _now_ts()
    job_id = str(raw.get("id") or "").strip()
    enabled = _normalize_bool(raw.get("enabled"), True)
    name = str(raw.get("name") or "").strip()

    with _cron_lock(repo_root):
        jobs = _load_jobs_unlocked(repo_root)
        existing = None
        for idx, job in enumerate(jobs):
            if job.get("id") == job_id and job_id:
                existing = (idx, job)
                break
        if existing is None:
            job_id = uuid.uuid4().hex[:12]
            item = _normalize_job({
                "id": job_id,
                "name": name,
                "session": session_name,
                "agent": agent,
                "time": time_str,
                "prompt": prompt,
                "enabled": enabled,
                "created_at": now_ts,
                "updated_at": now_ts,
                "last_status": "",
                "last_status_detail": "",
            })
            jobs.append(item)
        else:
            idx, prior = existing
            item = dict(prior)
            item.update({
                "name": name or prior.get("name") or "",
                "session": session_name,
                "agent": agent,
                "time": time_str,
                "prompt": prompt,
                "enabled": enabled,
                "updated_at": now_ts,
            })
            item = _normalize_job(item)
            jobs[idx] = item
        _save_jobs_unlocked(repo_root, jobs)
    return _job_display(item)


def delete_cron_job(repo_root: Path | str, job_id: str) -> bool:
    target_id = str(job_id or "").strip()
    if not target_id:
        return False
    with _cron_lock(repo_root):
        jobs = _load_jobs_unlocked(repo_root)
        new_jobs = [job for job in jobs if job.get("id") != target_id]
        if len(new_jobs) == len(jobs):
            return False
        _save_jobs_unlocked(repo_root, new_jobs)
        return True


def get_cron_job(repo_root: Path | str, job_id: str) -> dict | None:
    target_id = str(job_id or "").strip()
    if not target_id:
        return None
    for job in load_cron_jobs(repo_root):
        if job.get("id") == target_id:
            return _job_display(job)
    return None


def _update_job_fields(repo_root: Path | str, job_id: str, **fields) -> dict | None:
    target_id = str(job_id or "").strip()
    if not target_id:
        return None
    with _cron_lock(repo_root):
        jobs = _load_jobs_unlocked(repo_root)
        updated = None
        for idx, job in enumerate(jobs):
            if job.get("id") != target_id:
                continue
            item = dict(job)
            item.update(fields)
            item["updated_at"] = _now_ts()
            item = _normalize_job(item)
            jobs[idx] = item
            updated = item
            break
        if updated is None:
            return None
        _save_jobs_unlocked(repo_root, jobs)
        return _job_display(updated)


def set_cron_enabled(repo_root: Path | str, job_id: str, enabled: bool) -> dict | None:
    return _update_job_fields(repo_root, job_id, enabled=bool(enabled))


def claim_due_jobs(repo_root: Path | str, *, now: datetime | None = None) -> list[dict]:
    now = (now or _now_local()).astimezone()
    now_ts = now.strftime("%Y-%m-%d %H:%M:%S")
    claimed = []
    with _cron_lock(repo_root):
        jobs = _load_jobs_unlocked(repo_root)
        changed = False
        for idx, job in enumerate(jobs):
            if not job.get("enabled"):
                continue
            if job.get("pending_run_id"):
                continue
            slot_key = _current_slot_key(job, now=now)
            if not slot_key or job.get("last_run_slot") == slot_key:
                continue
            item = dict(job)
            item.update({
                "last_run_slot": slot_key,
                "last_run_at": now_ts,
                "last_status": "queued",
                "last_status_detail": "Queued scheduled run",
                "pending_run_id": uuid.uuid4().hex[:10],
                "pending_started_at": now_ts,
                "last_reminded_at": "",
                "last_trigger": "scheduled",
                "updated_at": now_ts,
            })
            item = _normalize_job(item)
            jobs[idx] = item
            claimed.append(item)
            changed = True
        if changed:
            _save_jobs_unlocked(repo_root, jobs)
    return [_job_display(item, now=now) for item in claimed]


def claim_manual_job(repo_root: Path | str, job_id: str) -> tuple[dict | None, str]:
    target_id = str(job_id or "").strip()
    if not target_id:
        return None, "job not found"
    now_ts = _now_ts()
    with _cron_lock(repo_root):
        jobs = _load_jobs_unlocked(repo_root)
        for idx, job in enumerate(jobs):
            if job.get("id") != target_id:
                continue
            if job.get("pending_run_id"):
                return None, "job is already running"
            item = dict(job)
            item.update({
                "last_run_at": now_ts,
                "last_status": "queued",
                "last_status_detail": "Queued manual run",
                "pending_run_id": uuid.uuid4().hex[:10],
                "pending_started_at": now_ts,
                "last_reminded_at": "",
                "last_trigger": "manual",
                "updated_at": now_ts,
            })
            item = _normalize_job(item)
            jobs[idx] = item
            _save_jobs_unlocked(repo_root, jobs)
            return _job_display(item), ""
    return None, "job not found"


def _read_recent_entries(index_path: Path, limit: int = 256) -> list[dict]:
    if not index_path.is_file():
        return []
    lines = deque(maxlen=max(32, int(limit)))
    try:
        with index_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    lines.append(line)
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return []
    entries = []
    for line in lines:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            entries.append(item)
    return entries


class CronScheduler:
    def __init__(self, *, repo_root: Path | str, hub_runtime, agent_send_path: Path | str):
        self.repo_root = Path(repo_root).resolve()
        self.hub = hub_runtime
        self.agent_send_path = str(agent_send_path)
        self._run_lock = threading.Lock()

    def _find_session_record(self, session_name: str) -> dict | None:
        query = self.hub.active_session_records_query()
        record = query.records.get(session_name)
        if record is not None:
            return record
        archived = self.hub.archived_session_records(query.records.keys())
        return archived.get(session_name)

    def _resolve_index_path(self, job: dict) -> Path | None:
        record = self._find_session_record(job.get("session", ""))
        if not record:
            return None
        index_path = str(record.get("index_path") or "").strip()
        if index_path:
            return Path(index_path)
        paths = self.hub.session_index_paths(
            job.get("session", ""),
            record.get("workspace", ""),
            record.get("log_dir", ""),
        )
        return paths[0] if paths else None

    def _find_reply(self, job: dict) -> dict | None:
        index_path = self._resolve_index_path(job)
        if index_path is None:
            return None
        since = str(job.get("pending_started_at") or "").strip()
        agent = str(job.get("agent") or "").strip().lower()
        for entry in reversed(_read_recent_entries(index_path)):
            if agent_index_entry_omit_for_redacted(str(entry.get("message") or "")):
                continue
            sender = str(entry.get("sender") or "").strip().lower()
            timestamp = str(entry.get("timestamp") or "").strip()
            if sender != agent:
                continue
            if since and timestamp and timestamp < since:
                continue
            return entry
        return None

    def _system_entry_paths(self, job: dict) -> list[Path]:
        index_path = self._resolve_index_path(job)
        if index_path is None:
            return []
        return [index_path]

    def _append_system_entry(self, job: dict, message: str, *, kind: str = "cron", action: str = "") -> None:
        session_name = str(job.get("session") or "").strip()
        if not session_name or not message:
            return
        entry = {
            "timestamp": _now_ts(),
            "session": session_name,
            "sender": "system",
            "targets": [],
            "message": str(message).strip(),
            "msg_id": uuid.uuid4().hex[:12],
            "kind": kind,
            "cron_id": str(job.get("id") or "").strip(),
            "cron_name": str(job.get("name") or "").strip(),
            "cron_agent": str(job.get("agent") or "").strip(),
        }
        if action:
            entry["cron_action"] = action
        for path in self._system_entry_paths(job):
            try:
                append_jsonl_entry(path, entry)
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)

    def _dispatch_system_message(self, job: dict, *, reminder: bool = False) -> str:
        name = str(job.get("name") or "cron").strip()
        agent = str(job.get("agent") or "").strip()
        if reminder:
            return f"Cron Reminder: {name} -> {agent}"
        return f"Cron: {name} -> {agent}"

    def _send_to_agent_pane(self, session_name: str, agent: str, message: str) -> tuple[bool, str]:
        pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
        pane_id = self.hub.tmux_env(session_name, pane_var)
        if not pane_id:
            return False, f"pane not found for {agent}"
        buffer_name = f"cron_{agent}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        payload = str(message or "")
        if not payload:
            return False, "empty prompt"
        try:
            load_res = subprocess.run(
                [*self.hub.tmux_prefix, "load-buffer", "-b", buffer_name, "-"],
                input=payload + "\n",
                text=True,
                capture_output=True,
                timeout=15,
                check=False,
            )
            if load_res.returncode != 0:
                return False, (load_res.stderr or load_res.stdout or "tmux load-buffer failed").strip()
            paste_res = subprocess.run(
                [*self.hub.tmux_prefix, "paste-buffer", "-b", buffer_name, "-d", "-t", pane_id],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if paste_res.returncode != 0:
                return False, (paste_res.stderr or paste_res.stdout or "tmux paste-buffer failed").strip()
            time.sleep(0.3)
            send_res = subprocess.run(
                [*self.hub.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if send_res.returncode != 0:
                return False, (send_res.stderr or send_res.stdout or "tmux send-keys failed").strip()
        except Exception as exc:
            return False, str(exc)
        return True, ""

    def _build_dispatch_message(self, job: dict, *, reminder: bool = False) -> str:
        prompt = str(job.get("prompt") or "").strip()
        if reminder:
            return (
                f"{prompt}\n\n"
                "結果がまだ user に返っていません。了解だけではなく、実際の結果本文をこの session で `agent-send` してください。\n"
                "失敗した場合も、失敗内容と blocker を実際の結果として送ってください。\n"
            )
        return (
            f"{prompt}\n\n"
            "完了したら、この session で user に `agent-send` してください。了解だけは送らないでください。\n"
        )

    def _dispatch_to_agent(self, job: dict, *, reminder: bool = False) -> tuple[bool, str]:
        session_name = str(job.get("session") or "").strip()
        agent = str(job.get("agent") or "").strip()
        if not session_name:
            return False, "session required"
        if not agent:
            return False, "agent required"
        active = self.hub.active_session_records_query().records
        if session_name not in active:
            ok, detail = self.hub.revive_archived_session(session_name)
            if not ok:
                return False, detail or "failed to revive session"
            active = self.hub.active_session_records_query().records
        record = active.get(session_name)
        if record is None:
            return False, "session is not active"
        agents = {str(name).strip() for name in (record.get("agents") or []) if str(name).strip()}
        if agents and agent not in agents:
            return False, f"agent not found in session: {agent}"
        ok, detail = self._send_to_agent_pane(session_name, agent, self._build_dispatch_message(job, reminder=reminder))
        if not ok:
            return False, detail
        self._append_system_entry(
            job,
            self._dispatch_system_message(job, reminder=reminder),
            action="reminder" if reminder else (str(job.get("last_trigger") or "").strip() or "dispatch"),
        )
        return True, ""

    def _set_status(self, job_id: str, **fields):
        _update_job_fields(self.repo_root, job_id, **fields)

    def _dispatch_claimed_job(self, job: dict):
        ok, detail = self._dispatch_to_agent(job, reminder=False)
        if ok:
            self._set_status(
                job.get("id", ""),
                last_status="running",
                last_status_detail="Prompt dispatched",
            )
            return
        self._set_status(
            job.get("id", ""),
            last_status="failed",
            last_status_detail=detail or "failed to dispatch",
            pending_run_id="",
            pending_started_at="",
            last_reminded_at="",
        )

    def run_now(self, job_id: str) -> tuple[bool, str]:
        claimed, detail = claim_manual_job(self.repo_root, job_id)
        if claimed is None:
            return False, detail
        self._dispatch_claimed_job(claimed)
        return True, ""

    def _tick_due_jobs(self):
        for job in claim_due_jobs(self.repo_root):
            self._dispatch_claimed_job(job)

    def _tick_pending_jobs(self):
        now = _now_local()
        for job in load_cron_jobs(self.repo_root):
            pending_id = str(job.get("pending_run_id") or "").strip()
            if not pending_id:
                continue
            reply = self._find_reply(job)
            if reply is not None:
                self._set_status(
                    job.get("id", ""),
                    last_status="ok",
                    last_status_detail="Reply received",
                    last_reply_at=str(reply.get("timestamp") or "").strip(),
                    pending_run_id="",
                    pending_started_at="",
                    last_reminded_at="",
                )
                continue
            started_at_raw = str(job.get("pending_started_at") or "").strip()
            try:
                started_at = datetime.strptime(started_at_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=now.tzinfo)
            except Exception:
                started_at = now
            elapsed = max(0, int((now - started_at).total_seconds()))
            reminded_at = str(job.get("last_reminded_at") or "").strip()
            if not reminded_at and elapsed >= DEFAULT_REPLY_TIMEOUT_SEC:
                ok, detail = self._dispatch_to_agent(job, reminder=True)
                self._set_status(
                    job.get("id", ""),
                    last_status="reminded" if ok else "failed",
                    last_status_detail="Reminder sent" if ok else (detail or "failed to send reminder"),
                    last_reminded_at=_now_ts() if ok else "",
                    pending_run_id=pending_id if ok else "",
                    pending_started_at=started_at_raw if ok else "",
                )
                continue
            if reminded_at and elapsed >= (DEFAULT_REPLY_TIMEOUT_SEC + DEFAULT_REMINDER_GRACE_SEC):
                self._set_status(
                    job.get("id", ""),
                    last_status="timeout",
                    last_status_detail="No reply after reminder",
                    pending_run_id="",
                    pending_started_at="",
                )

    def run_forever(self):
        time.sleep(3)
        while True:
            try:
                with self._run_lock:
                    self._tick_pending_jobs()
                    self._tick_due_jobs()
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
            time.sleep(SCHEDULER_POLL_SEC)
