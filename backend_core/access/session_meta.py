from __future__ import annotations

import json
from pathlib import Path

from backend_core.access.atomic_json import write_json_atomically
from backend_core.access.settings import agent_window_session_root


class SessionMetaError(ValueError):
    pass


def workspace_claim_conflict_message(workspace: str, sessions: list[str]) -> str:
    return f"Multiple sessions claim workspace {workspace}: {', '.join(sessions)}"


class WorkspaceClaimConflict(SessionMetaError):
    def __init__(self, workspace: str, sessions: list[str]):
        self.workspace = workspace
        self.sessions = list(sessions)
        super().__init__(workspace_claim_conflict_message(workspace, self.sessions))


def session_workspace_claims(
    *,
    exclude_session: str = "",
) -> tuple[dict[str, list[tuple[str, str]]], list[tuple[str, str]]]:
    """Group valid workspace claims and report unreadable session metadata."""
    exclude = str(exclude_session or "").strip()
    root = agent_window_session_root()
    claims: dict[str, list[tuple[str, str]]] = {}
    errors: list[tuple[str, str]] = []
    if not root.is_dir():
        return claims, errors
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name == exclude:
            continue
        try:
            workspace = session_workspace(entry.name)
        except SessionMetaError as exc:
            errors.append((entry.name, str(exc)))
            continue
        if not workspace:
            continue
        normalized = str(Path(workspace).expanduser().resolve())
        claims.setdefault(normalized, []).append((entry.name, workspace))
    return claims, errors


def find_session_for_workspace(workspace: Path | str, *, exclude_session: str = "") -> str | None:
    """Return the name of an existing session (active or archived) whose
    recorded workspace matches. A session's .meta file persists after the
    tmux session itself is gone, so this covers archived sessions too.
    """
    target = str(Path(workspace).expanduser().resolve())
    claims, errors = session_workspace_claims(exclude_session=exclude_session)
    if errors:
        raise SessionMetaError("; ".join(detail for _name, detail in errors))
    matches = claims.get(target, [])
    if not matches:
        return None
    names = [name for name, _raw_workspace in matches]
    if len(names) > 1:
        raise WorkspaceClaimConflict(target, names)
    return names[0]


def _parse_tmux_environment_output(output: str) -> dict[str, str]:
    env_map: dict[str, str] = {}
    for raw in (output or "").splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_map[key] = value
    return env_map


def _parse_agents_csv(agents_csv: str) -> list[str]:
    return [
        item.strip()
        for item in (agents_csv or "").split(",")
        if item.strip() and item.strip() != "-"
    ]


def _reconcile_agent_names(
    meta: dict[str, object],
    current_agents: list[str],
) -> None:
    raw_names = meta.get("agent_names")
    if raw_names is None:
        return
    if not isinstance(raw_names, dict):
        raise ValueError("agent_names must be an object")
    current = {str(agent or "").strip().lower() for agent in current_agents if str(agent or "").strip()}
    reconciled = {
        str(canonical or "").strip().lower(): str(display or "").strip()
        for canonical, display in raw_names.items()
        if str(canonical or "").strip() and str(display or "").strip()
        and str(canonical or "").strip().lower() in current
    }
    if reconciled:
        meta["agent_names"] = reconciled
    else:
        meta.pop("agent_names", None)


def session_workspace(session_name: str) -> str | None:
    """Return the workspace path recorded in a session's own .meta file.

    Used to resolve which live tmux session (if any) is currently backing
    an AW session: tmux only ever knows its own workspace, never an AW
    session's name, so the .meta-recorded workspace is the bridge between
    the two.
    """
    meta_path = agent_window_session_root() / str(session_name or "").strip() / ".meta"
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionMetaError(f"invalid session meta: {meta_path}") from exc
    if not isinstance(meta, dict):
        raise SessionMetaError(f"invalid session meta: {meta_path}")
    return str(meta.get("workspace") or "").strip() or None


def write_session_meta_file(
    session_name: str,
    agents_csv: str,
    tmux_env_output: str,
) -> None:
    env_map = _parse_tmux_environment_output(tmux_env_output)
    workspace = str(env_map.get("AGENT_WINDOW_WORKSPACE") or "").strip()
    if not workspace:
        raise ValueError("AGENT_WINDOW_WORKSPACE is required to write session meta")

    meta_path = agent_window_session_root() / str(session_name or "").strip() / ".meta"
    meta: dict[str, object] = {}
    if meta_path.is_file():
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"invalid session meta: {meta_path}")
        meta = raw

    parsed_agents = _parse_agents_csv(agents_csv)
    _reconcile_agent_names(meta, parsed_agents)
    # Timestamps lived here once; .log.jsonl is the real record of when a
    # session started and last moved, so a copy in .meta only went stale.
    meta.pop("session", None)
    meta.pop("created_at", None)
    meta.pop("updated_at", None)
    meta["workspace"] = workspace
    meta["agents"] = parsed_agents
    write_json_atomically(meta_path, meta, indent=2)
