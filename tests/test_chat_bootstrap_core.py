from __future__ import annotations

import json
import unittest

import _bootstrap  # noqa: F401
from agent_index.chat_bootstrap_core import build_chat_bootstrap_payload, encode_chat_bootstrap_payload


class ChatBootstrapCoreTests(unittest.TestCase):
    def test_build_chat_bootstrap_payload(self) -> None:
        payload = build_chat_bootstrap_payload(
            icon_data_uris={"claude": "data:image/png;base64,aaa"},
            server_instance="srv-1",
            hub_port=4242,
            chat_settings={
                "chat_sound": True,
                "chat_browser_notifications": False,
            },
            chat_base_path="/session/demo/",
            agent_icon_names=["claude", "codex"],
            all_base_agents=["claude", "codex"],
        )
        self.assertEqual(payload["basePath"], "/session/demo")
        self.assertEqual(payload["serverInstance"], "srv-1")
        self.assertEqual(payload["hubPort"], 4242)
        self.assertTrue(payload["chatSoundEnabled"])
        self.assertFalse(payload["chatBrowserNotificationsEnabled"])
        self.assertEqual(payload["agentIconNames"], ["claude", "codex"])
        self.assertEqual(payload["allBaseAgents"], ["claude", "codex"])

    def test_encode_chat_bootstrap_payload_escapes_script_close(self) -> None:
        encoded = encode_chat_bootstrap_payload({"message": "</script><b>danger</b>"})
        self.assertIn("<\\/", encoded)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["message"], "</script><b>danger</b>")


if __name__ == "__main__":
    unittest.main()
