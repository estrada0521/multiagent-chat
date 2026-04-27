#!/usr/bin/env python3
"""Remove chat index lines whose body is only ``[REDACTED]``; strip trailing placeholder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from multiagent_chat.redacted_placeholder import compact_agent_index_jsonl


def main() -> int:
    p = argparse.ArgumentParser(
        description="Compact .agent-index.jsonl: drop [REDACTED]-only messages, trim trailing [REDACTED]."
    )
    p.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Paths to .agent-index.jsonl (default: scan ./logs for **/.agent-index.jsonl)",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root when scanning ./logs (default: cwd)",
    )
    args = p.parse_args()
    targets: list[Path] = []
    if args.paths:
        targets = [Path(x) for x in args.paths]
    else:
        logs = (args.repo_root / "logs").resolve()
        if logs.is_dir():
            targets = sorted(logs.glob("**/.agent-index.jsonl"))
        if not targets:
            print("No paths given and no logs/**/.agent-index.jsonl found.", file=sys.stderr)
            return 1

    total_rm = total_rw = 0
    for path in targets:
        path = path.resolve()
        if not path.is_file():
            print(f"skip (not a file): {path}", file=sys.stderr)
            continue
        kept, removed, rewritten = compact_agent_index_jsonl(path)
        if removed or rewritten:
            print(f"{path}: kept={kept} removed={removed} rewritten={rewritten}")
        total_rm += removed
        total_rw += rewritten
    if total_rm == 0 and total_rw == 0:
        print("No changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
