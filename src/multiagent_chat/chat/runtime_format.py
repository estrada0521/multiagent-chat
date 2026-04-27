from __future__ import annotations

import re


def _pane_runtime_tag_occurrences(events: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    normalized: list[dict] = []
    for event in events:
        source_id = str((event or {}).get("source_id") or "").strip()
        if not source_id:
            continue
        counts[source_id] = counts.get(source_id, 0) + 1
        normalized.append({
            **event,
            "source_id": f"{source_id}#{counts[source_id]}",
        })
    return normalized


def _pane_runtime_with_occurrence_ids(events: list[dict], *, limit: int) -> list[dict]:
    normalized = _pane_runtime_tag_occurrences(events)
    return normalized[-max(1, int(limit)) :]


def _remove_all_but_last_thought(text: str, start_idx: int, end_idx: int) -> str:
    pattern = r"\[Thought: true\](.*?)(?=\[Thought: true\]|$)"
    matches = list(re.finditer(pattern, text, re.DOTALL))

    if start_idx >= len(matches) or end_idx >= len(matches):
        return text

    blocks_to_remove = matches[start_idx:end_idx]
    result = text
    for match in reversed(blocks_to_remove):
        result = result[: match.start()] + result[match.end() :]
    return result


def _deduplicate_consecutive_thought_blocks(text: str) -> str:
    pattern = r"\[Thought: true\](.*?)(?=\[Thought: true\]|$)"
    matches = list(re.finditer(pattern, text, re.DOTALL))

    if len(matches) < 2:
        return text

    result = text
    consecutive_start = None

    for i in range(len(matches)):
        if i == 0:
            consecutive_start = 0
        else:
            prev_end = matches[i - 1].end()
            curr_start = matches[i].start()
            between = text[prev_end:curr_start].strip()

            if between:
                if consecutive_start is not None and i - 1 > consecutive_start:
                    result = _remove_all_but_last_thought(result, consecutive_start, i - 1)
                consecutive_start = i

    if consecutive_start is not None and len(matches) - 1 > consecutive_start:
        result = _remove_all_but_last_thought(result, consecutive_start, len(matches) - 1)

    return result


def _pane_runtime_gemini_with_occurrence_ids(events: list[dict], *, limit: int) -> list[dict]:
    tagged = _pane_runtime_tag_occurrences(events)
    lim = max(1, int(limit))
    if len(tagged) <= lim:
        return tagged

    tail = tagged[-lim:]
    if any("✦" in str((e or {}).get("text") or "") for e in tail):
        return tail

    last_thought = None
    for i in range(len(tagged) - 1, -1, -1):
        if "✦" in str((tagged[i] or {}).get("text") or ""):
            last_thought = tagged[i]
            break

    if not last_thought:
        return tail

    return [last_thought] + tagged[-(lim - 1) :]
