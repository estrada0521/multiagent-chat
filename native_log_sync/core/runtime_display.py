from __future__ import annotations


def runtime_event(main: str, sub: str = "", *, source_id: str) -> dict:
    m = str(main or "").strip()
    s = str(sub or "").strip()
    if m and s:
        text = f"{m} {s}"
    elif m:
        text = m
    elif s:
        text = s
    else:
        text = ""
    return {"kind": "fixed", "text": text, "source_id": source_id}
