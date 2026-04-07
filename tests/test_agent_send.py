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
    fail_panes = {part for part in os.environ.get("FAKE_TMUX_FAIL_PANES", "").split(",") if part}
    if pane in fail_panes:
        sys.exit(1)
    pane_path = state_path(f"pane_{pane}.txt")
    write_text(pane_path, read_text(pane_path) + read_text(state_path("buffer.txt")))
    sys.exit(0)

if cmd == "send-keys":
    pane = args[args.index("-t") + 1]
    fail_panes = {part for part in os.environ.get("FAKE_TMUX_FAIL_PANES", "").split(",") if part}
    if "-l" in args and pane in fail_panes:
        sys.exit(1)
    trust_panes = {part for part in os.environ.get("FAKE_TMUX_TRUST_PANES", "").split(",") if part}
    trust_path = state_path(f"trust_{pane}.ok")
    pane_path = state_path(f"pane_{pane}.txt")
    if "-l" in args:
        payload = args[args.index("-l") + 1]
        write_text(pane_path, read_text(pane_path) + payload)
    else:
        if pane in trust_panes and ("Enter" in args or "a" in args):
            write_text(trust_path, "1")
            sys.exit(0)
        write_text(pane_path, read_text(pane_path) + "\\n")
    sys.exit(0)

