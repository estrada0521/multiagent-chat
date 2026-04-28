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
