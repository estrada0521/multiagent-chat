from __future__ import annotations

import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ..state_core import local_state_dir
from ..state_core import local_workspace_log_dir


_PREVIEW_TAIL_BYTES = 2 * 1024 * 1024
_PREVIEW_TAIL_CHUNK_BYTES = 64 * 1024


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


def _compact_message_preview(entry: dict[str, Any]) -> dict[str, str]:
    sender = (entry.get("sender") or "").strip()
    if sender == "system":
        return {"sender": "", "text": ""}
    message = str(entry.get("message") or "").strip()
    if not message:
        return {"sender": "", "text": ""}
    compact = re.sub(r"^\[From:\s*[^\]]+\]\s*", "", message, flags=re.IGNORECASE)
    compact = re.sub(r"^\[[^\]]*msg-id:[^\]]+\]\s*", "", compact, flags=re.IGNORECASE)
    compact = re.sub(r"\s+", " ", compact)
    compact = re.sub(r"\[Attached:\s*[^\]]+\]", "", compact).strip()
    compact = compact[:140].rstrip()
    if not compact:
        return {"sender": "", "text": ""}
    return {"sender": sender, "text": compact}


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


def _latest_message_preview_from_full_scan(index_path: Path) -> dict[str, str]:
    last_preview = {"sender": "", "text": ""}
    with index_path.open("r", encoding="utf-8") as handle:
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


def latest_message_preview(index_path: Path | None) -> dict[str, str]:
    if not index_path or not index_path.is_file():
        return {"sender": "", "text": ""}
    try:
        size = index_path.stat().st_size
        for line in _iter_tail_lines(index_path):
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
            return _latest_message_preview_from_full_scan(index_path)
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return {"sender": "", "text": ""}
    return {"sender": "", "text": ""}


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


def session_index_paths(
    runtime: Any,
    session_name: str,
    workspace: str = "",
    explicit_log_dir: str = "",
) -> list[Path]:
    roots: list[Path] = []
    workspace = (workspace or "").strip()
    workspace_candidates: list[str] = []
    if workspace:
        workspace_path = Path(workspace)
        workspace_candidates.extend(
            [
                str(local_workspace_log_dir(runtime.repo_root, workspace_path)),
                str(workspace_path / "logs"),
            ]
        )
    root_candidates = [
        explicit_log_dir,
        *workspace_candidates,
        str(runtime.central_log_dir),
    ]
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
    found: list[Path] = []
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
    runtime: Any,
    session_name: str,
    workspace: str = "",
    explicit_log_dir: str = "",
) -> Path | None:
    paths = session_index_paths(runtime, session_name, workspace, explicit_log_dir)
    return paths[0] if paths else None


def host_without_port(host_header: str) -> str:
    host = (host_header or "").strip() or "127.0.0.1"
    if host.startswith("["):
        end = host.find("]")
        return host[: end + 1] if end != -1 else host
    return host.split(":", 1)[0]


def build_session_record(
    runtime: Any,
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
    preferred_index_path: Path | None = None,
) -> dict:
    resolved_paths = list(index_paths or session_index_paths(runtime, name, workspace, explicit_log_dir))
    primary_index = None
    if preferred_index_path is not None:
        preferred_index = Path(preferred_index_path)
        if preferred_index.is_file():
            primary_index = preferred_index
            try:
                preferred_key = str(preferred_index.resolve())
            except Exception:
                preferred_key = str(preferred_index)
            has_preferred = False
            for candidate in resolved_paths:
                try:
                    candidate_key = str(candidate.resolve())
                except Exception:
                    candidate_key = str(candidate)
                if candidate_key == preferred_key:
                    has_preferred = True
                    break
            if not has_preferred:
                resolved_paths.insert(0, preferred_index)
    if primary_index is None:
        primary_index = resolved_paths[0] if resolved_paths else None

    if primary_index is not None:
        preview = latest_message_preview(primary_index)
        if not preview["text"]:
            preview = latest_message_preview_from_paths(resolved_paths)
    else:
        preview = {"sender": "", "text": ""}
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
        "chat_port": runtime.chat_port_for_session(name),
        "session_path": f"/session/{session_slug}/",
        "follow_path": f"/session/{session_slug}/?follow=1",
        "log_dir": explicit_log_dir or str(primary_index.parent if primary_index else ""),
        "index_path": str(primary_index) if primary_index else "",
        "chat_count": sum(count_nonempty_lines(path) for path in resolved_paths),
        "latest_message_sender": preview["sender"],
        "latest_message_preview": preview["text"],
    }


