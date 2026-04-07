from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index.chat_sync_loop_core import sync_agent_assistant_messages


def _cp(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class _RuntimeStub:
    def __init__(self) -> None:
        self.tmux_prefix = ["tmux"]
        self.session_name = "sample"
        self._pane_native_log_paths: dict[str, tuple[str, str]] = {}
        self.calls: list[tuple] = []

    def _sync_claude_assistant_messages(self, agent: str, native_log_path: str | None = None, *, workspace_hint: str | None = None) -> None:
        self.calls.append(("claude", agent, native_log_path, workspace_hint))

    def _sync_codex_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
        self.calls.append(("codex", agent, native_log_path))

    def _sync_opencode_assistant_messages(self, agent: str) -> None:
        self.calls.append(("opencode", agent))


class ChatSyncLoopCoreTests(unittest.TestCase):
    def test_claude_falls_back_to_workspace_hint_only(self) -> None:
        runtime = _RuntimeStub()
        with patch("agent_index.chat_sync_loop_core.subprocess.run", return_value=_cp(returncode=1)):
            sync_agent_assistant_messages(runtime, "claude-1")
        self.assertEqual(runtime.calls, [("claude", "claude-1", None, "")])

    def test_codex_no_pane_id_does_not_call_sync(self) -> None:
        runtime = _RuntimeStub()
        with patch("agent_index.chat_sync_loop_core.subprocess.run", return_value=_cp(returncode=1)):
            sync_agent_assistant_messages(runtime, "codex-1")
        self.assertEqual(runtime.calls, [])

    def test_opencode_calls_direct_sync(self) -> None:
        runtime = _RuntimeStub()
        sync_agent_assistant_messages(runtime, "opencode-1")
        self.assertEqual(runtime.calls, [("opencode", "opencode-1")])

    def test_codex_uses_cached_native_log_path(self) -> None:
        runtime = _RuntimeStub()
        runtime._pane_native_log_paths["%11"] = ("1234", "/tmp/codex-rollout.jsonl")
        run_calls = [
            _cp(stdout="MULTIAGENT_PANE_CODEX_1=%11\n"),
            _cp(stdout="1234\n"),
        ]
        with patch("agent_index.chat_sync_loop_core.subprocess.run", side_effect=run_calls):
            with patch("agent_index.chat_sync_loop_core.os.path.exists", return_value=True):
                sync_agent_assistant_messages(runtime, "codex-1")
        self.assertEqual(runtime.calls, [("codex", "codex-1", "/tmp/codex-rollout.jsonl")])


if __name__ == "__main__":
    unittest.main()
