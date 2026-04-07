from __future__ import annotations

import unittest
from unittest.mock import patch
import subprocess

import _bootstrap  # noqa: F401
from agent_index.multiagent_tmux_core import (
    configure_agent_pane_defaults,
    configure_window_size,
    create_user_pane_band,
    create_agent_window,
    kill_pane_target,
    kill_window_target,
    parse_pane_ids,
    retile_session_preserving_user_panes,
    split_agent_pane,
    tmux_prefix_args,
    window_target_for_pane,
)


class MultiagentTmuxCoreTests(unittest.TestCase):
    @staticmethod
    def _cp(args: list[str], *, rc: int = 0, out: str = "") -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=args, returncode=rc, stdout=out, stderr="")

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

    @patch("agent_index.multiagent_tmux_core.subprocess.run")
    def test_window_target_for_pane(self, run_mock) -> None:
        run_mock.return_value = self._cp([], out="@42\n")
        self.assertEqual(
            window_target_for_pane(pane_id="%11", tmux_socket="demo-sock"),
            "@42",
        )
        run_mock.assert_called_once_with(
            ["tmux", "-L", "demo-sock", "display-message", "-p", "-t", "%11", "#{window_id}"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("agent_index.multiagent_tmux_core.subprocess.run")
    def test_window_target_for_pane_returns_empty_on_failure(self, run_mock) -> None:
        run_mock.return_value = self._cp([], rc=1, out="")
        self.assertEqual(window_target_for_pane(pane_id="%11", tmux_socket="demo-sock"), "")

    @patch("agent_index.multiagent_tmux_core.subprocess.run")
    def test_configure_window_size(self, run_mock) -> None:
        configure_window_size(target="@5", width=140, height=80, tmux_socket="demo-sock")
        calls = [call.args[0] for call in run_mock.call_args_list]
        self.assertEqual(calls[0], ["tmux", "-L", "demo-sock", "set-window-option", "-t", "@5", "window-size", "manual"])
        self.assertEqual(calls[1], ["tmux", "-L", "demo-sock", "resize-window", "-t", "@5", "-x", "140", "-y", "80"])

    @patch("agent_index.multiagent_tmux_core.subprocess.run")
    def test_create_agent_window_success(self, run_mock) -> None:
        run_mock.side_effect = [
            self._cp([], out="%201\n"),
            self._cp([], out="@9\n"),
            self._cp([]),
            self._cp([]),
        ]
        pane = create_agent_window(
            session="demo",
            instance_name="claude-2",
            workspace="/tmp/ws",
            width=66,
            height=60,
            tmux_socket="demo-sock",
        )
        self.assertEqual(pane, "%201")
        calls = [call.args[0] for call in run_mock.call_args_list]
        self.assertEqual(
            calls[0],
            ["tmux", "-L", "demo-sock", "new-window", "-d", "-P", "-F", "#{pane_id}", "-t", "demo:", "-n", "claude-2", "-c", "/tmp/ws"],
        )
        self.assertEqual(calls[1], ["tmux", "-L", "demo-sock", "display-message", "-p", "-t", "%201", "#{window_id}"])
        self.assertEqual(calls[2], ["tmux", "-L", "demo-sock", "set-window-option", "-t", "@9", "window-size", "manual"])
        self.assertEqual(calls[3], ["tmux", "-L", "demo-sock", "resize-window", "-t", "@9", "-x", "66", "-y", "60"])

    @patch("agent_index.multiagent_tmux_core.subprocess.run")
    def test_split_agent_pane(self, run_mock) -> None:
        run_mock.return_value = self._cp([], out="%210\n")
        self.assertEqual(
            split_agent_pane(target_pane="%100", workspace="/tmp/ws", tmux_socket="demo-sock"),
            "%210",
        )
        run_mock.assert_called_once_with(
            ["tmux", "-L", "demo-sock", "split-window", "-h", "-P", "-F", "#{pane_id}", "-t", "%100", "-c", "/tmp/ws"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("agent_index.multiagent_tmux_core.subprocess.run")
    def test_create_user_pane_band_top(self, run_mock) -> None:
        run_mock.side_effect = [
            self._cp([], out="%300\n"),
            self._cp([], out="%301\n"),
            self._cp([], out="%302\n"),
        ]
        self.assertEqual(
            create_user_pane_band(
                target="%10",
                side="top",
                count=3,
                pane_height=2,
                workspace="/tmp/ws",
                tmux_socket="demo-sock",
            ),
            ["%300", "%301", "%302"],
        )
        calls = [call.args[0] for call in run_mock.call_args_list]
        self.assertEqual(
            calls[0],
            [
                "tmux",
                "-L",
                "demo-sock",
                "split-window",
                "-v",
                "-b",
                "-l",
                "2",
                "-P",
                "-F",
                "#{pane_id}",
                "-t",
                "%10",
                "-c",
                "/tmp/ws",
            ],
        )
        self.assertEqual(
            calls[1],
            [
                "tmux",
                "-L",
                "demo-sock",
                "split-window",
                "-h",
                "-b",
                "-p",
                "33",
                "-P",
                "-F",
                "#{pane_id}",
                "-t",
                "%300",
                "-c",
                "/tmp/ws",
            ],
        )
        self.assertEqual(
            calls[2],
            [
                "tmux",
                "-L",
                "demo-sock",
                "split-window",
                "-h",
                "-b",
                "-p",
                "50",
                "-P",
                "-F",
                "#{pane_id}",
                "-t",
                "%300",
                "-c",
                "/tmp/ws",
            ],
        )

    @patch("agent_index.multiagent_tmux_core.subprocess.run")
    def test_create_user_pane_band_bottom_and_validation(self, run_mock) -> None:
        run_mock.side_effect = [self._cp([], out="%400\n")]
        self.assertEqual(
            create_user_pane_band(
                target="%10",
                side="bottom",
                count=1,
                pane_height=1,
                workspace="/tmp/ws",
                tmux_socket="demo-sock",
            ),
            ["%400"],
        )
        self.assertEqual(
            run_mock.call_args_list[0].args[0],
            [
                "tmux",
                "-L",
                "demo-sock",
                "split-window",
                "-v",
                "-l",
                "1",
                "-P",
                "-F",
                "#{pane_id}",
                "-t",
                "%10",
                "-c",
                "/tmp/ws",
            ],
        )
        with self.assertRaises(ValueError):
            create_user_pane_band(
                target="%10",
                side="invalid",
                count=2,
                pane_height=1,
                workspace="/tmp/ws",
                tmux_socket="demo-sock",
            )

    @patch("agent_index.multiagent_tmux_core.subprocess.run")
    def test_configure_agent_pane_defaults(self, run_mock) -> None:
        configure_agent_pane_defaults(pane_id="%77", tmux_socket="demo-sock")
        calls = [call.args[0] for call in run_mock.call_args_list]
        self.assertEqual(calls[0], ["tmux", "-L", "demo-sock", "set-option", "-pt", "%77", "remain-on-exit", "on"])
        self.assertEqual(calls[1], ["tmux", "-L", "demo-sock", "set-option", "-pt", "%77", "mouse", "on"])

    @patch("agent_index.multiagent_tmux_core.subprocess.run")
    def test_kill_targets(self, run_mock) -> None:
        run_mock.side_effect = [self._cp([]), self._cp([], rc=1), self._cp([]), self._cp([], rc=1)]
        self.assertTrue(kill_window_target(window_target="@4", tmux_socket="demo-sock"))
        self.assertFalse(kill_window_target(window_target="@5", tmux_socket="demo-sock"))
        self.assertTrue(kill_pane_target(pane_id="%12", tmux_socket="demo-sock"))
        self.assertFalse(kill_pane_target(pane_id="%13", tmux_socket="demo-sock"))


if __name__ == "__main__":
    unittest.main()
