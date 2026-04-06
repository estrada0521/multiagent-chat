from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index.chat_pane_trace_core import build_pane_trace_view_model


class ChatPaneTraceCoreTests(unittest.TestCase):
    def test_build_pane_trace_view_model_defaults(self) -> None:
        model = build_pane_trace_view_model(
            agent="",
            agents=None,
            bg="",
            text="",
            chat_base_path="/session/demo/",
        )
        self.assertEqual(model["base_path"], "/session/demo")
        self.assertEqual(model["bg_value"], "rgb(10, 10, 10)")
        self.assertEqual(model["text_value"], "rgb(252, 252, 252)")
        self.assertEqual(model["all_agents"], [])
        self.assertEqual(model["initial_agent"], "")
        self.assertEqual(model["trace_path_prefix"], "/session/demo")

    def test_build_pane_trace_view_model_with_agents_and_rgb_text(self) -> None:
        model = build_pane_trace_view_model(
            agent="codex",
            agents=["claude", "codex"],
            bg="rgb(1,2,3)",
            text="rgb(250, 250, 250)",
            chat_base_path="",
        )
        self.assertEqual(model["all_agents"], ["claude", "codex"])
        self.assertEqual(model["initial_agent"], "codex")
        self.assertEqual(model["bg_value"], "rgb(1,2,3)")
        self.assertEqual(model["body_fg"], "rgba(250, 250, 250, 0.78)")
        self.assertEqual(model["body_dim_fg"], "rgba(250, 250, 250, 0.38)")
        self.assertEqual(model["trace_path_prefix"], "")

    def test_build_pane_trace_view_model_non_rgb_text_falls_back(self) -> None:
        model = build_pane_trace_view_model(
            agent="gemini",
            agents=None,
            bg="rgb(1,2,3)",
            text="#eee",
            chat_base_path="",
        )
        self.assertEqual(model["all_agents"], ["gemini"])
        self.assertEqual(model["initial_agent"], "gemini")
        self.assertEqual(model["body_fg"], "#eee")
        self.assertEqual(model["body_dim_fg"], "#eee")


if __name__ == "__main__":
    unittest.main()
