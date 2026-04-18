from __future__ import annotations

import unittest
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
    def test_runtime_resolution_no_longer_uses_fallbacks(self, mock_which) -> None:
        self.assertEqual(resolve_runtime_executable("cursor"), "agent")
        mock_which.assert_called_once_with("agent")

    @patch("agent_index.ensure_agent_clis.shutil.which", return_value="/tmp/copilot")
    def test_readiness_resolution_uses_path_hit(self, mock_which) -> None:
        self.assertEqual(resolve_readiness_executable(_bootstrap.REPO_ROOT, "copilot"), "/tmp/copilot")
        mock_which.assert_called_once_with("copilot")

    @patch("agent_index.ensure_agent_clis.shutil.which", return_value=None)
    def test_readiness_resolution_returns_none_without_path_hit(self, mock_which) -> None:
        self.assertIsNone(resolve_readiness_executable(_bootstrap.REPO_ROOT, "cursor"))
        mock_which.assert_called_once_with("agent")


if __name__ == "__main__":
    unittest.main()
