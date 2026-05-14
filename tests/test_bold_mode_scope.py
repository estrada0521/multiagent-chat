from __future__ import annotations

import unittest

from server.font_style import chat_font_settings_inline_style
from server.style import _chat_bold_mode_rules_block


def _agent_selectors(suffix: str, prefix: str = "") -> str:
    return f"{prefix}.message:not(.user):not(.system){suffix}"


def _detail_selectors(prefix: str = "") -> str:
    return f"{prefix}.agent-detail"


class BoldModeScopeTest(unittest.TestCase):
    def _render(self, *, mobile: bool, desktop: bool) -> str:
        return chat_font_settings_inline_style(
            {
                "bold_mode_mobile": mobile,
                "bold_mode_desktop": desktop,
                "message_text_size": 13,
            },
            bold_mode_viewport_max_px=480,
            generate_agent_message_selectors_fn=_agent_selectors,
            chat_bold_mode_rules_block_fn=_chat_bold_mode_rules_block,
            bh_agent_detail_selectors_fn=_detail_selectors,
        )

    def test_mobile_bold_excludes_tauri_desktop_chat(self) -> None:
        css = self._render(mobile=True, desktop=False)
        self.assertIn("@media (max-width: 480px)", css)
        self.assertIn('html:not([data-tauri-app="1"][data-hub-iframe-chat="1"]) .message.user .md-body', css)
        self.assertNotIn('html[data-tauri-app="1"][data-hub-iframe-chat="1"] .message.user .md-body', css)

    def test_desktop_bold_applies_to_tauri_chat_at_any_width(self) -> None:
        css = self._render(mobile=False, desktop=True)
        self.assertIn("@media (min-width: 481px)", css)
        self.assertIn('html[data-tauri-app="1"][data-hub-iframe-chat="1"] .message.user .md-body', css)


if __name__ == "__main__":
    unittest.main()
