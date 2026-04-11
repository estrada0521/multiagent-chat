from __future__ import annotations

import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from agent_index import hub_header_assets


class HeaderMenuBridgeAlignmentTests(unittest.TestCase):
    def test_hub_header_bridge_tracks_svg_hitbox(self) -> None:
        script = hub_header_assets.HUB_PAGE_HEADER_JS
        self.assertIn('var icon = menuBtn.querySelector("svg");', script)
        self.assertIn("var padX = 9;", script)
        self.assertIn("var padY = 10;", script)
        self.assertIn('window.addEventListener("scroll", _syncBridge, { passive: true });', script)
        self.assertIn(
            'window.visualViewport && window.visualViewport.addEventListener("scroll", _syncBridge, { passive: true });',
            script,
        )

    def test_chat_mobile_bridge_tracks_svg_hitbox(self) -> None:
        path = Path(__file__).resolve().parents[1] / "lib" / "agent_index" / "chat_template_mobile.html"
        source = path.read_text(encoding="utf-8")
        self.assertIn('const icon = rightMenuBtn.querySelector("svg");', source)
        self.assertIn("const padX = 9;", source)
        self.assertIn("const padY = 10;", source)
        self.assertIn('window.addEventListener("scroll", syncBridge, { passive: true });', source)
        self.assertIn(
            'window.visualViewport && window.visualViewport.addEventListener("scroll", syncBridge, { passive: true });',
            source,
        )


if __name__ == "__main__":
    unittest.main()
