from __future__ import annotations


def entry_window(
    entries: list[dict],
    *,
    limit_override: int | None,
    default_limit: int,
    before_msg_id: str = "",
    around_msg_id: str = "",
) -> tuple[list[dict], bool]:
    target_around = around_msg_id.strip()
    limit = limit_override if limit_override is not None else default_limit
    if target_around:
        idx = next((i for i, entry in enumerate(entries) if str(entry.get("msg_id") or "") == target_around), -1)
        if idx >= 0:
            if limit and limit > 0:
                half = max(0, limit // 2)
                start = max(0, idx - half)
                end = min(len(entries), start + limit)
                start = max(0, end - limit)
                has_older = start > 0
                return entries[start:end], has_older
            return entries, idx > 0
    if before_msg_id:
        target = before_msg_id.strip()
        idx = next((i for i, entry in enumerate(entries) if str(entry.get("msg_id") or "") == target), -1)
        if idx < 0:
            return [], False
        entries = entries[:idx]
    has_older = False
    if limit and limit > 0:
        has_older = len(entries) > limit
        return entries[-limit:], has_older
    return entries, False
