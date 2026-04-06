from __future__ import annotations

import signal
import unittest
from unittest.mock import call, patch

import _bootstrap  # noqa: F401
from agent_index.multiagent_session_core import session_context_from_env_output, stop_session_chat_server


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

    def test_stop_session_chat_server_without_session_name(self) -> None:
        ok, detail = stop_session_chat_server("/tmp/repo", "")
        self.assertFalse(ok)
        self.assertEqual(detail, "session_name is required")

    @patch("agent_index.multiagent_session_core.chat_server_listener_pids", return_value=[])
    @patch("agent_index.multiagent_session_core.resolve_chat_port", return_value=8123)
    def test_stop_session_chat_server_returns_ok_when_listener_missing(
        self,
        _mock_port: object,
        _mock_listeners: object,
    ) -> None:
        ok, detail = stop_session_chat_server("/tmp/repo", "demo")
        self.assertTrue(ok)
        self.assertEqual(detail, "")

    @patch("agent_index.multiagent_session_core._wait_for_chat_port_close", return_value=True)
    @patch("agent_index.multiagent_session_core._send_signal")
    @patch("agent_index.multiagent_session_core.chat_server_listener_pids", return_value=[101, 202])
    @patch("agent_index.multiagent_session_core.resolve_chat_port", return_value=8124)
    def test_stop_session_chat_server_stops_on_sigterm_success(
        self,
        _mock_port: object,
        _mock_listeners: object,
        mock_send_signal: object,
        _mock_wait: object,
    ) -> None:
        ok, detail = stop_session_chat_server("/tmp/repo", "demo")
        self.assertTrue(ok)
        self.assertEqual(detail, "")
        self.assertEqual(
            mock_send_signal.call_args_list,
            [call([101, 202], signal.SIGTERM)],
        )

    @patch("agent_index.multiagent_session_core._wait_for_chat_port_close", side_effect=[False, False])
    @patch("agent_index.multiagent_session_core._send_signal")
    @patch("agent_index.multiagent_session_core.chat_server_listener_pids", return_value=[303])
    @patch("agent_index.multiagent_session_core.resolve_chat_port", return_value=8125)
    def test_stop_session_chat_server_reports_failure_after_sigkill(
        self,
        _mock_port: object,
        _mock_listeners: object,
        mock_send_signal: object,
        _mock_wait: object,
    ) -> None:
        ok, detail = stop_session_chat_server("/tmp/repo", "demo")
        self.assertFalse(ok)
        self.assertEqual(detail, "chat server on port 8125 still running after SIGKILL")
        self.assertEqual(
            mock_send_signal.call_args_list,
            [call([303], signal.SIGTERM), call([303], signal.SIGKILL)],
        )


if __name__ == "__main__":
    unittest.main()
