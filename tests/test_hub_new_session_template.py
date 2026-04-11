from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index import hub_server


class HubNewSessionTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        hub_server.initialize_from_argv([".", "bin/agent-index", "9999", "multiagent"])

    def test_new_session_desktop_and_mobile_css_split_exists(self) -> None:
        out = hub_server.hub_new_session_html(variant="mobile")
        self.assertIn('html[data-view-variant="mobile"]:not([data-hub-embed="1"]) .title {', out)
        self.assertIn("font-size: 28px;", out)
        self.assertIn('html[data-view-variant="mobile"]:not([data-hub-embed="1"]) .pick-btn {', out)
        self.assertIn("font-size: 17px;", out)
        desktop = hub_server.hub_new_session_html(variant="desktop")
        self.assertIn('html[data-view-variant="desktop"]:not([data-hub-embed="1"]) .hub-page-header {', desktop)
        self.assertNotIn("__VIEW_VARIANT__", desktop)

    def test_embed_detection_supports_hub_launch_shell_target(self) -> None:
        out = hub_server.hub_new_session_html()
        self.assertIn('const rawTarget = (params.get("target") || "").trim();', out)
        self.assertIn('embed = (next.searchParams.get("embed") || "") === "1";', out)


if __name__ == "__main__":
    unittest.main()
