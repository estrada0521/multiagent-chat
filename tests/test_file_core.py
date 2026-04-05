from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from agent_index.file_core import FileRuntime


class FileCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name) / "workspace"
        self.workspace.mkdir()
        (self.workspace / "nested").mkdir()
        (self.workspace / "nested" / "data.txt").write_text("0123456789", encoding="utf-8")
        self.outside_file = Path(self.tempdir.name) / "outside.txt"
        self.outside_file.write_text("outside", encoding="utf-8")
        self.runtime = FileRuntime(workspace=self.workspace)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_resolve_path_accepts_workspace_member(self) -> None:
        resolved = self.runtime._resolve_path("nested/data.txt")
        self.assertEqual(resolved, str(Path(self.runtime.workspace) / "nested" / "data.txt"))

    def test_resolve_path_allows_traversal(self) -> None:
        resolved = self.runtime._resolve_path("../outside.txt")
        self.assertEqual(resolved, str(self.outside_file.resolve()))

    def test_resolve_path_allows_symlink_to_outside_workspace(self) -> None:
        try:
            os.symlink(self.outside_file, self.workspace / "nested" / "escape.txt")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink not supported: {exc}")
        resolved = self.runtime._resolve_path("nested/escape.txt")
        self.assertEqual(resolved, str(self.outside_file.resolve()))

    def test_resolve_path_allows_symlink_that_stays_inside_workspace(self) -> None:
        try:
            os.symlink(self.workspace / "nested" / "data.txt", self.workspace / "nested" / "mirror.txt")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink not supported: {exc}")
        resolved = self.runtime._resolve_path("nested/mirror.txt")
        self.assertEqual(resolved, str(Path(self.runtime.workspace) / "nested" / "data.txt"))

    def test_resolve_path_allows_workspace_root(self) -> None:
        self.assertEqual(
            self.runtime._resolve_path(""),
            self.runtime.workspace,
        )

    def test_parse_single_range_supports_suffix_ranges(self) -> None:
        start, end, is_partial = self.runtime._parse_single_range("bytes=-4", 10)
        self.assertEqual((start, end, is_partial), (6, 9, True))

    def test_raw_response_metadata_returns_partial_range(self) -> None:
        metadata = self.runtime.raw_response_metadata("nested/data.txt", "bytes=2-5")
        self.assertEqual(metadata["status"], 206)
        self.assertEqual(metadata["start"], 2)
        self.assertEqual(metadata["end"], 5)
        self.assertEqual(metadata["length"], 4)
        self.assertEqual(metadata["content_range"], "bytes 2-5/10")

    def test_raw_response_metadata_returns_416_for_invalid_range(self) -> None:
        metadata = self.runtime.raw_response_metadata("nested/data.txt", "bytes=20-30")
        self.assertEqual(metadata["status"], 416)
        self.assertEqual(metadata["size"], 10)


if __name__ == "__main__":
    unittest.main()
