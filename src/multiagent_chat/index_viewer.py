"""Render and follow session index files for agent-index."""

from __future__ import annotations

import json
import os
import sys
import time


def _matches(entry: dict[str, object], filter_agent: str) -> bool:
    if not filter_agent:
        return True
    if str(entry.get("sender", "")).lower() == filter_agent:
        return True
    return any(str(target).lower() == filter_agent for target in entry.get("targets", []))


def _render(entry: dict[str, object], json_mode: bool) -> str:
    if json_mode:
        return json.dumps(entry, ensure_ascii=True)
    targets = ",".join(str(target) for target in entry.get("targets", []))
    return f'{entry["timestamp"]}  {entry["sender"]} -> {targets}\n  {entry["message"]}'


def _read_entries(path: str) -> list[dict[str, object]]:
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 5:
        raise SystemExit(
            "usage: python -m multiagent_chat.index_viewer <path> <limit> <filter_agent> <json_mode> <follow_mode>"
        )

    path = argv[0]
    limit = int(argv[1])
    filter_agent = argv[2].strip().lower()
    json_mode = argv[3] == "1"
    follow_mode = argv[4] == "1"

    entries = [entry for entry in _read_entries(path) if _matches(entry, filter_agent)]
    if limit and limit > 0:
        entries = entries[-limit:]
    for entry in entries:
        print(_render(entry, json_mode))

    if not follow_mode:
        return

    position = os.path.getsize(path)
    while True:
        time.sleep(0.5)
        if not os.path.exists(path):
            continue
        current_size = os.path.getsize(path)
        if current_size < position:
            position = 0
        if current_size == position:
            continue
        with open(path, "r", encoding="utf-8") as handle:
            handle.seek(position)
            chunk = handle.read()
            position = handle.tell()
        for line in chunk.splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if _matches(entry, filter_agent):
                print(_render(entry, json_mode), flush=True)


if __name__ == "__main__":
    main()
