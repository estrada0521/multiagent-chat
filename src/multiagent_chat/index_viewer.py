from __future__ import annotations

import json
import sys


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
    if len(argv) != 4:
        raise SystemExit(
            "usage: python -m multiagent_chat.index_viewer <path> <limit> <filter_agent> <json_mode>"
        )

    path = argv[0]
    limit = int(argv[1])
    filter_agent = argv[2].strip().lower()
    json_mode = argv[3] == "1"

    entries = [entry for entry in _read_entries(path) if _matches(entry, filter_agent)]
    if limit and limit > 0:
        entries = entries[-limit:]
    for entry in entries:
        print(_render(entry, json_mode))


if __name__ == "__main__":
    main()
