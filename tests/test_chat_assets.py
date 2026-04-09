from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index import chat_assets


class ChatAssetsTests(unittest.TestCase):
    def test_chat_script_defaults_empty_target_to_user(self) -> None:
        self.assertIn('target = "user";', chat_assets.CHAT_APP_SCRIPT_ASSET)

    def test_chat_variants_force_mobile_state_by_template(self) -> None:
        self.assertIn("const MOBILE_VIEWPORT_MAX_PX = 480;", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const _isMobile = false;", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const _isMobile = true;", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertNotIn("window.matchMedia(`(max-width: ${MOBILE_VIEWPORT_MAX_PX}px)`)", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertNotIn("window.matchMedia(`(max-width: ${MOBILE_VIEWPORT_MAX_PX}px)`)", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)

    def test_chat_asset_urls_include_variant(self) -> None:
        self.assertIn("view=desktop", chat_assets.chat_app_asset_url())
        self.assertIn("view=mobile", chat_assets.chat_app_asset_url(variant="mobile"))
        self.assertIn("view=desktop", chat_assets.chat_style_asset_url())
        self.assertIn("view=mobile", chat_assets.chat_style_asset_url(variant="mobile"))

    def test_chat_script_derives_base_path_from_session_route_when_needed(self) -> None:
        self.assertIn("const CHAT_BOOTSTRAP = window.__CHAT_BOOTSTRAP__ || {};", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('const CHAT_BASE_PATH = String(CHAT_BOOTSTRAP.basePath || "");', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const CHAT_BOOTSTRAP = window.__CHAT_BOOTSTRAP__ || {};", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn('const CHAT_BASE_PATH = String(CHAT_BOOTSTRAP.basePath || "");', chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertNotIn("detectChatBasePath", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertNotIn("detectChatBasePath", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)

    def test_chat_script_linkifies_inline_code_file_refs(self) -> None:
        self.assertIn("linkifyInlineCodeFileRefs(scope);", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('anchor.className = "inline-file-link";', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const decorateLocalFileLinks = (scope = document) => {", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('anchor.classList.add("local-file-link");', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn(".md-body a.inline-file-link code", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(".md-body a.local-file-link", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn("color: var(--inline-file-link-fg);", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(".has-hover .md-body a.inline-file-link:hover code", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(".has-hover .md-body a.inline-file-link:hover,", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(".has-hover .md-body a.local-file-link:hover { text-decoration: none; }", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(
            ".message.user .md-body :not(pre):not(a.inline-file-link):not(a.local-file-link) > code",
            chat_assets.CHAT_MAIN_STYLE_ASSET,
        )

    def test_chat_script_checks_file_existence_before_opening_preview(self) -> None:
        self.assertIn("const fileExistsOnDisk = async (path) => {", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const exists = await fileExistsOnDisk(normalizedPath);", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("if (isPublicChatView) {", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("openFileModal(normalizedPath, ext, sourceEl, triggerEvent);", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("if (!exists) {", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const fileExistsOnDisk = async (path) => {", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("const exists = await fileExistsOnDisk(normalizedPath);", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("if (isPublicChatView) {", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("openFileModal(normalizedPath, ext, sourceEl, triggerEvent);", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)

    def test_chat_launch_shell_gate_waits_until_first_render(self) -> None:
        self.assertIn('document.documentElement.dataset.launchShell = "1";', chat_assets.CHAT_HTML)
        self.assertIn('document.documentElement.dataset.launchShell = "1";', chat_assets.CHAT_MOBILE_HTML)
        self.assertIn("html[data-launch-shell=\"1\"] body > .shell {", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn("html[data-launch-shell=\"1\"] body > .shell {", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn("let hasInitialRefreshHydrated = false;", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const releaseLaunchShellGate = () => {", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("(!hasInitialRefreshHydrated && followMode)", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("releaseLaunchShellGate();", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("let hasInitialRefreshHydrated = false;", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("const releaseLaunchShellGate = () => {", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("(!hasInitialRefreshHydrated && followMode)", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("releaseLaunchShellGate();", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)

    def test_chat_script_uses_file_view_for_html_and_exposes_html_mode_toggle(self) -> None:
        self.assertIn('id="fileModalHtmlModeBtn"', chat_assets.CHAT_HTML)
        self.assertIn('const fileModalHtmlModeBtn = document.getElementById("fileModalHtmlModeBtn");', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const viewerUrl = withChatBase(`/file-view?path=${encodeURIComponent(path)}&embed=1`);", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('agent-index-file-preview-mode', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("postFileModalHtmlPreviewMode();", chat_assets.CHAT_APP_SCRIPT_ASSET)

    def test_chat_script_relaxes_fetch_timeout_for_session_proxy(self) -> None:
        for script in (chat_assets.CHAT_APP_SCRIPT_ASSET, chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET):
            self.assertIn("const fetchWithTimeout = async (url, options = {}, timeoutMs = 5000) => {", script)
            self.assertIn("fetchWithTimeout(`/session-state?ts=${Date.now()}`, {}, 3500);", script)
            self.assertIn("fetchWithTimeout(messagesFetchUrl({ limit: 1 }), {}, 3500);", script)

    def test_chat_script_avoids_double_base_prefix_on_fetch_and_allows_slower_session_routes(self) -> None:
        self.assertNotIn("fetch(withChatBase(", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertNotIn("fetch(withChatBase(", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("const fetchWithTimeout = async (url, options = {}, timeoutMs = 5000) => {", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const fetchWithTimeout = async (url, options = {}, timeoutMs = 5000) => {", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("fetchWithTimeout(`/session-state?ts=${Date.now()}`, {}, 3500);", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("fetchWithTimeout(`/session-state?ts=${Date.now()}`, {}, 3500);", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("fetchWithTimeout(messagesFetchUrl({ limit: 1 }), {}, 3500);", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("fetchWithTimeout(messagesFetchUrl({ limit: 1 }), {}, 3500);", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)

    def test_mobile_file_preview_uses_solid_surface_and_agent_font(self) -> None:
        self.assertIn("body.file-modal-open .shell > .hub-page-header::before {", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn(".file-modal-dialog {", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn(".file-modal-body {", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn("background: rgb(10, 10, 10);", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn("backdrop-filter: none;", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn("font-family: var(--agent-thinking-font-family", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)

    def test_chat_script_uses_inline_code_for_at_file_autocomplete(self) -> None:
        self.assertIn('const inlineRef = "`" + path + "`";', chat_assets.CHAT_APP_SCRIPT_ASSET)

    def test_chat_script_collects_inline_code_refs_for_file_menu(self) -> None:
        self.assertIn("const collectInlineReferencedPaths = (entry) => {", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("body.matchAll(/`([^`\\n]+)`/g)", chat_assets.CHAT_APP_SCRIPT_ASSET)

    def test_chat_style_uses_red_for_real_urls(self) -> None:
        self.assertIn("--external-link-fg:", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(
            ".md-body a:not(.inline-file-link):not(.local-file-link) { color: var(--external-link-fg); text-decoration: none; }",
            chat_assets.CHAT_MAIN_STYLE_ASSET,
        )

    def test_chat_script_renders_agent_thinking_compactly(self) -> None:
        self.assertIn('kind === "agent-thinking"', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("computeThinkingMetaHiddenIds", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("hideMetaRow", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("thinking-meta-hidden", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn(".message-row.kind-agent-thinking .message", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(".message-row.kind-agent-thinking + .message-row.kind-agent-thinking", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(".message-row.kind-agent-thinking.thinking-meta-hidden", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(".message-row.kind-agent-thinking .md-body", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(".message-row.kind-agent-thinking .md-body p", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertNotIn("groupThinkingEntries", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertNotIn("thinking-group-details", chat_assets.CHAT_MAIN_STYLE_ASSET)

    def test_chat_variant_assets_are_distinct(self) -> None:
        self.assertNotEqual(chat_assets.CHAT_APP_SCRIPT_ASSET, chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertNotEqual(chat_assets.CHAT_MAIN_STYLE_ASSET, chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)

    def test_chat_script_embedded_home_click_and_render_ready_handshake(self) -> None:
        self.assertIn('window.parent.postMessage({ type: "multiagent-toggle-hub-sidebar" }, "*");', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('window.parent.postMessage({ type: "multiagent-open-hub-path", url: hubUrl }, "*");', chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn('window.parent.postMessage({ type: "multiagent-chat-render-ready" }, "*");', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('window.parent.postMessage({ type: "multiagent-chat-render-ready" }, "*");', chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)

    def test_chat_runtime_indicator_is_scrollable_and_has_bottom_running_line(self) -> None:
        self.assertIn(".message-thinking-container {", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn("position: relative;", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn("body.agent-runtime-running::after", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn("animation: running-bottom-line-flow", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn(".message-thinking-container {", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn("position: relative;", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn("body.agent-runtime-running::after", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn("animation: running-bottom-line-flow", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)

    def test_mobile_chat_script_recomputes_bottom_spacer_after_iframe_prewarm(self) -> None:
        self.assertIn("const syncMainAfterHeight = () => {", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("syncMainAfterHeight();", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("window.addEventListener(\"resize\", syncMainAfterHeight, { passive: true });", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)


if __name__ == "__main__":
    unittest.main()
