from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend_core.access.session_meta import session_workspace_claims, workspace_claim_conflict_message
from backend_core.access.settings import agent_window_session_root, session_log_path
from backend_core.tmux.resolve import normalize_workspace


_PREVIEW_TAIL_BYTES = 2 * 1024 * 1024
_PREVIEW_TAIL_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class SessionQueryResult:
    records: dict[str, dict]
    warnings: dict[str, dict]
    state: str
    detail: str = ""

    @property
    def non_archived_names(self) -> set[str]:
        return set(self.records) | set(self.warnings)


def parse_saved_time(value: str) -> float:
    if not value:
        return 0
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(value, fmt).timestamp()
        except ValueError:
            pass
    return 0


def _compact_message_preview(entry: dict[str, Any]) -> dict[str, str]:
    sender = (entry.get("sender") or "").strip()
    if sender == "system":
        return {"sender": "", "text": "", "revision": ""}
    message = str(entry.get("message") or "").strip()
    if not message:
        return {"sender": "", "text": "", "revision": ""}
    compact = re.sub(r"^\[From:\s*[^\]]+\]\s*", "", message, flags=re.IGNORECASE)
    compact = re.sub(r"^\[[^\]]*msg-id:[^\]]+\]\s*", "", compact, flags=re.IGNORECASE)
    compact = re.sub(r"\s+", " ", compact)
    compact = re.sub(r"\[Attached:\s*[^\]]+\]", "", compact).strip()
    compact = compact[:140].rstrip()
    if not compact:
        return {"sender": "", "text": "", "revision": ""}
    context_hash = str(entry.get("context_hash") or "").strip()
    native_log_offset = str(entry.get("native_log_offset") or "").strip()
    revision = f"{context_hash}:{native_log_offset}" if native_log_offset else context_hash
    return {"sender": sender, "text": compact, "revision": revision}


def _iter_tail_lines(path: Path, *, max_bytes: int = _PREVIEW_TAIL_BYTES):
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            pos = handle.tell()
            remaining = min(max_bytes, pos)
            buffer = b""
            while pos > 0 and remaining > 0:
                read_size = min(_PREVIEW_TAIL_CHUNK_BYTES, pos, remaining)
                pos -= read_size
                remaining -= read_size
                handle.seek(pos)
                buffer = handle.read(read_size) + buffer
                parts = buffer.split(b"\n")
                if pos > 0 and remaining > 0:
                    buffer = parts[0]
                    parts = parts[1:]
                else:
                    buffer = b""
                for raw in reversed(parts):
                    if raw.strip():
                        yield raw.decode("utf-8", errors="replace")
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)


def _latest_message_preview_from_full_scan(log_path: Path) -> dict[str, str]:
    last_preview = {"sender": "", "text": "", "revision": ""}
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                continue
            preview = _compact_message_preview(entry)
            if preview["text"]:
                last_preview = preview
    return last_preview


def latest_message_preview(log_path: Path | None) -> dict[str, str]:
    if not log_path or not log_path.is_file():
        return {"sender": "", "text": "", "revision": ""}
    try:
        size = log_path.stat().st_size
        for line in _iter_tail_lines(log_path):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                continue
            preview = _compact_message_preview(entry)
            if preview["text"]:
                return preview
        if size > _PREVIEW_TAIL_BYTES:
            return _latest_message_preview_from_full_scan(log_path)
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return {"sender": "", "text": "", "revision": ""}
    return {"sender": "", "text": "", "revision": ""}


def host_without_port(host_header: str) -> str:
    host = (host_header or "").strip() or "127.0.0.1"
    if host.startswith("["):
        end = host.find("]")
        return host[: end + 1] if end != -1 else host
    return host.split(":", 1)[0]


def build_session_record(
    *,
    name: str,
    workspace: str,
    log_path: Path | None = None,
) -> dict:
    path = Path(log_path) if log_path is not None else session_log_path(name)
    primary = path if path.is_file() else None
    preview = latest_message_preview(primary)
    return {
        "name": name,
        "workspace": workspace,
        "latest_message_sender": preview["sender"],
        "latest_message_preview": preview["text"],
        "latest_message_revision": preview["revision"],
    }


def build_warning_session_record(*, name: str, warning: str) -> dict:
    return {
        "name": name,
        "warning": warning,
    }


class _TmuxQueryTimeout(RuntimeError):
    pass


