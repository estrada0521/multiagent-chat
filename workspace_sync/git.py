from __future__ import annotations

import hashlib
import json
import re
import subprocess
import threading
import time
from pathlib import Path

from backend_core.agents.registry import AGENTS, ALL_AGENT_NAMES

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


def invalidate_branch_overview_cache() -> None:
    _clear_branch_overview_cache()


def _agent_from_text_multiagent_email(text: str) -> str:
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


def _recent_logged_commit_agents(max_lines: int = 4000) -> dict[str, str]:
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
    def _status_bucket_paths(lines: list[str]) -> tuple[set[str], set[str], set[str]]:
        staged: set[str] = set()
        unstaged: set[str] = set()
        untracked: set[str] = set()
        for raw in lines:
            line = str(raw or "")
            path = _status_path_for_fingerprint(line)
            if not path:
                continue
            if line.startswith("??"):
                untracked.add(path)
                continue
            x = line[0] if len(line) > 0 else " "
            y = line[1] if len(line) > 1 else " "
            if x not in {" ", "?"}:
                staged.add(path)
            if y not in {" ", "?"}:
                unstaged.add(path)
        return staged, unstaged, untracked
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
    staged_paths, unstaged_paths, untracked_paths = _status_bucket_paths(status_lines)
    staged_diff_res = _run("diff", "--numstat", "--cached", "--")
    unstaged_diff_res = _run("diff", "--numstat", "--")
    worktree_staged_added, worktree_staged_deleted = _parse_numstat(staged_diff_res)
    worktree_unstaged_added, worktree_unstaged_deleted = _parse_numstat(unstaged_diff_res)
    worktree_has_untracked_diff = bool(untracked_paths)
    worktree_added = 0
    worktree_deleted = 0
    diff_head_res = _run("diff", "--numstat", "HEAD", "--")
    worktree_has_staged_diff = staged_diff_res.returncode == 0 and bool((staged_diff_res.stdout or "").strip())
    worktree_has_unstaged_diff = unstaged_diff_res.returncode == 0 and bool((unstaged_diff_res.stdout or "").strip())
    worktree_has_diff = worktree_has_staged_diff or worktree_has_unstaged_diff or worktree_has_untracked_diff
    if diff_head_res.returncode == 0:
        worktree_added, worktree_deleted = _parse_numstat(diff_head_res)
        worktree_has_diff = bool((diff_head_res.stdout or "").strip()) or worktree_has_untracked_diff
    else:
        worktree_added = worktree_unstaged_added + worktree_staged_added
        worktree_deleted = worktree_unstaged_deleted + worktree_staged_deleted
    logged_commit_agents = _recent_logged_commit_agents()
    log_res = _run(
        "log",
        f"--skip={offset}",
        f"--max-count={limit}",
        "--format=%h\x1f%aI\x1f%s\x1f%an\x1f%cn\x1f%ae\x1f%ce\x1f%(trailers:key=Co-Authored-By,valueonly,separator=;)\x1f%D",
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
            refs = parts[8].strip() if len(parts) > 8 else ""
            recent_commits.append({
                "hash": h,
                "time": hhmm,
                "subject": subj,
                "agent": agent,
                "is_origin_main": "origin/main" in refs,
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
        "worktree_staged_added": worktree_staged_added,
        "worktree_staged_deleted": worktree_staged_deleted,
        "worktree_staged_changed_paths": len(staged_paths),
        "worktree_staged_has_diff": worktree_has_staged_diff,
        "worktree_unstaged_added": worktree_unstaged_added,
        "worktree_unstaged_deleted": worktree_unstaged_deleted,
        "worktree_unstaged_changed_paths": len(unstaged_paths),
        "worktree_unstaged_has_diff": worktree_has_unstaged_diff,
        "worktree_untracked_has_diff": worktree_has_untracked_diff,
        "worktree_untracked_changed_paths": len(untracked_paths),
        "worktree_fingerprint": _worktree_fingerprint(),
        "status_lines": status_lines[:8],
        "recent_commits": recent_commits,
    }
    with _branch_overview_cache_lock:
        _branch_overview_cache[cache_key] = (time.monotonic(), result)
    return result


def git_diff_files(*, commit_hash: str = "", scope: str = ""):
    root = Path(_workspace or _repo_root)
    commit_hash = str(commit_hash or "").strip()
    scope = str(scope or "").strip().lower()

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
    def _untracked_paths() -> list[str]:
        res = _run("ls-files", "--others", "--exclude-standard", "--full-name", "--")
        if res.returncode != 0:
            return []
        return [line.strip() for line in (res.stdout or "").splitlines() if line.strip()]
    def _append_untracked(files: list[dict], paths: list[str]) -> list[dict]:
        seen = {str(item.get("path") or "").strip() for item in files}
        merged = list(files)
        for path in paths:
            if path in seen:
                continue
            merged.append({
                "path": path,
                "ins": 0,
                "dels": 0,
                "changed": 0,
                "binary": False,
                "untracked": True,
            })
            seen.add(path)
        return merged

    lines: list[str] = []
    include_untracked = False
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
        if scope == "staged":
            diff_res = _run("diff", "--numstat", "--cached", "--")
            if diff_res.returncode != 0:
                raise RuntimeError((diff_res.stderr or diff_res.stdout or "git diff failed").strip())
            lines = (diff_res.stdout or "").splitlines()
        elif scope == "unstaged":
            diff_res = _run("diff", "--numstat", "--")
            if diff_res.returncode != 0:
                raise RuntimeError((diff_res.stderr or diff_res.stdout or "git diff failed").strip())
            lines = (diff_res.stdout or "").splitlines()
        elif scope == "untracked":
            lines = []
            include_untracked = True
        else:
            include_untracked = True
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
    if include_untracked:
        files = _append_untracked(files, _untracked_paths())
    return {
        "hash": commit_hash,
        "scope": scope,
        "changed_paths": len(files),
        "total_ins": total_ins,
        "total_dels": total_dels,
        "files": files,
    }



def git_restore_file(*, rel_path: str, scope: str = ""):
    root = Path(_workspace or _repo_root).resolve()
    rel_path = str(rel_path or "").strip().lstrip("/")
    scope = str(scope or "").strip().lower()
    if not rel_path:
        raise ValueError("path required")
    if scope not in {"", "unstaged"}:
        raise ValueError("invalid scope")
    candidate = (root / rel_path).resolve()
    try:
        normalized = candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise PermissionError("outside workspace") from exc
    status_res = subprocess.run(
        ["git", "-C", str(root), "status", "--short", "--untracked-files=all", "--", normalized],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    status_lines = [line.rstrip() for line in (status_res.stdout or "").splitlines() if line.strip()]
    is_untracked = any(line.startswith("?? ") for line in status_lines)
    if is_untracked:
        raise ValueError("cannot restore untracked file")

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

    restore_args = ["restore"]
    if scope == "unstaged":
        restore_args.append("--worktree")
    else:
        restore_args.append("--worktree")
    restore_res = _run(*restore_args, "--", normalized, timeout=30)
    if restore_res.returncode != 0:
        msg = (restore_res.stderr or restore_res.stdout or "git restore failed").strip()
        raise RuntimeError(msg)

    _clear_branch_overview_cache()
    return {"ok": True, "path": normalized}


def _resolve_repo_path(rel_path: str) -> tuple[Path, str]:
    root = Path(_workspace or _repo_root).resolve()
    rel_path = str(rel_path or "").strip().lstrip("/")
    if not rel_path:
        raise ValueError("path required")
    candidate = (root / rel_path).resolve()
    try:
        normalized = candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise PermissionError("outside workspace") from exc
    return candidate, normalized


def _git_status_lines(root: Path, normalized: str) -> list[str]:
    status_res = subprocess.run(
        ["git", "-C", str(root), "status", "--short", "--untracked-files=all", "--", normalized],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    return [line.rstrip() for line in (status_res.stdout or "").splitlines() if line.strip()]


def git_delete_untracked_file(*, rel_path: str):
    root = Path(_workspace or _repo_root).resolve()
    candidate, normalized = _resolve_repo_path(rel_path)
    status_lines = _git_status_lines(root, normalized)
    if not any(line.startswith("?? ") for line in status_lines):
        raise ValueError("file is not untracked")
    if not candidate.exists():
        raise FileNotFoundError(normalized)
    if candidate.is_dir():
        raise ValueError("cannot delete directory")
    candidate.unlink()
    _clear_branch_overview_cache()
    return {"ok": True, "path": normalized}


def git_ignore_file(*, rel_path: str):
    root = Path(_workspace or _repo_root).resolve()
    _, normalized = _resolve_repo_path(rel_path)
    status_lines = _git_status_lines(root, normalized)
    if not any(line.startswith("?? ") for line in status_lines):
        raise ValueError("file is not untracked")

    gitignore_path = root / ".gitignore"
    content = ""
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")

    new_line = normalized
    if content and not content.endswith("\n"):
        new_line = "\n" + new_line
    if not content.endswith("\n"):
         new_line += "\n"
    elif not new_line.endswith("\n"):
         new_line += "\n"

    with gitignore_path.open("a", encoding="utf-8") as f:
        f.write(new_line)

    _clear_branch_overview_cache()
    return {"ok": True, "path": normalized}


