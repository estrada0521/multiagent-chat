"""Resolve the chat port for a session from the command line."""

from __future__ import annotations

import sys
from pathlib import Path

from agent_index.state_core import resolve_chat_port


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        raise SystemExit("usage: python -m agent_index.chat_port_cli <repo_root> <session_name>")
    repo_root = Path(argv[0]).resolve()
    session_name = argv[1] or "default"
    print(resolve_chat_port(repo_root, session_name))


if __name__ == "__main__":
    main()
