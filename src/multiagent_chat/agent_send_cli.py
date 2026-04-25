from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .agent_registry import ALL_AGENT_NAMES, number_alias_map
from .agent_send_core import AgentSendError, AgentSendRuntime


def _usage_text() -> str:
    aliases = number_alias_map()
    alias_line = "  " + "  ".join(f"{n}={aliases[n]}" for n in sorted(aliases))
    return "\n".join(
        [
            "Usage: agent-send [--session NAME] [--reply MSG_ID] <target>",
            "",
            "Message body is read from stdin.",
            "",
            "Examples:",
            "  printf '%s' 'hello' | agent-send claude",
            "  agent-send --reply abc123 codex <<'MSGEOF'",
            "  [From: user] hello",
            "  MSGEOF",
            "",
            "Targets:",
            f"  {', '.join(ALL_AGENT_NAMES)} | others",
            alias_line,
            "  claude-1       (specific instance when duplicates exist)",
            "  claude,codex   (comma-separated targets)",
            "  claude         (sends to ALL claude instances if duplicated)",
        ]
    )


def _parse_agent_send_args(argv: list[str]) -> tuple[bool, str, str, str]:
    show_help = False
    session_name = (os.environ.get("MULTIAGENT_SESSION") or "").strip()
    reply_to = ""
    idx = 0

    while idx < len(argv):
        token = argv[idx]
        if token in {"-h", "--help"}:
            show_help = True
            idx += 1
            continue
        if token == "--session":
            if idx + 1 >= len(argv):
                raise AgentSendError("agent-send: --session requires a value")
            session_name = argv[idx + 1]
            idx += 2
            continue
        if token == "--reply":
            if idx + 1 >= len(argv):
                raise AgentSendError("agent-send: --reply requires a value")
            reply_to = argv[idx + 1]
            idx += 2
            continue
        if token == "--stdin":
            raise AgentSendError("agent-send: --stdin has been removed; stdin is now the default")
        if token == "--":
            idx += 1
            break
        break

    remaining = argv[idx:]
    if show_help and not remaining:
        return True, session_name, reply_to, ""
    if not remaining:
        return False, session_name, reply_to, ""

    target = remaining[0]
    extras = remaining[1:]
    if extras:
        raise AgentSendError(
            "agent-send: inline text arguments are no longer supported.\n\n"
            "Pass the message body on stdin instead.\n\n"
            "Examples:\n"
            "  printf '%s' 'hello' | agent-send claude\n"
            "  agent-send --reply <msg-id> claude <<'MSGEOF'\n"
            "  [From: codex] hello\n"
            "  MSGEOF"
        )
    return False, session_name, reply_to, target


def run(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("--repo-root", default="")
    bootstrap.add_argument("--script-dir", default="")
    known, remaining = bootstrap.parse_known_args(args)

    repo_root = Path(known.repo_root).resolve() if known.repo_root else Path(__file__).resolve().parents[2]
    script_dir = Path(known.script_dir).resolve() if known.script_dir else (repo_root / "bin")

    try:
        show_help, session_name, reply_to, target = _parse_agent_send_args(remaining)
    except AgentSendError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if show_help:
        print(_usage_text())
        return 0

    if not target:
        print(_usage_text(), file=sys.stderr)
        return 1

    if sys.stdin.isatty():
        print(
            "agent-send requires a message body on stdin.\n\n"
            "Examples:\n"
            "  printf '%s' 'hello' | agent-send claude\n"
            "  printf '%s' 'hello' | agent-send --reply <msg-id> claude",
            file=sys.stderr,
        )
        return 1

    payload = sys.stdin.read()
    if payload == "":
        # Keep parity with shell behavior: empty stdin is treated as empty body.
        print("agent-send: empty message body", file=sys.stderr)
        return 1
    if not payload:
        print("agent-send: empty message body", file=sys.stderr)
        return 1

    runtime = AgentSendRuntime(
        repo_root=repo_root,
        script_dir=script_dir,
        env=dict(os.environ),
        cwd=Path.cwd(),
    )

    try:
        success = runtime.send_message(
            target_spec=target,
            payload=payload,
            explicit_session=session_name,
            reply_to=reply_to,
        )
    except AgentSendError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0 if success else 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
