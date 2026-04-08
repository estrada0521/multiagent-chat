from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index import chat_assets


class ChatAssetsTests(unittest.TestCase):
    def test_chat_script_defaults_empty_target_to_user(self) -> None:
        self.assertIn('target = "user";', chat_assets.CHAT_APP_SCRIPT_ASSET)

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
        self.assertIn("if (!exists) {", chat_assets.CHAT_APP_SCRIPT_ASSET)

    def test_chat_script_uses_file_view_for_html_and_exposes_html_mode_toggle(self) -> None:
        self.assertIn('id="fileModalHtmlModeBtn"', chat_assets.CHAT_HTML)
        self.assertIn('const fileModalHtmlModeBtn = document.getElementById("fileModalHtmlModeBtn");', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("const viewerUrl = withChatBase(`/file-view?path=${encodeURIComponent(path)}&embed=1`);", chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn('agent-index-file-preview-mode', chat_assets.CHAT_APP_SCRIPT_ASSET)
        self.assertIn("postFileModalHtmlPreviewMode();", chat_assets.CHAT_APP_SCRIPT_ASSET)

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


if __name__ == "__main__":
    unittest.main()
