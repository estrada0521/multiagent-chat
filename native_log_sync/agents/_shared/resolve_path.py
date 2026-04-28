from __future__ import annotations

import os
import re
import sys
import unicodedata
from pathlib import Path

from native_log_sync.io.cursor_state import NativeLogCursor, _native_path_claim_key


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
    min_mtime: float,
    *,
    exclude_paths: set[str] | None = None,
) -> Path | None:
    if not candidates:
        return None
    claimed: set[str] = set()
    normalize_exclude = {_native_path_claim_key(p) for p in exclude_paths} if exclude_paths else set()
    for other_agent, cursor in cursors.items():
        if other_agent == agent:
            continue
        claimed.add(_native_path_claim_key(cursor.path))
    eligible: list[tuple[float, Path]] = []
    seen_candidate_keys: set[str] = set()
    for candidate in candidates:
        try:
            stat_result = candidate.stat()
            mtime = stat_result.st_mtime
        except OSError:
            continue
        if mtime < min_mtime:
            continue
        candidate_key = _native_path_claim_key(candidate, stat_result=stat_result)
        if candidate_key in claimed or candidate_key in normalize_exclude or candidate_key in seen_candidate_keys:
            continue
        seen_candidate_keys.add(candidate_key)
        eligible.append((mtime, candidate))
    if not eligible:
        return None
    eligible.sort(key=lambda item: item[0], reverse=True)
    return eligible[0][1]
