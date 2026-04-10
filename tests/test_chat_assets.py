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
        self.assertIn("const fileViewHrefForPath = (path, { embed = false } = {}) => {", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('params.set("agent_font_mode", currentFilePreviewFontMode());', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('if (CHAT_BASE_PATH) params.set("base_path", CHAT_BASE_PATH);', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('if (textSize) params.set("agent_text_size", textSize);', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const viewerUrl = fileViewHrefForPath(path, { embed: true });", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const viewerUrl = fileViewHrefForPath(path, { embed: true });", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn('let fileModalHtmlPreviewMode = "text";', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('let fileModalHtmlPreviewMode = "text";', chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn('stored.mode === "web" ? "web" : "text"', chat_assets.CHAT_APP_SCRIPT_ASSET)
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

    def test_chat_runtime_indicator_is_scrollable_and_toggles_running_state(self) -> None:
        self.assertIn(".message-thinking-container {", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn("position: relative;", chat_assets.CHAT_MAIN_STYLE_ASSET)
        self.assertIn('document.body?.classList.toggle("agent-runtime-running", hasRuntimeRunning);', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn(".message-thinking-container {", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn("position: relative;", chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET)
        self.assertIn('document.body?.classList.toggle("agent-runtime-running", hasRuntimeRunning);', chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)

    def test_mobile_chat_script_recomputes_bottom_spacer_after_iframe_prewarm(self) -> None:
        self.assertIn("const syncMainAfterHeight = () => {", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("syncMainAfterHeight();", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        self.assertIn("window.addEventListener(\"resize\", syncMainAfterHeight, { passive: true });", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)

    def test_mobile_chat_autoloads_older_entries_and_only_shows_centered_rail(self) -> None:
        self.assertIn(
            "return olderEntries.length ? merged : merged.slice(-INITIAL_MESSAGE_WINDOW);",
            chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET,
        )
        self.assertIn(
            ".message-row:not(.user):not(.kind-agent-thinking).is-centered .message::before",
            chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET,
        )
        self.assertNotIn(
            ".message-row:not(.user):not(.kind-agent-thinking):is(:hover, :focus-within, .is-centered) .message::before",
            chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET,
        )

    def test_consecutive_agent_meta_hiding_is_consistent_on_mobile(self) -> None:
        self.assertIn(
            'const currentIsAgent = sender && sender !== "user" && sender !== "system";',
            chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET,
        )
        self.assertIn(
            "currentIsAgent && sender === prevSender && currentIsThinking === prevWasThinking",
            chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET,
        )

    def test_file_modal_header_uses_filename_only_and_file_icons_are_white(self) -> None:
        self.assertNotIn('id="fileModalPath"', chat_assets.CHAT_HTML)
        self.assertNotIn('id="fileModalPath"', chat_assets.CHAT_MOBILE_HTML)
        self.assertNotIn("fileModalPath", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertNotIn("fileModalPath", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)
        for style in (chat_assets.CHAT_MAIN_STYLE_ASSET, chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET):
            self.assertIn(".file-item-icon {", style)
            self.assertIn("color: var(--text);", style)
            self.assertIn("opacity: 1;", style)

    def test_camera_mode_has_frosted_backdrop_toggle_button(self) -> None:
        self.assertIn('id="cameraModeBackdropBtn"', chat_assets.CHAT_HTML)
        self.assertIn('id="cameraModeBackdropBtn"', chat_assets.CHAT_MOBILE_HTML)
        for style in (chat_assets.CHAT_MAIN_STYLE_ASSET, chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET):
            self.assertIn(".camera-mode-shell.backdrop-frosted::after", style)
            self.assertIn(".camera-mode-backdrop-toggle", style)
            self.assertIn("background: rgba(0, 0, 0, 0.46);", style)
            self.assertIn(".camera-mode-hint[hidden] {", style)
            self.assertIn(".camera-mode-shell.backdrop-frosted .camera-mode-bottom {", style)
            self.assertIn("min-height: 100%;", style)
            self.assertIn(".camera-mode-shell.backdrop-frosted .camera-mode-replies {", style)
            self.assertIn("mask-image: none;", style)
        for script in (chat_assets.CHAT_APP_SCRIPT_ASSET, chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET):
            self.assertIn('const cameraModeBackdropBtn = document.getElementById("cameraModeBackdropBtn");', script)
            self.assertIn("let cameraModeBackdropFrosted = false;", script)
            self.assertIn("const syncCameraModeBackdrop = () => {", script)
            self.assertIn("cameraModeBackdropBtn?.addEventListener(\"click\", (event) => {", script)
            self.assertIn('cameraModeTargetRail?.classList.toggle("is-visible", !!(mounted && compact && activeTarget));', script)
            self.assertNotIn('cameraModeTargetRail?.classList.toggle("is-visible", !!(mounted && cameraModeBackdropFrosted && activeTarget));', script)
            self.assertNotIn('setCameraModeHint("Opening camera...");', script)

    def test_camera_mode_replies_use_lower_half_and_share_main_message_styles(self) -> None:
        for style in (chat_assets.CHAT_MAIN_STYLE_ASSET, chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET):
            self.assertIn(".camera-mode-bottom {", style)
            self.assertIn("top: 50%;", style)
            self.assertIn("min-height: 50vh;", style)
            self.assertNotIn(".camera-mode .message.user .message-body-row.is-collapsed::after {", style)
            self.assertNotIn(".camera-mode-replies .message-row.system {", style)
        self.assertNotIn("cameraModeHint.classList.contains(\"error\")", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertNotIn("cameraModeHint.classList.contains(\"error\")", chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET)

    def test_mobile_header_action_buttons_use_ios_press_feedback(self) -> None:
        style = chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET
        self.assertIn("--page-side-pad: 12px;", style)
        self.assertIn("--chrome-icon-btn-size: 44px;", style)
        self.assertIn("--chrome-icon-size: 21px;", style)
        self.assertIn("--chrome-icon-gap: 9px;", style)
        self.assertIn("padding: max(8px, env(safe-area-inset-top)) calc(var(--page-side-pad) + 5px + env(safe-area-inset-right, 0px)) 8px var(--page-side-pad);", style)
        self.assertIn(".shell > .hub-page-header #gitBranchMenuBtn,", style)
        self.assertIn(".shell > .hub-page-header #attachedFilesMenuBtn {", style)
        self.assertIn("display: none;", style)
        self.assertIn(".shell > .hub-page-header .hub-page-header-actions {", style)
        self.assertIn("gap: 0;", style)
        self.assertIn(".shell > .hub-page-header .hub-page-header-actions .hub-page-menu-btn {", style)
        self.assertIn("background: transparent;", style)
        self.assertIn("border: none;", style)
        self.assertIn("box-shadow: none;", style)
        self.assertNotIn("is-tap-bloom", style)
        mobile_script = chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET
        self.assertNotIn("bindMobileHeaderPressFeedback", mobile_script)
        self.assertNotIn("is-tap-bloom", mobile_script)

    def test_mobile_hamburger_supports_ios_native_picker_menu(self) -> None:
        self.assertIn('id="hubPageNativeMenuSelect"', chat_assets.CHAT_MOBILE_HTML)
        self.assertNotIn('id="hubPageNativeMenuSelect"', chat_assets.CHAT_HTML)
        for icon_name in ("branches", "files", "reload", "terminal", "finder", "camera", "export", "sync", "add", "remove"):
            self.assertIn(f'data-menu-icon="{icon_name}"', chat_assets.CHAT_MOBILE_HTML)
        mobile_style = chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET
        self.assertIn(".hub-native-menu-select.is-ios-active {", mobile_style)
        self.assertIn("opacity: 0.01;", mobile_style)
        self.assertIn("pointer-events: auto;", mobile_style)
        self.assertIn('.hub-native-menu-select option[data-menu-icon="branches"] {', mobile_style)
        self.assertIn('.hub-native-menu-select option[data-menu-icon="files"] {', mobile_style)
        self.assertIn('.hub-native-menu-select option[data-menu-icon="reload"] {', mobile_style)
        self.assertIn('.hub-native-menu-select option[data-menu-icon="terminal"] {', mobile_style)
        self.assertIn('.hub-native-menu-select option[data-menu-icon="finder"] {', mobile_style)
        self.assertIn('.hub-native-menu-select option[data-menu-icon="camera"] {', mobile_style)
        self.assertIn('.hub-native-menu-select option[data-menu-icon="export"] {', mobile_style)
        self.assertIn('.hub-native-menu-select option[data-menu-icon="sync"] {', mobile_style)
        self.assertIn('.hub-native-menu-select option[data-menu-icon="add"] {', mobile_style)
        self.assertIn('.hub-native-menu-select option[data-menu-icon="remove"] {', mobile_style)
        self.assertIn("background-image: url(\"data:image/svg+xml,", mobile_style)
        mobile_script = chat_assets.CHAT_MOBILE_APP_SCRIPT_ASSET
        self.assertIn('const nativeHeaderMenuSelect = document.getElementById("hubPageNativeMenuSelect");', mobile_script)
        self.assertIn("const useNativeHeaderMenuPicker = !!(_isMobile && isAppleTouchDevice && nativeHeaderMenuSelect && rightMenuBtn);", mobile_script)
        self.assertIn("const syncNativeHeaderMenuSelectAnchor = () => {", mobile_script)
        self.assertIn('nativeHeaderMenuSelect.classList.add("is-ios-active");', mobile_script)
        self.assertIn('nativeHeaderMenuSelect?.addEventListener("change", () => {', mobile_script)
        self.assertIn('if (target === "openGitBranchMenu") {', mobile_script)
        self.assertIn("gitBranchMenuBtn?.click();", mobile_script)
        self.assertIn('if (target === "openAttachedFilesMenu") {', mobile_script)
        self.assertIn("attachedFilesMenuBtn?.click();", mobile_script)
        self.assertIn('if (useNativeHeaderMenuPicker) {', mobile_script)
        self.assertIn("if (openNativeHeaderMenuPicker()) return;", mobile_script)

    def test_target_chip_active_icon_remains_white(self) -> None:
        for style in (chat_assets.CHAT_MAIN_STYLE_ASSET, chat_assets.CHAT_MOBILE_MAIN_STYLE_ASSET):
            self.assertIn(".target-chip.active .target-icon {", style)
            self.assertIn("filter: brightness(0) invert(1);", style)
            self.assertNotIn('active[data-base-agent="codex"] .target-icon', style)
            self.assertNotIn('active[data-base-agent="copilot"] .target-icon', style)


if __name__ == "__main__":
    unittest.main()
