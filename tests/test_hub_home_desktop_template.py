from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index import hub_server


class HubHomeDesktopTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        hub_server.initialize_from_argv([".", "bin/agent-index", "9999", "multiagent"])

    def test_settings_sidebar_uses_launch_shell(self) -> None:
        out = hub_server.HUB_HOME_DESKTOP_HTML
        self.assertIn(
            'if (mode === "settings") return `/hub-launch-shell.html?target=${encodeURIComponent("/settings?embed=1")}`;',
            out,
        )

    def test_settings_sidebar_keeps_loaded_iframe(self) -> None:
        out = hub_server.HUB_HOME_DESKTOP_HTML
        self.assertIn("const settingsUrl = deskSidebarPageUrl(\"settings\");", out)
        self.assertIn("if (!currentUrl || currentUrl !== nextUrl) {", out)
        self.assertNotIn('_deskSidebarFrame.src = "about:blank";', out)


if __name__ == "__main__":
    unittest.main()
