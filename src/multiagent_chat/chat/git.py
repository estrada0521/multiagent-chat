"""Git helpers for chat_server (branch overview, commits, restore, agent attribution).

These were extracted from chat_server.py to reduce that module's size. State is
injected via :func:`configure` once at startup, mirroring the existing module-global
pattern used in chat_server.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from multiagent_chat.agents.registry import AGENTS, ALL_AGENT_NAMES

_MULTIAGENT_AGENT_EMAIL_DOMAIN = "agents.multiagent.local"
_AGENT_NAME_SET = frozenset(ALL_AGENT_NAMES)

_workspace: str = ""
_repo_root: Path = Path()
_index_path: Path = Path()
_runtime = None
_BRANCH_OVERVIEW_CACHE_TTL_SECONDS = 5.0
_branch_overview_cache_lock = threading.Lock()
_branch_overview_cache: dict[tuple[str, int, int], tuple[float, dict]] = {}


def configure(*, workspace: str, repo_root: Path, index_path: Path, runtime) -> None:
    global _workspace, _repo_root, _index_path, _runtime
    _workspace = workspace or ""
    _repo_root = repo_root
    _index_path = index_path
    _runtime = runtime
    _clear_branch_overview_cache()


def _clear_branch_overview_cache() -> None:
    with _branch_overview_cache_lock:
        _branch_overview_cache.clear()


def _agent_from_text_multiagent_email(text: str) -> str:
    """If text contains local@agents.multiagent.local, return registered agent base name."""
    low = (text or "").lower()
    if _MULTIAGENT_AGENT_EMAIL_DOMAIN not in low:
        return ""
    dom = re.escape(_MULTIAGENT_AGENT_EMAIL_DOMAIN)
    for m in re.finditer(rf"([a-z0-9][a-z0-9._+-]*)@{dom}\b", low):
        base = m.group(1).split("+", 1)[0].strip()
        if base in _AGENT_NAME_SET:
            return base
    return ""


def _detect_agent_from_commit_fields(*fields: str) -> str:
    """Detect agent from commit metadata without naive substring matches (avoids false positives)."""
    for raw in fields:
        hit = _agent_from_text_multiagent_email(raw)
        if hit:
            return hit
    names = sorted(ALL_AGENT_NAMES, key=len, reverse=True)
    for raw in fields:
        if not raw:
            continue
        low = raw.strip().lower()
        if not low:
            continue
        for name in names:
            pat = r"(?<![a-z0-9])" + re.escape(name) + r"(?:-\d+)?(?![a-z0-9])"
            if re.search(pat, low):
                return name
    return ""


def _git_author_env_for_agent(agent: str) -> dict[str, str] | None:
    """Author/committer env vars for git so branch menu can attribute commits to agents."""
    a = (agent or "").strip().lower()
    if not a or a == "user":
        return None
    if a not in _AGENT_NAME_SET:
        return None
    info = AGENTS.get(a)
    display = info.display_name if info else a
    email = f"{a}@{_MULTIAGENT_AGENT_EMAIL_DOMAIN}"
    name = f"{display} ({a})"
    return {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
    }


def _git_commit_env(agent: str = "") -> dict[str, str]:
    """Start from the current env but clear inherited git identity unless explicitly set for an agent."""
    git_env = os.environ.copy()
    git_env.pop("MULTIAGENT_AGENT_NAME", None)
    for key in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
    ):
        git_env.pop(key, None)
    _ident = _git_author_env_for_agent(agent)
    if _ident:
        git_env.update(_ident)
    return git_env


def _recent_logged_commit_agents(max_lines: int = 4000) -> dict[str, str]:
    """Prefer explicit session log attribution over git author metadata for branch-menu icons."""
    try:
        lines = []
        with _index_path.open("r", encoding="utf-8") as f:
            for line in f:
                lines.append(line)
                if len(lines) > max_lines:
                    del lines[: len(lines) - max_lines]
    except Exception:
        return {}
    agents_by_hash: dict[str, str] = {}
    for raw in reversed(lines):
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        if entry.get("kind") != "git-commit":
            continue
        commit_hash = (entry.get("commit_hash") or "").strip()
        agent = (entry.get("agent") or "").strip().lower()
        if not commit_hash or not agent or commit_hash in agents_by_hash:
            continue
        agents_by_hash[commit_hash] = agent
    return agents_by_hash


def git_branch_overview(*, offset=0, limit=50, force_refresh: bool = False):
    root = Path(_workspace or _repo_root)
    try:
        offset = max(0, int(offset))
    except Exception:
        offset = 0
    try:
        limit = max(1, min(int(limit), 200))
    except Exception:
        limit = 50
    cache_key = (str(root.resolve()), offset, limit)
    now = time.monotonic()
    if not force_refresh:
        with _branch_overview_cache_lock:
            cached = _branch_overview_cache.get(cache_key)
            if cached and now - cached[0] < _BRANCH_OVERVIEW_CACHE_TTL_SECONDS:
                return cached[1]

    def _run(*args):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    def _parse_numstat(res):
        added = 0
        deleted = 0
        if res.returncode != 0:
            return added, deleted
        for line in (res.stdout or "").splitlines():
            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue
            ins, dels = parts[0], parts[1]
            if ins.isdigit():
                added += int(ins)
            if dels.isdigit():
                deleted += int(dels)
        return added, deleted
    branch_res = _run("rev-parse", "--abbrev-ref", "HEAD")
    branch = (branch_res.stdout or "").strip() if branch_res.returncode == 0 else "unknown"
    total_commits = 0
    total_res = _run("rev-list", "--count", "HEAD")
    if total_res.returncode == 0:
        try:
            total_commits = max(0, int((total_res.stdout or "").strip() or "0"))
        except Exception:
            total_commits = 0
    upstream_res = _run("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    upstream = (upstream_res.stdout or "").strip() if upstream_res.returncode == 0 else ""
    ahead_behind = ""
    if upstream:
        count_res = _run("rev-list", "--left-right", "--count", f"{branch}...{upstream}")
        if count_res.returncode == 0:
            parts = (count_res.stdout or "").strip().split()
            if len(parts) == 2:
                ahead_behind = f"ahead {parts[0]} / behind {parts[1]}"
    status_res = _run("status", "--short", "--branch", "--untracked-files=all")
    status_lines = []
    if status_res.returncode == 0:
        for line in (status_res.stdout or "").splitlines():
            line = line.rstrip()
            if not line or line.startswith("## "):
                continue
            status_lines.append(line)
    def _status_path_for_fingerprint(line: str) -> str:
        raw = str(line or "")
        path = raw[3:] if len(raw) > 3 else raw
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[-1]
        return path.strip().strip('"')
    def _worktree_fingerprint() -> str:
        digest = hashlib.sha1()
        for line in sorted(status_lines):
            digest.update(line.encode("utf-8", "surrogateescape"))
            digest.update(b"\0")
            rel = _status_path_for_fingerprint(line)
            if not rel:
                continue
            try:
                st = (root / rel).stat()
            except OSError:
                digest.update(b"missing\0")
                continue
            digest.update(str(st.st_size).encode("ascii", "ignore"))
            digest.update(b":")
            digest.update(str(st.st_mtime_ns).encode("ascii", "ignore"))
            digest.update(b"\0")
        return digest.hexdigest()
    worktree_added = 0
    worktree_deleted = 0
    diff_head_res = _run("diff", "--numstat", "HEAD", "--")
    worktree_has_diff = False
    if diff_head_res.returncode == 0:
        worktree_added, worktree_deleted = _parse_numstat(diff_head_res)
        worktree_has_diff = bool((diff_head_res.stdout or "").strip())
    else:
        unstaged_add, unstaged_del = _parse_numstat(_run("diff", "--numstat", "--"))
        staged_add, staged_del = _parse_numstat(_run("diff", "--numstat", "--cached", "--"))
        worktree_added = unstaged_add + staged_add
        worktree_deleted = unstaged_del + staged_del
    logged_commit_agents = _recent_logged_commit_agents()
    log_res = _run(
        "log",
        f"--skip={offset}",
        f"--max-count={limit}",
        "--format=%h\x1f%aI\x1f%s\x1f%an\x1f%cn\x1f%ae\x1f%ce\x1f%(trailers:key=Co-Authored-By,valueonly,separator=;)",
    )
    recent_commits = []
    if log_res.returncode == 0:
        for line in (log_res.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\x1f")
            if len(parts) < 3:
                continue
            h, ts, subj = parts[0], parts[1], parts[2]
            author_name = parts[3].strip() if len(parts) > 3 else ""
            committer_name = parts[4].strip() if len(parts) > 4 else ""
            author_email = parts[5].strip() if len(parts) > 5 else ""
            committer_email = parts[6].strip() if len(parts) > 6 else ""
            co_author = parts[7].strip() if len(parts) > 7 else ""
            agent = logged_commit_agents.get(h) or _detect_agent_from_commit_fields(
                author_email,
                committer_email,
                co_author,
                author_name,
                committer_name,
            )
            hhmm = ""
            try:
                t_part = ts.split("T")[1] if "T" in ts else ""
                if t_part:
                    hhmm = t_part[:5]
            except Exception:
                pass
            recent_commits.append({
                "hash": h,
                "time": hhmm,
                "subject": subj,
                "agent": agent,
            })
    stat_res = _run("log", f"--skip={offset}", f"--max-count={limit}", "--format=%h", "--shortstat")
    commit_stats = {}
    if stat_res.returncode == 0:
        current_hash = None
        for line in (stat_res.stdout or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if len(stripped) <= 12 and all(c in "0123456789abcdef" for c in stripped):
                current_hash = stripped
            elif current_hash and "changed" in stripped:
                ins = dels = changed_paths = 0
                for part in stripped.split(","):
                    part = part.strip()
                    files_match = re.search(r"(\d+)\s+files?\s+changed", part)
                    if files_match:
                        changed_paths = int(files_match.group(1))
                        continue
                    if "insertion" in part:
                        ins = int(part.split()[0])
                    elif "deletion" in part:
                        dels = int(part.split()[0])
                commit_stats[current_hash] = {"ins": ins, "dels": dels, "changed_paths": changed_paths}
                current_hash = None
    for c in recent_commits:
        s = commit_stats.get(c["hash"]) or {}
        c["ins"] = int(s.get("ins", 0) or 0)
        c["dels"] = int(s.get("dels", 0) or 0)
        c["changed_paths"] = int(s.get("changed_paths", 0) or 0)
    next_offset = offset + len(recent_commits)
    has_more = next_offset < total_commits if total_commits else len(recent_commits) >= limit
    result = {
        "branch": branch,
        "upstream": upstream,
        "ahead_behind": ahead_behind,
        "offset": offset,
        "limit": limit,
        "next_offset": next_offset,
        "total_commits": total_commits,
        "has_more": has_more,
        "worktree_added": worktree_added,
        "worktree_deleted": worktree_deleted,
        "worktree_has_diff": worktree_has_diff,
        "worktree_changed_paths": len(status_lines),
        "worktree_fingerprint": _worktree_fingerprint(),
        "status_lines": status_lines[:8],
        "recent_commits": recent_commits,
    }
    with _branch_overview_cache_lock:
        _branch_overview_cache[cache_key] = (time.monotonic(), result)
    return result


def git_diff_files(*, commit_hash: str = ""):
    root = Path(_workspace or _repo_root)
    commit_hash = str(commit_hash or "").strip()

    def _run(*args):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def _parse_numstat_lines(lines: list[str]) -> tuple[list[dict], int, int]:
        by_path: dict[str, dict] = {}
        order: list[str] = []
        for raw in lines:
            line = str(raw or "").rstrip()
            if not line:
                continue
            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue
            ins_raw, dels_raw, path_raw = parts[0], parts[1], parts[2]
            path = path_raw.strip()
            if not path:
                continue
            ins = int(ins_raw) if ins_raw.isdigit() else 0
            dels = int(dels_raw) if dels_raw.isdigit() else 0
            binary = not (ins_raw.isdigit() and dels_raw.isdigit())
            if path not in by_path:
                by_path[path] = {
                    "path": path,
                    "ins": 0,
                    "dels": 0,
                    "changed": 0,
                    "binary": False,
                }
                order.append(path)
            entry = by_path[path]
            entry["ins"] += ins
            entry["dels"] += dels
            entry["changed"] = entry["ins"] + entry["dels"]
            entry["binary"] = bool(entry.get("binary")) or binary
        files = [by_path[path] for path in order]
        total_ins = sum(int(item.get("ins") or 0) for item in files)
        total_dels = sum(int(item.get("dels") or 0) for item in files)
        return files, total_ins, total_dels

    lines: list[str] = []
    if commit_hash:
        diff_res = _run(
            "show",
            "--numstat",
            "--format=",
            "--find-renames",
            "--find-copies",
            commit_hash,
            "--",
        )
        if diff_res.returncode != 0:
            raise RuntimeError((diff_res.stderr or diff_res.stdout or "git diff failed").strip())
        lines = (diff_res.stdout or "").splitlines()
    else:
        diff_res = _run("diff", "--numstat", "HEAD", "--")
        if diff_res.returncode == 0:
            lines = (diff_res.stdout or "").splitlines()
        else:
            staged = _run("diff", "--numstat", "--cached", "--")
            unstaged = _run("diff", "--numstat", "--")
            if staged.returncode != 0 and unstaged.returncode != 0:
                raise RuntimeError(
                    (
                        diff_res.stderr
                        or diff_res.stdout
                        or staged.stderr
                        or staged.stdout
                        or unstaged.stderr
                        or unstaged.stdout
                        or "git diff failed"
                    ).strip()
                )
            lines = (staged.stdout or "").splitlines() + (unstaged.stdout or "").splitlines()

    files, total_ins, total_dels = _parse_numstat_lines(lines)
    return {
        "hash": commit_hash,
        "changed_paths": len(files),
        "total_ins": total_ins,
        "total_dels": total_dels,
        "files": files,
    }

def git_commit_file(*, rel_path: str, message: str, agent: str = ""):
    root = Path(_workspace or _repo_root).resolve()
    rel_path = str(rel_path or "").strip().lstrip("/")
    message = str(message or "").strip()
    if not rel_path:
        raise ValueError("path required")
    if not message:
        raise ValueError("message required")
    candidate = (root / rel_path).resolve()
    try:
        normalized = candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise PermissionError("outside workspace") from exc

    git_env = _git_commit_env(agent)

    def _run(*args, timeout=20):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=git_env,
        )

    add_res = _run("add", "-A", "--", normalized)
    if add_res.returncode != 0:
        raise RuntimeError((add_res.stderr or add_res.stdout or "git add failed").strip())

    staged_res = _run("diff", "--cached", "--name-only", "--", normalized)
    if staged_res.returncode != 0:
        raise RuntimeError((staged_res.stderr or staged_res.stdout or "git diff failed").strip())
    if not (staged_res.stdout or "").strip():
        raise ValueError("no staged changes for path")

    commit_res = _run("commit", "-m", message, "--only", "--", normalized, timeout=30)
    stdout = (commit_res.stdout or "").strip()
    stderr = (commit_res.stderr or "").strip()
    if commit_res.returncode != 0:
        raise RuntimeError(stderr or stdout or f"git commit failed ({commit_res.returncode})")

    head_res = _run("rev-parse", "--short", "HEAD")
    commit_short = (head_res.stdout or "").strip() if head_res.returncode == 0 else ""
    commit_hash = (_run("rev-parse", "HEAD").stdout or "").strip()

    _runtime.record_git_commit(commit_hash=commit_hash, commit_short=commit_short, subject=message, agent=agent)
    _clear_branch_overview_cache()

    return {
        "ok": True,
        "path": normalized,
        "message": message,
        "commit_short": commit_short,
        "stdout": stdout,
    }

def git_commit_all(*, message: str, agent: str = ""):
    root = Path(_workspace or _repo_root).resolve()
    message = str(message or "").strip()
    if not message:
        raise ValueError("message required")

    git_env = _git_commit_env(agent)

    def _run(*args, timeout=20):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=git_env,
        )

    add_res = _run("add", "-A", "--", ".")
    if add_res.returncode != 0:
        raise RuntimeError((add_res.stderr or add_res.stdout or "git add failed").strip())

    staged_res = _run("diff", "--cached", "--name-only")
    if staged_res.returncode != 0:
        raise RuntimeError((staged_res.stderr or staged_res.stdout or "git diff failed").strip())
    staged_paths = [line.strip() for line in (staged_res.stdout or "").splitlines() if line.strip()]
    if not staged_paths:
        raise ValueError("no staged changes")

    commit_res = _run("commit", "-m", message, timeout=30)
    stdout = (commit_res.stdout or "").strip()
    stderr = (commit_res.stderr or "").strip()
    if commit_res.returncode != 0:
        raise RuntimeError(stderr or stdout or f"git commit failed ({commit_res.returncode})")

    head_res = _run("rev-parse", "--short", "HEAD")
    commit_short = (head_res.stdout or "").strip() if head_res.returncode == 0 else ""
    commit_hash = (_run("rev-parse", "HEAD").stdout or "").strip()

    _runtime.record_git_commit(commit_hash=commit_hash, commit_short=commit_short, subject=message, agent=agent)
    _clear_branch_overview_cache()

    return {
        "ok": True,
        "message": message,
        "commit_short": commit_short,
        "paths": staged_paths,
        "stdout": stdout,
    }


def git_restore_file(*, rel_path: str):
    """Discard staged + unstaged changes for one path; match `git restore --staged --worktree`."""
    root = Path(_workspace or _repo_root).resolve()
    rel_path = str(rel_path or "").strip().lstrip("/")
    if not rel_path:
        raise ValueError("path required")
    candidate = (root / rel_path).resolve()
    try:
        normalized = candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise PermissionError("outside workspace") from exc

    def _run(*args, timeout=20):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    restore_res = _run("restore", "--staged", "--worktree", "--", normalized, timeout=30)
    if restore_res.returncode != 0:
        checkout_res = _run("checkout", "HEAD", "--", normalized, timeout=30)
        if checkout_res.returncode != 0:
            msg = (
                restore_res.stderr
                or restore_res.stdout
                or checkout_res.stderr
                or checkout_res.stdout
                or "git restore failed"
            ).strip()
            raise RuntimeError(msg)

    _runtime.append_system_entry(
        f"Restored to HEAD: {normalized}",
        kind="git-restore",
        path=normalized,
    )
    _clear_branch_overview_cache()
    return {"ok": True, "path": normalized}
