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
        self.external_root = Path(self.tempdir.name) / "session-artifacts"
        self.external_root.mkdir()
        (self.workspace / "nested").mkdir()
        (self.workspace / "nested" / "data.txt").write_text("0123456789", encoding="utf-8")
        self.outside_file = Path(self.tempdir.name) / "outside.txt"
        self.outside_file.write_text("outside", encoding="utf-8")
        (self.external_root / "upload.txt").write_text("upload", encoding="utf-8")
        self.runtime = FileRuntime(workspace=self.workspace, allowed_roots=[self.external_root])

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_resolve_path_accepts_workspace_member(self) -> None:
        resolved = self.runtime._resolve_path("nested/data.txt")
        self.assertEqual(resolved, str(Path(self.runtime.workspace) / "nested" / "data.txt"))

    def test_resolve_path_rejects_traversal_outside_allowed_roots(self) -> None:
        with self.assertRaises(PermissionError):
            self.runtime._resolve_path("../outside.txt")

    def test_resolve_path_rejects_symlink_to_outside_allowed_roots(self) -> None:
        try:
            os.symlink(self.outside_file, self.workspace / "nested" / "escape.txt")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink not supported: {exc}")
        with self.assertRaises(PermissionError):
            self.runtime._resolve_path("nested/escape.txt")

    def test_resolve_path_allows_symlink_that_stays_inside_workspace(self) -> None:
        try:
            os.symlink(self.workspace / "nested" / "data.txt", self.workspace / "nested" / "mirror.txt")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink not supported: {exc}")
        resolved = self.runtime._resolve_path("nested/mirror.txt")
        self.assertEqual(resolved, str(Path(self.runtime.workspace) / "nested" / "data.txt"))

    def test_resolve_path_allows_additional_safe_root(self) -> None:
        resolved = self.runtime._resolve_path(str(self.external_root / "upload.txt"))
        self.assertEqual(resolved, str((self.external_root / "upload.txt").resolve()))

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

    def test_file_view_text_keeps_line_number_and_code_line_height_in_sync(self) -> None:
        page = self.runtime.file_view(
            "nested/data.txt",
            embed=True,
            agent_font_family='"Test Family", serif',
            agent_text_size=15,
        )
        self.assertIn('class="code-table"', page)
        self.assertIn('class="ln">1</td>', page)
        self.assertIn('--agent-font-family:"Test Family", serif;', page)
        self.assertIn("--code-font-family:", page)
        self.assertIn("--message-text-size:15px;", page)
        self.assertIn("--message-text-line-height:24px;", page)
        self.assertIn('.code-table .ln{', page)
        self.assertIn("font-family:var(--code-font-family);font-size:var(--message-text-size)", page)
        self.assertIn("line-height:var(--message-text-line-height)", page)
        self.assertIn('.code-table .lc pre{', page)
        self.assertIn('codeScroll?.addEventListener("wheel",verticalBiasWheel,{passive:false});', page)

    def test_file_view_html_can_toggle_between_web_and_text_modes(self) -> None:
        html_path = self.workspace / "nested" / "page.html"
        html_path.write_text("<!doctype html>\n<html><body>Hello</body></html>\n", encoding="utf-8")
        page = self.runtime.file_view(
            "nested/page.html",
            embed=False,
            agent_font_family='"Test Family", serif',
            agent_text_size=15,
        )
        self.assertIn('data-preview-mode="web"', page)
        self.assertIn('data-preview-mode="text"', page)
        self.assertIn('HTML preview mode', page)
        self.assertIn('sandbox="allow-same-origin allow-scripts allow-forms allow-popups"', page)
        self.assertIn('/file-raw?path=nested/page.html', page)
        self.assertIn('class="html-preview-text-table"', page)
        self.assertIn("font-family:var(--code-font-family);font-size:var(--message-text-size)", page)
        self.assertIn("--message-text-size:15px;", page)
        self.assertIn("viewContainer.scrollTop += event.deltaY;", page)
        self.assertIn("window.__agentIndexApplyHtmlPreviewMode=setMode;", page)
        self.assertIn('data.type!=="agent-index-file-preview-mode"', page)

    def test_file_view_html_embed_uses_parent_control_surface(self) -> None:
        html_path = self.workspace / "nested" / "embedded.html"
        html_path.write_text("<!doctype html>\n<html><body>Hello</body></html>\n", encoding="utf-8")
        page = self.runtime.file_view("nested/embedded.html", embed=True)
        self.assertNotIn('aria-label="HTML preview mode"', page)
        self.assertIn("window.__agentIndexApplyHtmlPreviewMode=setMode;", page)
        self.assertIn('data.type!=="agent-index-file-preview-mode"', page)
        self.assertIn('sandbox="allow-same-origin allow-scripts allow-forms allow-popups"', page)

    def test_file_view_markdown_uses_chat_font_mode_and_code_scroll_controls(self) -> None:
        markdown_path = self.workspace / "nested" / "notes.md"
        markdown_path.write_text(
            "# Title\n\n```python\nprint('hello')\nprint('world')\n```\n",
            encoding="utf-8",
        )
        page = self.runtime.file_view(
            "nested/notes.md",
            embed=True,
            agent_font_mode="gothic",
            agent_font_family='"Test Family", sans-serif',
            agent_text_size=16,
        )
        self.assertIn('data-agent-font-mode="gothic"', page)
        self.assertIn('--agent-font-family:"Test Family", sans-serif;', page)
        self.assertIn(".md-preview-shell{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;background:var(--bg)}", page)
        self.assertIn(".md-body :not(pre)>code{font-family:var(--code-font-family);", page)
        self.assertIn("prismjs@1.29.0/prism.min.js", page)
        self.assertIn("components/prism-python.min.js", page)
        self.assertNotIn("plugins/line-numbers/prism-line-numbers.min.css", page)
        self.assertNotIn("plugins/line-numbers/prism-line-numbers.min.js", page)
        self.assertNotIn('preEl.classList.add("line-numbers");', page)
        self.assertNotIn(".md-body pre.line-numbers .line-numbers-rows > span:before{", page)
        self.assertIn(".md-body pre{display:block;width:100%;max-width:100%;box-sizing:border-box;", page)
        self.assertIn("padding:14px 16px;margin:0;overflow-x:auto;", page)
        self.assertIn(".md-body .code-block-wrap{position:relative;display:block;margin:14px 0;overflow-x:hidden}", page)
        self.assertIn(".md-body .code-block-wrap .code-copy-btn{position:absolute;top:8px;right:8px;", page)
        self.assertIn("overflow-x:auto;overflow-y:hidden", page)

    def test_file_view_markdown_loads_only_needed_client_libs(self) -> None:
        markdown_path = self.workspace / "nested" / "simple.md"
        markdown_path.write_text("# Minimal\n\ntext only\n", encoding="utf-8")
        page = self.runtime.file_view("nested/simple.md", embed=True)
        self.assertIn("marked@12/marked.min.js", page)
        self.assertNotIn("prismjs@1.29.0/prism.min.js", page)
        self.assertNotIn("plugins/line-numbers/prism-line-numbers.min.css", page)
        self.assertNotIn("plugins/line-numbers/prism-line-numbers.min.js", page)
        self.assertNotIn("katex@0.16.11/dist/katex.min.js", page)

    def test_file_view_markdown_loads_prism_components_for_detected_fence_langs(self) -> None:
        markdown_path = self.workspace / "nested" / "bash-only.md"
        markdown_path.write_text("```bash\necho hi\n```\n", encoding="utf-8")
        page = self.runtime.file_view("nested/bash-only.md", embed=True)
        self.assertIn("prismjs@1.29.0/prism.min.js", page)
        self.assertIn("components/prism-bash.min.js", page)
        self.assertNotIn("components/prism-python.min.js", page)
        self.assertNotIn("components/prism-typescript.min.js", page)


if __name__ == "__main__":
    unittest.main()
