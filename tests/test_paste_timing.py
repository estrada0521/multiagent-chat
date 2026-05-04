from __future__ import annotations

import unittest

from message_delivery.paste_timing import delivery_paste_delay_seconds


class DeliveryPasteDelaySecondsTest(unittest.TestCase):
    def test_default_attached_delay_matches_agent_send_baseline(self) -> None:
        self.assertEqual(0.3, delivery_paste_delay_seconds("", env={}, session_attached_count=1))

    def test_detached_session_uses_extra_margin(self) -> None:
        self.assertEqual(0.45, delivery_paste_delay_seconds("", env={}, session_attached_count=0))

    def test_long_payload_adds_extra_delay(self) -> None:
        self.assertGreater(
            delivery_paste_delay_seconds("x" * 4000, env={}, session_attached_count=1),
            0.3,
        )

    def test_env_override_wins(self) -> None:
        self.assertEqual(
            0.9,
            delivery_paste_delay_seconds("x" * 4000, env={"AGENT_SEND_PASTE_DELAY": "0.9"}, session_attached_count=0),
        )


if __name__ == "__main__":
    unittest.main()
