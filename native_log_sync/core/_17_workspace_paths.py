from __future__ import annotations

import os
import subprocess
from pathlib import Path

from native_log_sync.agents._shared.resolve_path import workspace_slug_variants


def workspace_git_root(runtime, workspace: str, *, subprocess_module=subprocess, path_class=Path) -> str:
    cached = runtime._workspace_git_root_cache.get(workspace)
    if cached is not None:
        return cached
    git_root = ""
    try:
        res = subprocess_module.run(
            ["git", "-C", workspace, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0:
            candidate = (res.stdout or "").strip()
            if candidate:
                git_root = str(path_class(candidate).resolve())
    except Exception:
        git_root = ""
    runtime._workspace_git_root_cache[workspace] = git_root
    return git_root


def workspace_aliases(runtime, workspace: str, *, path_class=Path) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()

    def _push_alias(value: str) -> None:
        item = str(value or "").strip()
        if not item or item in seen:
            return
        seen.add(item)
        aliases.append(item)

    def _tmp_aliases(value: str) -> list[str]:
        item = str(value or "").strip()
        if not item:
            return []
        if item == "/tmp" or item.startswith("/tmp/"):
            return [item, f"/private{item}"]
        if item == "/private/tmp" or item.startswith("/private/tmp/"):
            return [item, item[len("/private") :]]
        return [item]

    for candidate in (workspace, workspace_git_root(runtime, workspace)):
        value = str(candidate or "").strip()
        if not value:
            continue
        variants = [value]
        try:
            variants.append(str(path_class(value).resolve()))
        except Exception:
            pass
        for variant in variants:
            for alias in _tmp_aliases(variant):
                _push_alias(alias)
    return aliases


def cursor_transcript_roots(runtime, workspace: str, *, path_class=Path) -> list[Path]:
    slug_candidates: list[str] = []
    seen_slugs: set[str] = set()

    def _append_slug_from_path(path_value: str) -> None:
        slug = str(path_value).replace("/", "-").lstrip("-")
        if slug and slug not in seen_slugs:
            seen_slugs.add(slug)
            slug_candidates.append(slug)

    for path_value in workspace_aliases(runtime, workspace):
        pv = str(path_value or "").strip()
        if not pv:
            continue
        _append_slug_from_path(pv)
        for v in workspace_slug_variants(pv):
            _append_slug_from_path(v)
        workspace_name = path_class(pv).name.strip()
        if workspace_name:
            for v in workspace_slug_variants(workspace_name, include_lower=True):
                _append_slug_from_path(v)

    roots: list[Path] = []
    seen_roots: set[str] = set()
    for slug in slug_candidates:
        root = path_class.home() / ".cursor" / "projects" / slug / "agent-transcripts"
        if not root.exists():
            continue
        try:
            key = str(root.resolve())
        except OSError:
            key = str(root)
        if key not in seen_roots:
            seen_roots.add(key)
            roots.append(root)
    return roots


def cursor_fsevent_watch_path_strings(runtime, workspace: str, *, path_class=Path) -> list[str]:
    workspace_text = str(workspace or "").strip()
    if not workspace_text:
        return []
    home = path_class.home()
    projects_base = home / ".cursor" / "projects"
    paths: list[str] = []
    seen: set[str] = set()
    need_broad = False
    for path_value in workspace_aliases(runtime, workspace_text):
        slug = str(path_value).replace("/", "-").lstrip("-")
        if not slug:
            continue
        transcripts = home / ".cursor" / "projects" / slug / "agent-transcripts"
        proj = home / ".cursor" / "projects" / slug
        if transcripts.is_dir():
            candidate = transcripts
        elif proj.is_dir():
            candidate = proj
        else:
            need_broad = True
            continue
        resolved = str(candidate.resolve())
        if resolved not in seen:
            seen.add(resolved)
            paths.append(resolved)
    if need_broad and projects_base.is_dir():
        broad = str(projects_base.resolve())
        if broad not in seen:
            paths.append(broad)
    if not paths and workspace_text and projects_base.is_dir():
        paths.append(str(projects_base.resolve()))
    chats_dir = home / ".cursor" / "chats"
    if chats_dir.is_dir():
        chats_resolved = str(chats_dir.resolve())
        if chats_resolved not in seen:
            paths.append(chats_resolved)
    return paths


def claude_fsevent_watch_path_strings(runtime, workspace: str, *, path_class=Path) -> list[str]:
    workspace_text = str(workspace or "").strip()
    if not workspace_text:
        return []
    home = path_class.home()
    projects_base = home / ".claude" / "projects"
    if not projects_base.exists():
        return []
    paths: list[str] = []
    seen: set[str] = set()
    need_broad = False
    for path_value in workspace_aliases(runtime, workspace_text):
        found = False
        for slug in workspace_slug_variants(str(path_value)):
            proj = home / ".claude" / "projects" / f"-{slug}"
            if proj.is_dir():
                resolved = str(proj.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(resolved)
                found = True
                break
        if not found:
            need_broad = True
    if need_broad or not paths:
        broad = str(projects_base.resolve())
        if broad not in seen:
            paths.append(broad)
    return paths


def codex_fsevent_watch_path_strings(runtime, workspace: str, *, path_class=Path) -> list[str]:
    sessions = path_class.home() / ".codex" / "sessions"
    return [str(sessions.resolve())] if sessions.exists() else []


def copilot_fsevent_watch_path_strings(runtime, workspace: str, *, path_class=Path) -> list[str]:
    session_state = path_class.home() / ".copilot" / "session-state"
    return [str(session_state.resolve())] if session_state.exists() else []


def opencode_fsevent_watch_path_strings(runtime, workspace: str, *, path_class=Path) -> list[str]:
    share_dir = path_class.home() / ".local" / "share" / "opencode"
    return [str(share_dir.resolve())] if share_dir.is_dir() else []


def qwen_fsevent_watch_path_strings(runtime, workspace: str, *, path_class=Path) -> list[str]:
    workspace_text = str(workspace or "").strip()
    if not workspace_text:
        return []
    home = path_class.home()
    projects_base = home / ".qwen" / "projects"
    if not projects_base.exists():
        return []
    paths: list[str] = []
    seen: set[str] = set()
    need_broad = False
    for path_value in workspace_aliases(runtime, workspace_text):
        found = False
        for slug in workspace_slug_variants(str(path_value), include_lower=True):
            chats_dir = home / ".qwen" / "projects" / f"-{slug}" / "chats"
            proj_dir = home / ".qwen" / "projects" / f"-{slug}"
            if chats_dir.is_dir():
                resolved = str(chats_dir.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(resolved)
                found = True
                break
            elif proj_dir.is_dir():
                resolved = str(proj_dir.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(resolved)
                found = True
                break
        if not found:
            need_broad = True
    if need_broad or not paths:
        broad = str(projects_base.resolve())
        if broad not in seen:
            paths.append(broad)
    return paths


def gemini_fsevent_watch_path_strings(runtime, workspace: str, *, path_class=Path) -> list[str]:
    workspace_text = str(workspace or "").strip()
    if not workspace_text:
        return []
    home = path_class.home()
    tmp_base = home / ".gemini" / "tmp"
    if not tmp_base.exists():
        return []
    paths: list[str] = []
    seen: set[str] = set()
    need_broad = False
    for alias in workspace_aliases(runtime, workspace_text):
        workspace_name = path_class(str(alias)).name.strip()
        if not workspace_name:
            continue
        found = False
        for variant in workspace_slug_variants(workspace_name, include_lower=True):
            chats_dir = home / ".gemini" / "tmp" / variant / "chats"
            variant_dir = home / ".gemini" / "tmp" / variant
            if chats_dir.is_dir():
                resolved = str(chats_dir.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(resolved)
                found = True
                break
            elif variant_dir.is_dir():
                resolved = str(variant_dir.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(resolved)
                found = True
                break
        if not found:
            need_broad = True
    if need_broad or not paths:
        broad = str(tmp_base.resolve())
        if broad not in seen:
            paths.append(broad)
    return paths
