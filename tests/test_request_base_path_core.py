from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index.request_base_path_core import normalize_request_base_path, request_base_path


class RequestBasePathCoreTests(unittest.TestCase):
    def test_normalize_request_base_path_accepts_session_prefix(self) -> None:
        self.assertEqual(normalize_request_base_path("/session/demo"), "/session/demo")

    def test_normalize_request_base_path_rejects_invalid_chars(self) -> None:
        self.assertEqual(normalize_request_base_path("/session/demo bad"), "")
        self.assertEqual(normalize_request_base_path("//evil"), "")
        self.assertEqual(normalize_request_base_path('/session/"demo"'), "")

    def test_request_base_path_prefers_forwarded_prefix(self) -> None:
        self.assertEqual(
            request_base_path(
                headers={"X-Forwarded-Prefix": "/session/demo"},
                query_string="base_path=%2Fsession%2Fother",
            ),
            "/session/demo",
        )

    def test_request_base_path_uses_query_fallback(self) -> None:
        self.assertEqual(
            request_base_path(headers={}, query_string="path=notes.md&base_path=%2Fsession%2Fdemo"),
            "/session/demo",
        )

    def test_request_base_path_ignores_invalid_query_fallback(self) -> None:
        self.assertEqual(
            request_base_path(headers={}, query_string="base_path=%2Fsession%2Fdemo%20bad"),
            "",
        )


if __name__ == "__main__":
    unittest.main()