def collect_repo_sessions(runtime: Any) -> tuple[list[dict], str, str]:
    result = runtime.tmux_run(["list-sessions", "-F", "#{session_name}"])
    if result.timed_out:
        return [], "unhealthy", "tmux list-sessions timed out"
    if result.returncode != 0:
        return [], "ok", ""

    sessions: list[dict] = []
    any_timeout = False
    timeout_detail = ""

    for name in result.stdout.splitlines():
        if not name or any_timeout:
            continue

        bin_dir, t1 = runtime.tmux_env_query(name, "MULTIAGENT_BIN_DIR")
        if t1:
            any_timeout, timeout_detail = True, f"tmux show-environment (BIN_DIR) timed out for {name}"
            break
        if not bin_dir:
            continue

        try:
            if Path(bin_dir).resolve() != runtime.script_dir:
                continue
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            continue

        workspace, t2 = runtime.tmux_env_query(name, "MULTIAGENT_WORKSPACE")
        explicit_log_dir, t3 = runtime.tmux_env_query(name, "MULTIAGENT_LOG_DIR")
        index_path_env, t4 = runtime.tmux_env_query(name, "MULTIAGENT_INDEX_PATH")
        r_attached = runtime.tmux_run(["display-message", "-p", "-t", name, "#{session_attached}"])
        r_created = runtime.tmux_run(["display-message", "-p", "-t", name, "#{session_created}"])
        r_dead = runtime.tmux_run(["list-panes", "-t", name, "-F", "#{pane_dead}"])
        agents, t5 = runtime.session_agents_query(name)

        if t2 or t3 or t4 or r_attached.timed_out or r_created.timed_out or r_dead.timed_out or t5:
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

        preferred_index_path = None
        if index_path_env:
            try:
                preferred_index_path = Path(index_path_env).resolve()
            except Exception:
                preferred_index_path = Path(index_path_env)
        if preferred_index_path is None:
            preferred_index_path = runtime._chat_launch_session_dir(name, workspace, explicit_log_dir) / ".agent-index.jsonl"
        index_paths = session_index_paths(runtime, name, workspace, explicit_log_dir)
        sessions.append(
            build_session_record(
                runtime,
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
                preferred_index_path=preferred_index_path,
            )
        )

    if any_timeout:
        return sessions, "unhealthy", timeout_detail

    sessions.sort(key=lambda item: item["created_epoch"], reverse=True)
    return sessions, "ok", ""


def archived_sessions(runtime: Any, active_names: set[str] | list[str] | None = None) -> list[dict]:
    active_names_set = set(active_names or [])
    records: dict[str, dict] = {}
    log_roots: list[Path] = []
    for candidate in (
        runtime.central_log_dir,
        local_state_dir(runtime.repo_root) / "workspaces",
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
            entries: list[Path] = []
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
            meta: dict[str, Any] = {}
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
            if not session_name or session_name in active_names_set:
                continue
            workspace = (meta.get("workspace") or "").strip() or str(runtime.repo_root)
            created_epoch = parse_saved_time(str(meta.get("created_at", "")))
            updated_epoch = parse_saved_time(str(meta.get("updated_at", "")))
            updated_epoch = max(updated_epoch, safe_mtime(meta_path), safe_mtime(index_path))
            if not created_epoch:
                created_epoch = updated_epoch
            agents: list[str] = []
            seen_agents: set[str] = set()
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
                _candidates: list[tuple[str, float]] = []
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
                inferred: set[str] = set()
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
            record = build_session_record(
                runtime,
                name=session_name,
                workspace=workspace,
                agents=agents,
                status="archived",
                attached=0,
                dead_panes=0,
                created_epoch=int(created_epoch or 0),
                created_at=str(meta.get("created_at") or format_epoch(created_epoch)),
                updated_epoch=int(updated_epoch or 0),
                updated_at=str(meta.get("updated_at") or format_epoch(updated_epoch)),
                explicit_log_dir=str(entry),
                index_paths=[index_path] if index_path.exists() else [],
            )
            existing = records.get(session_name)
            if existing is None or record["updated_epoch"] > existing["updated_epoch"]:
                records[session_name] = record
    sessions = list(records.values())
    sessions.sort(key=lambda item: item["updated_epoch"], reverse=True)
    return sessions
