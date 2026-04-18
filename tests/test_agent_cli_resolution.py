from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index.chat_agent_lifecycle_core import resolve_agent_executable as resolve_runtime_executable
from agent_index.ensure_agent_clis import resolve_agent_executable as resolve_readiness_executable


class AgentCliResolutionTests(unittest.TestCase):
    @patch("agent_index.chat_agent_lifecycle_core.shutil.which", return_value="/tmp/codex")
    def test_runtime_resolution_uses_path_hit(self, mock_which) -> None:
        self.assertEqual(resolve_runtime_executable("codex"), "/tmp/codex")
        mock_which.assert_called_once_with("codex")

    @patch("agent_index.chat_agent_lifecycle_core.shutil.which", return_value=None)
    def test_runtime_resolution_uses_standard_install_location(self, mock_which) -> None:
        self.assertEqual(resolve_runtime_executable("cursor"), "/Users/okadaharuto/.local/bin/agent")
        self.assertEqual(mock_which.call_args_list, [unittest.mock.call("agent"), unittest.mock.call("cursor-agent")])

    @patch("agent_index.ensure_agent_clis.shutil.which", return_value="/tmp/copilot")
    def test_readiness_resolution_uses_path_hit(self, mock_which) -> None:
        self.assertEqual(resolve_readiness_executable(_bootstrap.REPO_ROOT, "copilot"), "/tmp/copilot")
        mock_which.assert_called_once_with("copilot")

    @patch("agent_index.ensure_agent_clis.shutil.which", return_value=None)
    def test_readiness_resolution_uses_standard_install_location_when_path_misses(self, mock_which) -> None:
        self.assertEqual(
            resolve_readiness_executable(_bootstrap.REPO_ROOT, "cursor"),
            "/Users/okadaharuto/.local/bin/agent",
        )
        self.assertEqual(mock_which.call_args_list, [unittest.mock.call("agent"), unittest.mock.call("cursor-agent")])

    def test_readiness_resolution_uses_standard_install_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            fallback = home / ".local" / "bin" / "claude"
            fallback.parent.mkdir(parents=True, exist_ok=True)
            fallback.write_text("", encoding="utf-8")
            fallback.chmod(0o755)
            with (
                patch("agent_index.ensure_agent_clis.shutil.which", return_value=None),
                patch.dict(os.environ, {"HOME": str(home)}, clear=False),
            ):
                self.assertEqual(
                    resolve_readiness_executable(_bootstrap.REPO_ROOT, "claude"),
                    str(fallback),
                )

    def test_readiness_resolution_uses_nvm_install_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            nvm_bin = home / ".nvm" / "versions" / "node" / "v1.2.3" / "bin"
            copilot = nvm_bin / "copilot"
            nvm_bin.mkdir(parents=True, exist_ok=True)
            copilot.write_text("", encoding="utf-8")
            copilot.chmod(0o755)
            with (
                patch("agent_index.ensure_agent_clis.shutil.which", return_value=None),
                patch.dict(os.environ, {"HOME": str(home), "NVM_BIN": ""}, clear=False),
            ):
                self.assertEqual(
                    resolve_readiness_executable(_bootstrap.REPO_ROOT, "copilot"),
                    str(copilot),
                )


if __name__ == "__main__":
    unittest.main()
