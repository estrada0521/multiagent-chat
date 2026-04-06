from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index import hub_server


class HubSettingsTemplateTests(unittest.TestCase):
    """Regression tests for hub_settings_html after template extraction.

    The 1122-line f-string template inside hub_settings_html was moved to
    hub_settings_template.html with 23 __TOKEN__ placeholders that are
    substituted by a .replace() chain inside the function. These tests pin
    the rendering contract so the extraction does not drift.
    """

    @classmethod
    def setUpClass(cls) -> None:
        hub_server.initialize_from_argv([".", "bin/agent-index", "9999", "multiagent"])

    def test_render_basic_shape(self) -> None:
        out = hub_server.hub_settings_html()
        self.assertTrue(out.startswith("<!doctype html>"))
        self.assertTrue(out.rstrip().endswith("</html>"))
        self.assertIn("Hub Settings", out)

    def test_all_placeholders_are_substituted(self) -> None:
        out = hub_server.hub_settings_html()
        tokens = [
            "__HUB_THEME__",
            "__STARFIELD_ATTR__",
            "__HUB_MANIFEST_URL__",
            "__PWA_ICON_192_URL__",
            "__APPLE_TOUCH_ICON_URL__",
            "__THEME_HINT_HTML__",
            "__THEME_OPTIONS__",
            "__NOTICE_HTML__",
            "__USER_MESSAGE_FONT_OPTIONS__",
            "__AGENT_MESSAGE_FONT_OPTIONS__",
            "__FONT_MODE__",
            "__MESSAGE_LIMIT__",
            "__MESSAGE_TEXT_SIZE__",
            "__MESSAGE_MAX_WIDTH__",
            "__USER_MSG_OPACITY__",
            "__AGENT_MSG_OPACITY__",
            "__CHAT_AUTO_CHECKED__",
            "__CHAT_AWAKE_CHECKED__",
            "__CHAT_SOUND_CHECKED__",
            "__CHAT_BROWSER_NOTIF_CHECKED__",
            "__CHAT_TTS_CHECKED__",
            "__STARFIELD_CHECKED__",
            "__BOLD_MODE_MOBILE_CHECKED__",
            "__BOLD_MODE_DESKTOP_CHECKED__",
        ]
        for token in tokens:
            self.assertNotIn(token, out, f"unreplaced placeholder: {token}")

    def test_saved_notice_appears(self) -> None:
        out_quiet = hub_server.hub_settings_html(saved=False)
        out_saved = hub_server.hub_settings_html(saved=True)
        self.assertNotIn("Saved.", out_quiet)
        self.assertIn("Saved.", out_saved)

    def test_escape_sequences_preserved(self) -> None:
        """The template unescaping step must not corrupt literal Python escape
        sequences — particularly backslashes in JS regex literals and unicode
        characters like the horizontal ellipsis.
        """
        out = hub_server.hub_settings_html()
        # The JS regex `/\+/g` should survive as a single-backslash sequence.
        self.assertIn(r"replace(/\+/g,", out)
        # Ellipsis character should render as the actual character, not an
        # escape sequence.
        self.assertIn("Restarting\u2026", out)
        self.assertNotIn(r"Restarting\u2026", out)

    def test_settings_form_contains_theme_options(self) -> None:
        out = hub_server.hub_settings_html()
        # Theme <select> should have at least one <option> element.
        self.assertIn("<option value=", out)
        # The current theme should be rendered into the html[data-theme] attribute.
        self.assertRegex(out, r'data-theme="[^"]+"')


if __name__ == "__main__":
    unittest.main()