if cmd == "capture-pane":
    pane = args[args.index("-t") + 1]
    trust_panes = {part for part in os.environ.get("FAKE_TMUX_TRUST_PANES", "").split(",") if part}
    trust_path = state_path(f"trust_{pane}.ok")
    if pane in trust_panes and not trust_path.exists():
        if "claude" in pane:
            sys.stdout.write(
                "Quick safety check\\n"
                "❯ 1. Yes, I trust this folder\\n"
                "Enter to confirm · Esc to cancel\\n"
            )
        elif "gemini" in pane:
            sys.stdout.write(
                "Do you trust the files in this folder?\\n"
                "● 1. Trust folder\\n"
            )
        elif "cursor" in pane:
            sys.stdout.write(
                "Workspace Trust Required\\n"
                "▶ [a] Trust this workspace\\n"
            )
        else:
            sys.stdout.write("Trust this workspace\\n")
        sys.exit(0)
    pane_text = read_text(state_path(f"pane_{pane}.txt"))
    if "claude" in pane:
        prompt = "❯\\n"
    elif "gemini" in pane or "qwen" in pane:
        prompt = "Type your message or @path/to/file\\n"
    elif "cursor" in pane:
        prompt = "/ commands · @ files · ! shell\\n"
    else:
        prompt = "›\\n"
    sys.stdout.write(pane_text + prompt)
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

    def _base_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
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
        if extra:
            env.update(extra)
        return env

    def _run_agent_send(
        self,
        *args: str,
        message: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(AGENT_SEND), *args],
            input=message,
            text=True,
            capture_output=True,
            cwd=REPO_ROOT,
            env=self._base_env(extra_env),
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

    def _pane_text(self, pane_id: str) -> str:
        return (self.fake_tmux_dir / f"pane_{pane_id}.txt").read_text(encoding="utf-8")

    def test_user_target_is_rejected(self) -> None:
        result = self._run_agent_send("user", message="hello")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('target "user" has been removed', result.stderr)
        index_path = self.log_root / self.session_name / ".agent-index.jsonl"
        self.assertFalse(index_path.exists())

    def test_reply_preview_is_recorded_for_follow_up_messages(self) -> None:
        self._write_tmux_session_env(
            MULTIAGENT_BIN_DIR=str(REPO_ROOT / "bin"),
            MULTIAGENT_WORKSPACE=str(self.workspace),
            MULTIAGENT_LOG_DIR=str(self.log_root),
            MULTIAGENT_AGENTS="claude",
            MULTIAGENT_PANE_CLAUDE="pane-claude",
        )
        first = self._run_agent_send("claude", message="first message")
        self.assertEqual(first.returncode, 0, msg=first.stderr or first.stdout)
        first_entry = self._read_entries()[-1]
        second = self._run_agent_send("--reply", first_entry["msg_id"], "claude", message="second message")
        self.assertEqual(second.returncode, 0, msg=second.stderr or second.stdout)
        second_entry = self._read_entries()[-1]
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
        self.assertEqual(entries[-1]["targets"], ["claude"])
        self.assertIn("hello alias", self._pane_text(pane_id))

    def test_claude_trust_prompt_is_auto_confirmed_before_delivery(self) -> None:
        pane_id = "pane-claude"
        self._write_tmux_session_env(
            MULTIAGENT_BIN_DIR=str(REPO_ROOT / "bin"),
            MULTIAGENT_WORKSPACE=str(self.workspace),
            MULTIAGENT_LOG_DIR=str(self.log_root),
            MULTIAGENT_AGENTS="claude",
            MULTIAGENT_PANE_CLAUDE=pane_id,
        )
        result = self._run_agent_send(
            "claude",
            message="hello after trust",
            extra_env={"FAKE_TMUX_TRUST_PANES": pane_id},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn("hello after trust", self._pane_text(pane_id))
        entries = self._read_entries()
        self.assertEqual(entries[-1]["targets"], ["claude"])

    def test_gemini_trust_prompt_is_auto_confirmed_before_delivery(self) -> None:
        pane_id = "pane-gemini"
        self._write_tmux_session_env(
            MULTIAGENT_BIN_DIR=str(REPO_ROOT / "bin"),
            MULTIAGENT_WORKSPACE=str(self.workspace),
            MULTIAGENT_LOG_DIR=str(self.log_root),
            MULTIAGENT_AGENTS="gemini",
            MULTIAGENT_PANE_GEMINI=pane_id,
        )
        result = self._run_agent_send(
            "gemini",
            message="hello gemini trust",
            extra_env={"FAKE_TMUX_TRUST_PANES": pane_id},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn("hello gemini trust", self._pane_text(pane_id))
        entries = self._read_entries()
        self.assertEqual(entries[-1]["targets"], ["gemini"])

    def test_cursor_trust_prompt_is_auto_confirmed_before_delivery(self) -> None:
        pane_id = "pane-cursor"
        self._write_tmux_session_env(
            MULTIAGENT_BIN_DIR=str(REPO_ROOT / "bin"),
            MULTIAGENT_WORKSPACE=str(self.workspace),
            MULTIAGENT_LOG_DIR=str(self.log_root),
            MULTIAGENT_AGENTS="cursor",
            MULTIAGENT_PANE_CURSOR=pane_id,
        )
        result = self._run_agent_send(
            "cursor",
            message="hello cursor trust",
            extra_env={"FAKE_TMUX_TRUST_PANES": pane_id},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn("hello cursor trust", self._pane_text(pane_id))
        entries = self._read_entries()
        self.assertEqual(entries[-1]["targets"], ["cursor"])

    def test_multi_target_delivers_to_each_agent_and_logs_fanout(self) -> None:
        self._write_tmux_session_env(
            MULTIAGENT_BIN_DIR=str(REPO_ROOT / "bin"),
            MULTIAGENT_WORKSPACE=str(self.workspace),
            MULTIAGENT_LOG_DIR=str(self.log_root),
            MULTIAGENT_AGENTS="claude,codex",
            MULTIAGENT_PANE_CLAUDE="pane-claude",
            MULTIAGENT_PANE_CODEX="pane-codex",
        )
        result = self._run_agent_send("claude,codex", message="hello everyone")
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        entries = self._read_entries()
        self.assertEqual(entries[-1]["targets"], ["claude", "codex"])
        self.assertIn("hello everyone", self._pane_text("pane-claude"))
        self.assertIn("hello everyone", self._pane_text("pane-codex"))

    def test_partial_success_logs_only_successful_targets(self) -> None:
        self._write_tmux_session_env(
            MULTIAGENT_BIN_DIR=str(REPO_ROOT / "bin"),
            MULTIAGENT_WORKSPACE=str(self.workspace),
            MULTIAGENT_LOG_DIR=str(self.log_root),
            MULTIAGENT_AGENTS="claude,codex",
            MULTIAGENT_PANE_CLAUDE="pane-claude",
            MULTIAGENT_PANE_CODEX="pane-codex",
        )
        result = self._run_agent_send(
            "claude,codex",
            message="hello partial",
            extra_env={"FAKE_TMUX_FAIL_PANES": "pane-codex"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Failed to deliver to: codex", result.stderr)
        entries = self._read_entries()
        self.assertEqual(entries[-1]["targets"], ["claude"])
        self.assertIn("hello partial", self._pane_text("pane-claude"))
        self.assertFalse((self.fake_tmux_dir / "pane_pane-codex.txt").exists())

    def test_invalid_target_fails_without_writing_index_entry(self) -> None:
        result = self._run_agent_send("not-an-agent", message="hello")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown target: not-an-agent", result.stderr)
        index_path = self.log_root / self.session_name / ".agent-index.jsonl"
        self.assertFalse(index_path.exists())

    def test_empty_message_body_is_rejected(self) -> None:
        result = self._run_agent_send("claude", message="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent-send: empty message body", result.stderr)


if __name__ == "__main__":
    unittest.main()
