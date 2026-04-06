from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index.multiagent_session_core import session_context_from_env_output


class MultiagentSessionCoreTests(unittest.TestCase):
    def test_session_context_from_env_output_extracts_values(self) -> None:
        context = session_context_from_env_output(
            "\n".join(
                [
                    "MULTIAGENT_WORKSPACE=/tmp/demo",
                    "MULTIAGENT_BIN_DIR=/tmp/bin",
                    "MULTIAGENT_TMUX_SOCKET=demo-sock",
                    "MULTIAGENT_LOG_DIR=/tmp/logs",
                ]
            )
        )
        self.assertEqual(context["workspace"], "/tmp/demo")
        self.assertEqual(context["bin_dir"], "/tmp/bin")
        self.assertEqual(context["tmux_socket"], "demo-sock")
        self.assertEqual(context["log_dir"], "/tmp/logs")

    def test_session_context_from_env_output_cleans_unset_values(self) -> None:
        context = session_context_from_env_output(
            "\n".join(
                [
                    "MULTIAGENT_WORKSPACE=-",
                    "MULTIAGENT_BIN_DIR=",
                    "-MULTIAGENT_TMUX_SOCKET",
                    "UNRELATED=1",
                ]
            )
        )
        self.assertEqual(context["workspace"], "")
        self.assertEqual(context["bin_dir"], "")
        self.assertEqual(context["tmux_socket"], "")
        self.assertEqual(context["log_dir"], "")


if __name__ == "__main__":
    unittest.main()
