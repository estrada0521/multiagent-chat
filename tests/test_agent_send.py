from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import _bootstrap

REPO_ROOT = _bootstrap.REPO_ROOT
AGENT_SEND = REPO_ROOT / "bin" / "agent-send"


class AgentSendIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        self.log_root = self.base / "logs"
        self.session_name = "test-session"
        self.fake_tmux_dir = self.base / "fake-tmux"
        self.fake_tmux_dir.mkdir()
        self._install_fake_tmux()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _install_fake_tmux(self) -> None:
        script = self.fake_tmux_dir / "tmux"
        script.write_text(
            """#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


def state_path(*parts: str) -> Path:
    return Path(os.environ["FAKE_TMUX_DIR"], *parts)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def load_session(session: str) -> dict[str, str]:
    data = {}
    for line in read_text(state_path(f"session_{session}.env")).splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key] = value
    return data


args = sys.argv[1:]
while len(args) >= 2 and args[0] in {"-L", "-S"}:
    args = args[2:]
if not args:
    sys.exit(1)
cmd = args[0]

if cmd == "show-environment":
    session = args[args.index("-t") + 1]
    key = args[-1]
    value = load_session(session).get(key)
    if value is None:
        sys.exit(1)
    sys.stdout.write(f"{key}={value}\\n")
    sys.exit(0)

if cmd == "set-buffer":
    payload = args[args.index("--") + 1] if "--" in args else args[-1]
    write_text(state_path("buffer.txt"), payload)
    sys.exit(0)

if cmd == "paste-buffer":
    pane = args[args.index("-t") + 1]
    pane_path = state_path(f"pane_{pane}.txt")
    write_text(pane_path, read_text(pane_path) + read_text(state_path("buffer.txt")))
    sys.exit(0)

if cmd == "send-keys":
    pane = args[args.index("-t") + 1]
    pane_path = state_path(f"pane_{pane}.txt")
    write_text(pane_path, read_text(pane_path) + "\\n")
    sys.exit(0)

if cmd == "has-session":
    sys.exit(0)

if cmd == "display-message":
    sys.stdout.write(os.environ.get("MULTIAGENT_SESSION", "test-session") + "\\n")
    sys.exit(0)

if cmd == "list-sessions":
    sys.stdout.write(os.environ.get("MULTIAGENT_SESSION", "test-session") + "\\n")
    sys.exit(0)

sys.exit(1)
""",
            encoding="utf-8",
        )
        script.chmod(0o755)

    def _base_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.pop("TMUX", None)
        env.pop("TMUX_PANE", None)
        env.update(
            {
                "FAKE_TMUX_DIR": str(self.fake_tmux_dir),
                "MULTIAGENT_SESSION": self.session_name,
                "MULTIAGENT_WORKSPACE": str(self.workspace),
                "MULTIAGENT_LOG_DIR": str(self.log_root),
                "MULTIAGENT_AGENT_NAME": "codex-1",
                "PATH": f"{self.fake_tmux_dir}{os.pathsep}{env.get('PATH', '')}",
            }
        )
        return env

    def _run_agent_send(self, *args: str, message: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(AGENT_SEND), *args],
            input=message,
            text=True,
            capture_output=True,
            cwd=REPO_ROOT,
            env=self._base_env(),
            check=False,
        )

    def _read_entries(self) -> list[dict]:
        index_path = self.log_root / self.session_name / ".agent-index.jsonl"
        with index_path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def _write_tmux_session_env(self, **values: str) -> None:
        env_path = self.fake_tmux_dir / f"session_{self.session_name}.env"
        env_path.write_text(
            "".join(f"{key}={value}\n" for key, value in values.items()),
            encoding="utf-8",
        )

    def test_user_target_writes_jsonl_and_preserves_attachment_marker(self) -> None:
        result = self._run_agent_send("user", message="[Attached: docs/AGENT.md]\nhello")
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        entries = self._read_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["targets"], ["user"])
        self.assertIn("[Attached: docs/AGENT.md]", entries[0]["message"])
        self.assertIn("hello", entries[0]["message"])

    def test_reply_preview_is_recorded_for_follow_up_messages(self) -> None:
        first = self._run_agent_send("user", message="first message")
        self.assertEqual(first.returncode, 0, msg=first.stderr or first.stdout)
        first_entry = self._read_entries()[0]
        second = self._run_agent_send("--reply", first_entry["msg_id"], "user", message="second message")
        self.assertEqual(second.returncode, 0, msg=second.stderr or second.stdout)
        second_entry = self._read_entries()[1]
        self.assertEqual(second_entry["reply_to"], first_entry["msg_id"])
        self.assertEqual(second_entry["reply_preview"], f"{first_entry['sender']}: first message")

    def test_number_alias_resolves_and_delivers_to_tmux_agent(self) -> None:
        pane_id = "pane-claude"
        self._write_tmux_session_env(
            MULTIAGENT_BIN_DIR=str(REPO_ROOT / "bin"),
            MULTIAGENT_WORKSPACE=str(self.workspace),
            MULTIAGENT_LOG_DIR=str(self.log_root),
            MULTIAGENT_AGENTS="claude",
            MULTIAGENT_PANE_CLAUDE=pane_id,
        )
        result = self._run_agent_send("1", message="hello alias")
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        entries = self._read_entries()
        self.assertEqual(entries[0]["targets"], ["claude"])
        pane_text = (self.fake_tmux_dir / f"pane_{pane_id}.txt").read_text(encoding="utf-8")
        self.assertIn("hello alias", pane_text)


if __name__ == "__main__":
    unittest.main()
