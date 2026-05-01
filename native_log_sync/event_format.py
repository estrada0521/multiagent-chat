from __future__ import annotations


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
