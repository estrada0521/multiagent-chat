from __future__ import annotations

import json
import unittest

import _bootstrap  # noqa: F401
from agent_index.chat_render_core import apply_chat_template_replacements, build_chat_template_replacements


class ChatRenderCoreTests(unittest.TestCase):
    def test_build_chat_template_replacements(self) -> None:
        replacements = build_chat_template_replacements(
            icon_data_uris={"claude": "data:image/png;base64,aaa"},
            logo_src="/hub-logo",
            base_path="/session/demo",
            chat_manifest_url="/app.webmanifest?v=1",
            chat_pwa_icon_192_url="/pwa-icon-192.png?v=1",
            chat_apple_touch_icon_url="/apple-touch-icon.png?v=1",
            chat_style_asset_url="/chat-assets/chat-app.css?v=1",
            chat_app_bootstrap_html="<script>boot</script>",
            chat_app_asset_url="/chat-assets/chat-app.js?v=1",
            server_instance="srv-1",
            hub_port=4321,
            chat_settings={
                "theme": "black-hole",
                "starfield": False,
                "chat_sound": True,
                "chat_browser_notifications": False,
                "chat_tts": True,
                "agent_font_mode": "default",
                "message_limit": 80,
            },
            agent_font_mode_inline_style="font-weight: 500;",
            hub_header_css=".header {}",
        )
        self.assertEqual(replacements["__HUB_LOGO_DATA_URI__"], "/hub-logo")
        self.assertEqual(replacements["__CHAT_BASE_PATH__"], "/session/demo")
        self.assertEqual(replacements["__CHAT_SOUND_ENABLED__"], "true")
        self.assertEqual(replacements["__CHAT_BROWSER_NOTIFICATIONS_ENABLED__"], "false")
        self.assertEqual(replacements["__MESSAGE_LIMIT__"], "80")
        self.assertIn("claude", json.loads(replacements["__ICON_DATA_URIS__"]))

    def test_apply_chat_template_replacements(self) -> None:
        rendered = apply_chat_template_replacements(
            "A __ONE__ B __TWO__ C",
            {"__ONE__": "x", "__TWO__": "y"},
        )
        self.assertEqual(rendered, "A x B y C")


if __name__ == "__main__":
    unittest.main()
