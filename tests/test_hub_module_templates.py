from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index import hub_server


class HubModuleTemplateTests(unittest.TestCase):
    """Regression tests for the Hub module-level HTML templates."""

    @classmethod
    def setUpClass(cls) -> None:
        hub_server.initialize_from_argv([".", "bin/agent-index", "9999", "multiagent"])

    def test_all_templates_start_and_end_correctly(self) -> None:
        for name in (
            "HUB_HOME_HTML",
            "HUB_NEW_SESSION_HTML",
        ):
            val = getattr(hub_server, name)
            self.assertTrue(val.startswith("<!doctype html>"), f"{name} doctype")
            self.assertTrue(val.rstrip().endswith("</html>"), f"{name} closing")

    def test_hub_home_html_resolves_module_tokens(self) -> None:
        val = hub_server.HUB_HOME_HTML
        for token in (
            "__HUB_MANIFEST_URL__",
            "__HUB_HEADER_CSS__",
            "__HUB_HEADER_HTML__",
            "__HUB_HEADER_JS__",
            "__CLAUDE_ICON__",
            "__CODEX_ICON__",
            "__GEMINI_ICON__",
        ):
            self.assertNotIn(token, val, f"unresolved token: {token}")
        self.assertIn('menuPanel.classList.toggle("open");', val)
        self.assertIn('id="deskNewSessionToggle"', val)
        self.assertIn('id="deskLauncherBtn"', val)
        self.assertIn('id="deskReloadBtn"', val)
        self.assertIn('id="deskSidebarResizer"', val)
        self.assertIn("function renderAgentIconStrip(agents) {", val)
        self.assertIn("async function startDeskNewSessionFlow() {", val)
        self.assertIn("function scheduleDeskActivePrewarm() {", val)
        self.assertIn('data-desk-swipe-action="', val)
        self.assertNotIn("function renderRows(", val)
        self.assertNotIn('id="chatOverlay"', val)
        self.assertNotIn('/resume"', val)
        self.assertNotIn('/stats"', val)
        self.assertNotIn('/crons"', val)

    def test_hub_new_session_html_resolves_all_icons(self) -> None:
        val = hub_server.HUB_NEW_SESSION_HTML
        for token in (
            "__HUB_MANIFEST_URL__",
            "__HUB_HEADER_CSS__",
        ):
            self.assertNotIn(token, val, f"unresolved token: {token}")
        self.assertIn('const pickBtn = document.getElementById("pickBtn");', val)
        self.assertIn('/pick-workspace', val)
        self.assertIn('/start-session-draft', val)
        self.assertIn('Choose in Finder', val)
        self.assertIn('menuPanel.classList.toggle("open");', val)
        self.assertNotIn('class="agent-card', val)
        self.assertNotIn('session-name', val)
        self.assertNotIn('/resume"', val)
        self.assertNotIn('/stats"', val)

    def test_escape_sequences_preserved_in_templates(self) -> None:
        # These unicode characters (middle dot, em dash, ellipsis) were
        # written in the original Python source as \u00b7, \u2014, \u2026.
        # After extraction they must be real characters, not escape strings.
        new_session = hub_server.HUB_NEW_SESSION_HTML
        self.assertIn("New Session \u00b7 Hub", new_session)
        self.assertIn("Starting\u2026", new_session)
        self.assertNotIn(r"\u00b7", new_session)
        self.assertNotIn(r"\u2026", new_session)


if __name__ == "__main__":
    unittest.main()
