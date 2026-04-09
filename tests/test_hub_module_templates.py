from __future__ import annotations

import unittest
from pathlib import Path

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
        desktop = hub_server.HUB_HOME_DESKTOP_HTML
        mobile = hub_server.HUB_HOME_MOBILE_HTML
        for val in (desktop, mobile):
            for token in (
                "__HUB_MANIFEST_URL__",
                "__HUB_HEADER_CSS__",
                "__HUB_HEADER_HTML__",
                "__HUB_HEADER_JS__",
            ):
                self.assertNotIn(token, val, f"unresolved token: {token}")
            self.assertNotIn('/resume"', val)
            self.assertNotIn('/stats"', val)
            self.assertNotIn('/crons"', val)
        self.assertIn('menuPanel.classList.toggle("open");', desktop)
        self.assertIn('menuPanel.classList.toggle("open");', mobile)
        self.assertIn("desk-sidebar", desktop)
        self.assertIn("desk-main", desktop)
        self.assertNotIn("#chatOverlay.overlay-visible {", desktop)
        self.assertIn("#chatOverlay {", mobile)
        self.assertIn("z-index: 9999;", mobile)
        self.assertIn("background: #000;", mobile)
        self.assertIn("#chatOverlay.overlay-visible {", mobile)
        self.assertIn("transform: translateX(18px);", mobile)
        self.assertIn('id="launchShell"', mobile)
        self.assertIn("scheduleActiveSessionPrewarm(activeSessions);", mobile)
        self.assertIn("function primeChatFrame(sessionName, chatUrl) {", mobile)
        self.assertIn("function ensureChatLaunchShellFlag(rawUrl) {", mobile)
        self.assertIn('next.searchParams.set("launch_shell", "1");', mobile)
        self.assertIn("const CHAT_RENDER_READY_FALLBACK_MS = 2600;", mobile)
        self.assertIn('e.data && e.data.type === "multiagent-chat-render-ready"', mobile)
        self.assertNotIn('<img class="launch-shell-logo"', mobile)
        self.assertIn('src="data:image/', mobile)

    def test_desktop_hub_sidebar_stays_open_on_non_phone_toggle(self) -> None:
        desktop = hub_server.HUB_HOME_DESKTOP_HTML
        self.assertIn("function syncDeskSidebarViewportMode({ force = false } = {}) {", desktop)
        self.assertIn("syncDeskSidebarViewportMode({ force: true });", desktop)
        self.assertRegex(
            desktop,
            r'if \(event\.data && event\.data\.type === "multiagent-toggle-hub-sidebar"\) \{'
            r'\s*if \(isPhoneViewport\(\)\) \{'
            r'\s*setDeskSidebarOpen\(!isDeskSidebarOpen\(\)\);'
            r'\s*if \(isDeskSidebarOpen\(\)\) setDeskSidebarMode\("list"\);'
            r'\s*\} else \{'
            r'\s*setDeskSidebarOpen\(true\);'
            r'\s*setDeskSidebarMode\("list"\);'
            r'\s*\}'
            r'\s*return;'
            r'\s*\}',
        )

    def test_hub_launch_shell_html_targets_real_hub(self) -> None:
        val = hub_server.HUB_LAUNCH_SHELL_HTML
        self.assertTrue(val.startswith("<!doctype html>"))
        self.assertIn("const shellPath = \"/hub-launch-shell.html\";", val)
        self.assertIn("const ensureLaunchShellFlag = (rawTarget) => {", val)
        self.assertIn("next.searchParams.set(\"launch_shell\", \"1\")", val)
        self.assertIn("params.get(\"target\")", val)
        self.assertIn("fetch(target, { cache: \"no-store\" })", val)
        self.assertIn("rgb(10, 10, 10)", val)
        self.assertNotIn('<img class="launch-shell-logo"', val)

    def test_hub_service_worker_prefers_network_launch_shell(self) -> None:
        sw_path = Path(__file__).resolve().parents[1] / "lib" / "agent_index" / "static" / "pwa" / "service-worker.js"
        val = sw_path.read_text(encoding="utf-8")
        self.assertIn("const freshShell = await fetch(`${prefix}/hub-launch-shell.html`, { cache: \"no-store\" });", val)
        self.assertIn("await cache.put(`${prefix}/hub-launch-shell.html`, freshShell.clone());", val)

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
        self.assertIn('const pickBtn = document.getElementById("pickBtn");', val)
        self.assertIn('const NATIVE_PICKER_SUPPORTED =', val)
        self.assertIn('/pick-workspace', val)
        self.assertIn('/start-session-draft', val)
        self.assertIn('Choose in Finder', val)
        self.assertIn('menuPanel.classList.toggle("open");', val)
        self.assertNotIn('/resume"', val)
        self.assertNotIn('/stats"', val)

    def test_escape_sequences_preserved_in_templates(self) -> None:
        # These unicode characters (middle dot, em dash, ellipsis) were
        # written in the original Python source as \u00b7, \u2014, \u2026.
        # After extraction they must be real characters, not escape strings.
        new_session = hub_server.HUB_NEW_SESSION_HTML
        self.assertIn("New Session \u00b7 Hub", new_session)
        self.assertIn("Choose in Finder", new_session)
        self.assertNotIn(r"\u00b7", new_session)


if __name__ == "__main__":
    unittest.main()
