from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index.chat_style_core import _chat_bold_mode_rules_block


class ChatStyleCoreTests(unittest.TestCase):
    def test_bold_mode_rules_include_composer_textarea(self) -> None:
        css = _chat_bold_mode_rules_block()
        self.assertIn(".composer textarea", css)
        self.assertIn("font-weight: 620", css)
        self.assertIn('html[data-agent-font-mode="gothic"] .message.claude .md-body', css)
        self.assertIn('html[data-agent-font-mode="gothic"] .message.codex .md-body h1', css)


if __name__ == "__main__":
    unittest.main()
