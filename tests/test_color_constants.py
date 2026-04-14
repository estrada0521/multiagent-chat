from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index import color_constants


class ColorConstantsTests(unittest.TestCase):
    def test_resolve_theme_palette_derives_gray_levels(self) -> None:
        palette = color_constants.resolve_theme_palette({"theme_bg_level": 8, "theme_fg_level": 240})
        self.assertEqual(palette["gray_panel_strong_level"], 13)
        self.assertEqual(palette["gray_surface_level"], 18)
        self.assertEqual(palette["gray_surface_alt_level"], 23)
        self.assertEqual(palette["gray_hover_level"], 28)
        self.assertEqual(palette["gray_inline_border_level"], 62)
        self.assertEqual(palette["gray_muted_level"], 146)

    def test_apply_color_tokens_rewrites_legacy_dark_gray_literals(self) -> None:
        result = color_constants.apply_color_tokens(
            "a:rgb(20,20,20);b:rgba(30, 30, 29,0.5);c:rgb(158, 158, 158);",
            {"theme_bg_level": 5, "theme_fg_level": 250},
        )
        self.assertIn("a:rgb(15,15,15);", result)
        self.assertIn("b:rgba(25, 25, 25,0.5);", result)
        self.assertIn("c:rgb(156,156,156);", result)

    def test_apply_color_tokens_rewrites_gray_tokens(self) -> None:
        result = color_constants.apply_color_tokens(
            "__GRAY_SURFACE__ __GRAY_HOVER_CHANNELS__ __GRAY_MUTED__",
            {"theme_bg_level": 12, "theme_fg_level": 245},
        )
        self.assertEqual(result, "rgb(22,22,22) 32, 32, 32 rgb(151,151,151)")


if __name__ == "__main__":
    unittest.main()
