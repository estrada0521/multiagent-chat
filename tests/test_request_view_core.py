from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index.request_view_core import request_view_variant


class RequestViewCoreTests(unittest.TestCase):
    def test_query_override_wins(self) -> None:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        self.assertEqual(
            request_view_variant(headers=headers, query_string="view=mobile"),
            "mobile",
        )

    def test_client_hint_prefers_mobile(self) -> None:
        headers = {"Sec-CH-UA-Mobile": "?1"}
        self.assertEqual(request_view_variant(headers=headers, query_string=""), "mobile")

    def test_user_agent_falls_back_to_mobile(self) -> None:
        headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"}
        self.assertEqual(request_view_variant(headers=headers, query_string=""), "mobile")

    def test_desktop_is_default(self) -> None:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        self.assertEqual(request_view_variant(headers=headers, query_string=""), "desktop")


if __name__ == "__main__":
    unittest.main()
