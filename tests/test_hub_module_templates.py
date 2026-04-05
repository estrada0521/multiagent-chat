from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index import hub_server


class HubModuleTemplateTests(unittest.TestCase):
    """Regression tests for the three module-level HTML templates that were
    extracted out of hub_server.py string literals:

      * HUB_APP_HTML           (1421 lines -> hub_app_template.html)
      * HUB_HOME_HTML          ( 991 lines -> hub_home_template.html)
      * HUB_NEW_SESSION_HTML   ( 673 lines -> hub_new_session_template.html)

    HUB_APP_HTML is additionally reused as the base for HUB_RESUME_HTML and
    HUB_STATS_HTML. These tests pin shape and substitution behavior.
    """

    @classmethod
    def setUpClass(cls) -> None:
        hub_server.initialize_from_argv([".", "bin/agent-index", "9999", "multiagent"])

    def test_all_templates_start_and_end_correctly(self) -> None:
        for name in (
            "HUB_APP_HTML",
            "HUB_HOME_HTML",
            "HUB_NEW_SESSION_HTML",
            "HUB_RESUME_HTML",
            "HUB_STATS_HTML",
        ):
            val = getattr(hub_server, name)
            self.assertTrue(val.startswith("<!doctype html>"), f"{name} doctype")
            self.assertTrue(val.rstrip().endswith("</html>"), f"{name} closing")

    def test_hub_app_html_keeps_render_time_placeholders(self) -> None:
        # HUB_APP_HTML is substituted at render time (per-session) — these
        # tokens MUST remain present in the module-level constant.
        val = hub_server.HUB_APP_HTML
        for token in (
            "__HUB_MANIFEST_URL__",
            "__HUB_HEADER_CSS__",
            "__HUB_HEADER_HTML__",
            "__HUB_HEADER_JS__",
        ):
            self.assertIn(token, val, f"missing render-time token: {token}")
        # But the module-level substitutions should be resolved.
        self.assertNotIn("__ALL_AGENT_NAMES_JS__", val)
        self.assertNotIn("__SELECTABLE_AGENT_NAMES_JS__", val)

    def test_hub_home_html_resolves_module_tokens(self) -> None:
        val = hub_server.HUB_HOME_HTML
        for token in (
            "__HUB_MANIFEST_URL__",
            "__HUB_HEADER_CSS__",
            "__HUB_HEADER_HTML__",
            "__HUB_HEADER_JS__",
        ):
            self.assertNotIn(token, val, f"unresolved token: {token}")

    def test_hub_new_session_html_resolves_all_icons(self) -> None:
        val = hub_server.HUB_NEW_SESSION_HTML
        for token in (
            "__CLAUDE_ICON__",
            "__CODEX_ICON__",
            "__GEMINI_ICON__",
            "__KIMI_ICON__",
            "__COPILOT_ICON__",
            "__CURSOR_ICON__",
            "__GROK_ICON__",
            "__OPENCODE_ICON__",
            "__QWEN_ICON__",
            "__AIDER_ICON__",
            "__NEW_SESSION_MAX_PER_AGENT__",
            "__HUB_MANIFEST_URL__",
            "__HUB_HEADER_CSS__",
        ):
            self.assertNotIn(token, val, f"unresolved token: {token}")

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