def live_tmux_sessions_query(runtime: Any) -> tuple[dict[str, tuple[str, int]], str, str]:
    """Map each live workspace to its tmux name and creation time."""
    result = runtime.tmux_run(["list-sessions", "-F", "#{session_name}\t#{session_created}"])
    if result.timed_out:
        return {}, "unhealthy", "tmux list-sessions timed out"
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "no server running" in stderr or "No such file or directory" in stderr:
            return {}, "ok", ""
        return {}, "unhealthy", stderr or f"tmux list-sessions failed (exit {result.returncode})"

    sessions: list[tuple[str, int]] = []
    for raw_line in result.stdout.splitlines():
        tmux_name, separator, created_raw = raw_line.partition("\t")
        tmux_name = tmux_name.strip()
        if not tmux_name:
            continue
        created_epoch = int(created_raw) if separator and created_raw.isdigit() else 0
        sessions.append((tmux_name, created_epoch))

    def workspace_of(tmux_name: str) -> str | None:
        workspace, timed_out = runtime.tmux_env_query(tmux_name, "AGENT_WINDOW_WORKSPACE")
        if timed_out:
            raise _TmuxQueryTimeout(tmux_name)
        return workspace or None

    try:
        workspace_to_tmux: dict[str, tuple[str, int]] = {}
        for tmux_name, created_epoch in sessions:
            workspace = workspace_of(tmux_name)
            if not workspace:
                continue
            workspace_to_tmux.setdefault(normalize_workspace(workspace), (tmux_name, created_epoch))
    except _TmuxQueryTimeout as exc:
        return {}, "unhealthy", f"tmux show-environment (WORKSPACE) timed out for {exc}"
    return workspace_to_tmux, "ok", ""


def collect_repo_sessions(runtime: Any) -> tuple[list[dict], list[dict], str, str]:
    claims, claim_errors = session_workspace_claims()
    unique_claims: list[tuple[str, str, str]] = []
    warnings: list[dict] = [
        build_warning_session_record(name=name, warning=detail)
        for name, detail in claim_errors
    ]
    for normalized_workspace, claimants in claims.items():
        claimant_names = [name for name, _workspace in claimants]
        if len(claimants) > 1:
            warning = workspace_claim_conflict_message(normalized_workspace, claimant_names)
            for name, _workspace in claimants:
                warnings.append(build_warning_session_record(name=name, warning=warning))
            continue
        name, workspace = claimants[0]
        unique_claims.append((normalized_workspace, name, workspace))
    warnings.sort(key=lambda item: item["name"])

    workspace_to_tmux, state, detail = live_tmux_sessions_query(runtime)
    if state != "ok":
        return [], warnings, state, detail

    sessions: list[tuple[int, dict]] = []

    for normalized_workspace, name, workspace in unique_claims:
        tmux_session = workspace_to_tmux.get(normalized_workspace)
        if not tmux_session:
            continue
        _tmux_name, created_epoch = tmux_session
        sessions.append(
            (
                created_epoch,
                build_session_record(name=name, workspace=workspace),
            )
        )

    sessions.sort(key=lambda item: item[0], reverse=True)
    return [record for _created_epoch, record in sessions], warnings, "ok", ""


def active_session_records_query(runtime: Any) -> SessionQueryResult:
    sessions, warnings, state, detail = collect_repo_sessions(runtime)
    return SessionQueryResult(
        records={item["name"]: item for item in sessions},
        warnings={item["name"]: item for item in warnings},
        state=state,
        detail=detail,
    )


def archived_sessions(excluded_names: set[str] | list[str] | None = None) -> list[dict]:
    excluded_names_set = set(excluded_names or [])
    records: dict[str, tuple[float, dict]] = {}
    log_roots: list[Path] = []
    for candidate in (agent_window_session_root(),):
        if not candidate or not Path(candidate).is_dir():
            continue
        root = Path(candidate)
        if root not in log_roots:
            log_roots.append(root)
    if not log_roots:
        return []
    for log_root in log_roots:
        entries = [entry for entry in log_root.iterdir() if entry.is_dir()]
        for entry in entries:
            session_name = entry.name.strip()
            if not session_name or session_name in excluded_names_set:
                continue
            meta_path = entry / ".meta"
            log_path = entry / ".log.jsonl"
            if not meta_path.exists() and not log_path.exists():
                continue
            meta: dict[str, Any] = {}
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if not isinstance(meta, dict):
                    raise ValueError(f"invalid session meta: {meta_path}")
            workspace = str(meta.get("workspace") or "").strip()
            created_epoch = parse_saved_time(str(meta.get("created_at", "")))
            agents: list[str] = []
            seen_agents: set[str] = set()
            meta_agents = meta.get("agents")
            if isinstance(meta_agents, list) and meta_agents:
                for a in meta_agents:
                    name = str(a).strip()
                    if name and name not in seen_agents:
                        seen_agents.add(name)
                        agents.append(name)
            record = build_session_record(
                name=session_name,
                workspace=workspace,
                log_path=log_path,
            )
            record["agents"] = agents
            record["log_dir"] = str(log_path.parent)
            existing = records.get(session_name)
            if existing is None or created_epoch > existing[0]:
                records[session_name] = (created_epoch, record)
    sessions = sorted(records.values(), key=lambda item: item[0], reverse=True)
    return [record for _created_epoch, record in sessions]


def archived_session_records(
    excluded_names: set[str] | list[str] | None = None,
) -> dict[str, dict]:
    return {item["name"]: item for item in archived_sessions(excluded_names)}
