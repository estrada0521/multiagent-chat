from __future__ import annotations

import unittest
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index.multiagent_tmux_core import (
    parse_pane_ids,
    retile_session_preserving_user_panes,
    tmux_prefix_args,
)


class MultiagentTmuxCoreTests(unittest.TestCase):
    def test_tmux_prefix_args(self) -> None:
        self.assertEqual(tmux_prefix_args("demo-sock"), ["tmux", "-L", "demo-sock"])
        self.assertEqual(tmux_prefix_args("/tmp/tmux.sock"), ["tmux", "-S", "/tmp/tmux.sock"])

    def test_parse_pane_ids(self) -> None:
        self.assertEqual(parse_pane_ids(""), [])
        self.assertEqual(parse_pane_ids("%1,%2"), ["%1", "%2"])
        self.assertEqual(parse_pane_ids(" %1, ,%3 "), ["%1", "%3"])

    @patch("agent_index.multiagent_tmux_core.subprocess.run")
    def test_retile_session_preserving_user_panes_invokes_tmux(self, run_mock) -> None:
        retile_session_preserving_user_panes(
            session="demo",
            user_panes_csv="%11,%12",
            tmux_socket="demo-sock",
        )
        calls = [call.args[0] for call in run_mock.call_args_list]
        self.assertEqual(calls[0], ["tmux", "-L", "demo-sock", "select-layout", "-t", "demo:0", "tiled"])
        self.assertEqual(calls[1], ["tmux", "-L", "demo-sock", "resize-pane", "-t", "%11", "-y", "2"])
        self.assertEqual(calls[2], ["tmux", "-L", "demo-sock", "resize-pane", "-t", "%12", "-y", "2"])


if __name__ == "__main__":
    unittest.main()
