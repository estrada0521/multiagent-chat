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
            "__HUB_MANIFEST_URL__",
            "__PWA_ICON_192_URL__",
            "__APPLE_TOUCH_ICON_URL__",
            "__NOTICE_HTML__",
            "__USER_MESSAGE_FONT_OPTIONS__",
            "__AGENT_MESSAGE_FONT_OPTIONS__",
            "__FONT_MODE__",
            "__MESSAGE_TEXT_SIZE__",
            "__CHAT_AUTO_CHECKED__",
            "__CHAT_AWAKE_CHECKED__",
            "__CHAT_SOUND_CHECKED__",
            "__CHAT_BROWSER_NOTIF_CHECKED__",
            "__BOLD_MODE_MOBILE_CHECKED__",
            "__BOLD_MODE_DESKTOP_CHECKED__",
            "__VIEW_VARIANT__",
        ]
        for token in tokens:
            self.assertNotIn(token, out, f"unreplaced placeholder: {token}")

    def test_saved_notice_is_suppressed(self) -> None:
        out_quiet = hub_server.hub_settings_html(saved=False)
        out_saved = hub_server.hub_settings_html(saved=True)
        self.assertNotIn("Saved.", out_quiet)
        self.assertNotIn("Saved.", out_saved)

    def test_escape_sequences_preserved(self) -> None:
        """The template unescaping step must not corrupt literal Python escape
        sequences — particularly JS template literals and unicode characters
        like the horizontal ellipsis.
        """
        out = hub_server.hub_settings_html()
        self.assertIn("fetch(`/sessions?ts=${Date.now()}`", out)
        # Ellipsis character should render as the actual character, not an
        # escape sequence.
        self.assertIn("Restarting\u2026", out)
        self.assertNotIn(r"Restarting\u2026", out)

    def test_settings_form_is_fixed_to_black_hole(self) -> None:
        out = hub_server.hub_settings_html()
        self.assertIn('data-theme="black-hole"', out)
        self.assertNotIn('id="theme"', out)
        self.assertNotIn("Default Message Count", out)
        self.assertNotIn("Message Max Width (px)", out)
        self.assertNotIn("Read aloud (TTS)", out)
        self.assertNotIn("Starfield background", out)
        self.assertNotIn("Black Hole Text Opacity", out)

    def test_settings_page_keeps_header_and_app_scripts(self) -> None:
        out = hub_server.hub_settings_html()
        self.assertIn('menuPanel.classList.toggle("open");', out)
        self.assertIn("const installAppBtn = document.getElementById('installAppBtn');", out)
        self.assertIn("const chatSoundToggle = document.querySelector('input[name=\"chat_sound\"]');", out)
        self.assertNotIn('id="gitBranchMenuBtn"', out)
        self.assertNotIn("openGitBranchMenu", out)
        self.assertNotIn('/resume"', out)
        self.assertNotIn('/stats"', out)
        self.assertNotIn('/crons"', out)

    def test_settings_copy_is_compact_for_sidebar_style(self) -> None:
        out = hub_server.hub_settings_html()
        self.assertNotIn("Applied when a chat opens. Toggling from chat UI is disabled.", out)
        self.assertNotIn(
            "Install Hub to the Home Screen, then allow browser notifications here. "
            "Hub will be the single notification endpoint for all sessions.",
            out,
        )
        self.assertNotIn('<div class="label">Chat Fonts</div>', out)
        self.assertNotIn('<div class="label">Visual Defaults</div>', out)
        self.assertNotIn("Bold mode — smartphone (narrow viewport, max 480px)", out)
        self.assertNotIn("Bold mode — desktop / wide (min 481px)", out)
        self.assertIn("Bold mode (mobile)", out)
        self.assertIn("Bold mode (desktop)", out)
        self.assertIn(".app-status-stack { display: none; }", out)
        self.assertNotIn("Already running as an installed app.", out)
        self.assertNotIn("Enabled. Save Settings to keep this on.", out)

    def test_embed_mode_keeps_sidebar_gutters(self) -> None:
        out = hub_server.hub_settings_html()
        self.assertIn('html[data-hub-embed="1"] .shell > :not(.hub-page-header) {', out)
        self.assertIn("padding-left: 10px;", out)
        self.assertIn("padding-right: 10px;", out)

    def test_settings_desktop_and_mobile_css_split_exists(self) -> None:
        out = hub_server.hub_settings_html(variant="mobile")
        self.assertIn('html[data-view-variant="mobile"]:not([data-hub-embed="1"]) .toggle-row {', out)
        self.assertIn('html[data-view-variant="mobile"]:not([data-hub-embed="1"]) .row {', out)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", out)
        self.assertIn("font-size: 15px;", out)
        desktop = hub_server.hub_settings_html(variant="desktop")
        self.assertIn('html[data-view-variant="desktop"]:not([data-hub-embed="1"]) .hub-page-header {', desktop)
        self.assertIn('html[data-view-variant="desktop"] #app-controls {', desktop)
        self.assertNotIn("__VIEW_VARIANT__", desktop)

    def test_embed_detection_supports_hub_launch_shell_target(self) -> None:
        out = hub_server.hub_settings_html()
        self.assertIn('const rawTarget = (params.get("target") || "").trim();', out)
        self.assertIn('embed = (next.searchParams.get("embed") || "") === "1";', out)

    def test_settings_font_selectors_are_stacked(self) -> None:
        out = hub_server.hub_settings_html()
        self.assertIn(".row {", out)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", out)
        self.assertNotIn("Chat Defaults", out)

    def test_save_button_uses_hub_top_style(self) -> None:
        out = hub_server.hub_settings_html()
        self.assertIn('<button class="save" type="submit">', out)
        self.assertIn('<svg viewBox="0 0 24 24" aria-hidden="true">', out)
        self.assertIn("justify-content: flex-start;", out)
        self.assertIn("text-align: left;", out)
        self.assertIn(".save:hover {", out)
        self.assertIn("border-radius: 999px;", out)
        self.assertIn("background: rgba(255,255,255,0.06);", out)
        self.assertIn("transition: background 140ms ease, border-color 140ms ease, color 140ms ease;", out)

    def test_save_submit_closes_page(self) -> None:
        out = hub_server.hub_settings_html()
        self.assertIn("const closeSettingsPage = () => {", out)
        self.assertIn('type: "multiagent-hub-close-sidebar-page"', out)
        self.assertIn("window.history.back();", out)
        self.assertIn('window.location.href = "/";', out)
        self.assertIn("settingsForm.addEventListener(\"submit\", async (event) => {", out)


if __name__ == "__main__":
    unittest.main()
