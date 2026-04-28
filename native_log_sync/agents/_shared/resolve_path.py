from __future__ import annotations

import os
import re
import sys
import unicodedata
from pathlib import Path

from native_log_sync.agents._shared.path_state import NativeLogCursor, _normalized_native_log_path


def workspace_slug_variants(path_value: str, *, include_lower: bool = False) -> list[str]:
    raw_slug = str(path_value or "").replace("/", "-").lstrip("-")
    if not raw_slug:
        return []
    variants: list[str] = []
    seen: set[str] = set()
    source_values: list[str] = []
    for candidate in (
        raw_slug,
        unicodedata.normalize("NFC", raw_slug),
        unicodedata.normalize("NFKC", raw_slug),
    ):
        if candidate not in source_values:
            source_values.append(candidate)
    for source in source_values:
        for candidate in (
            source,
            source.replace("_", "-"),
            re.sub(r"[^A-Za-z0-9.-]+", "-", source),
            re.sub(r"[^A-Za-z0-9.-]", "-", source),
            re.sub(r"[^A-Za-z0-9-]+", "-", source),
            re.sub(r"[^A-Za-z0-9-]", "-", source),
        ):
            trimmed = candidate.strip("-")
            compacted = re.sub(r"-+", "-", candidate).strip("-")
            for normalized in (trimmed, compacted):
                if not normalized:
                    continue
                outputs = (normalized, normalized.lower()) if include_lower else (normalized,)
                for output in outputs:
                    if output and output not in seen:
                        seen.add(output)
                        variants.append(output)
    return variants


def path_within_roots(path: str | Path, roots: list[Path]) -> bool:
    candidate = str(path or "").strip()
    if not candidate or not roots:
        return False
    candidate_real = os.path.realpath(candidate)
    candidate_cmp = candidate_real.lower() if sys.platform == "darwin" else candidate_real
    for root in roots:
        root_real = os.path.realpath(str(root))
        root_cmp = root_real.lower() if sys.platform == "darwin" else root_real
        root_prefix = root_cmp.rstrip(os.sep) + os.sep
        if candidate_cmp == root_cmp or candidate_cmp.startswith(root_prefix):
            return True
    return False


def pick_latest_unclaimed_for_agent(
    candidates: list[Path],
    cursors: dict[str, NativeLogCursor],
    agent: str,
    *,
    min_mtime: float = 0.0,
) -> Path | None:
    if not candidates:
        return None
    claimed: set[str] = set()
    for other_agent, cursor in cursors.items():
        if other_agent == agent:
            continue
        claimed.add(_normalized_native_log_path(cursor.path))
    eligible: list[tuple[float, Path]] = []
    seen_candidate_paths: set[str] = set()
    for candidate in candidates:
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            continue
        if mtime < min_mtime:
            continue
        candidate_path = _normalized_native_log_path(candidate)
        if candidate_path in claimed or candidate_path in seen_candidate_paths:
            continue
        seen_candidate_paths.add(candidate_path)
        eligible.append((mtime, candidate))
    if not eligible:
        return None
    eligible.sort(key=lambda item: item[0], reverse=True)
    return eligible[0][1]
