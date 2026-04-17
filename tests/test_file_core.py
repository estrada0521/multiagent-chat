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

    def test_list_dir_returns_direct_children_with_kinds(self) -> None:
        (self.workspace / "root.txt").write_text("root", encoding="utf-8")
        (self.workspace / "nested" / "inner").mkdir()
        (self.workspace / "nested" / "inner" / "deep.txt").write_text("deep", encoding="utf-8")
        entries = self.runtime.list_dir("")
        by_name = {entry["name"]: entry for entry in entries}
        self.assertEqual(by_name["nested"]["kind"], "dir")
        self.assertEqual(by_name["root.txt"]["kind"], "file")
        self.assertNotIn("deep.txt", by_name)

    def test_list_dir_skips_ignored_directories(self) -> None:
        (self.workspace / ".git").mkdir()
        (self.workspace / ".git" / "config").write_text("x", encoding="utf-8")
        entries = self.runtime.list_dir("")
        self.assertFalse(any(entry["name"] == ".git" for entry in entries))

    def test_list_dir_reports_file_size(self) -> None:
        entries = self.runtime.list_dir("nested")
        data_entry = next((entry for entry in entries if entry["name"] == "data.txt"), None)
        self.assertIsNotNone(data_entry)
        self.assertEqual(data_entry["kind"], "file")
        self.assertEqual(data_entry["size"], 10)

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
        self.assertIn("--preview-selected-line-bg:rgba(255,255,255,0.10);", page)
        self.assertIn("--preview-gutter-divider:rgba(255,255,255,0.16);", page)
        self.assertIn('.code-table .ln{', page)
        self.assertIn("padding:0 5px 0 4px;", page)
        self.assertIn("font-family:var(--code-font-family);font-size:var(--message-text-size)", page)
        self.assertIn("line-height:var(--message-text-line-height)", page)
        self.assertIn("position:sticky;left:0;z-index:1;background:", page)
        self.assertIn('data-preview-gutter-width="', page)
        self.assertIn('data-preview-title-offset="', page)
        self.assertIn('.view-container::before{content:"";position:absolute;top:0;bottom:0;left:0;width:var(--preview-gutter-width);background:var(--preview-gutter-bg);box-shadow:inset -1px 0 0 var(--preview-gutter-divider);', page)
        self.assertIn('.view-container::after{content:"";position:absolute;left:0;bottom:0;width:var(--preview-gutter-width);height:calc(var(--preview-scrollbar-size) + 4px);background:var(--preview-gutter-bg);box-shadow:inset -1px 0 0 var(--preview-gutter-divider);', page)
        self.assertIn('.code-scroll{position:relative;z-index:1;flex:1;min-height:0;width:100%;overflow:auto;overscroll-behavior:contain;padding-top:var(--tpad,0px)}', page)
        self.assertIn("box-sizing:border-box", page)
        self.assertIn('.code-table .lc pre{', page)
        self.assertIn('.code-table tbody tr.is-selected .ln,.code-table tbody tr.is-selected .lc{background:var(--preview-selected-line-bg)}', page)
        self.assertIn('codeScroll?.addEventListener("wheel",verticalBiasWheel,{passive:false});', page)
        self.assertIn('const selectableTable=document.querySelector(".code-table");', page)
        self.assertIn('selectedRow?.classList.remove("is-selected");', page)

    def test_file_view_header_shows_icon_and_filename_only(self) -> None:
        page = self.runtime.file_view("nested/data.txt", embed=False)
        self.assertIn('<span class="fn">data.txt</span>', page)
        self.assertNotIn('class="fp"', page)

    def test_file_view_non_markdown_text_extensions_get_line_numbers(self) -> None:
        ts_path = self.workspace / "nested" / "sample.ts"
        ts_path.write_text("const value = 1;\nconsole.log(value);\n", encoding="utf-8")
        page = self.runtime.file_view("nested/sample.ts", embed=True)
        self.assertIn('class="code-table"', page)
        self.assertIn('class="ln">1</td>', page)
        self.assertIn('data-preview-gutter-width="', page)
        self.assertIn("position:sticky;left:0;z-index:1;background:", page)
        self.assertIn('const selectableTable=document.querySelector(".code-table");', page)

    def test_file_view_progressive_text_uses_line_number_table_and_small_chunks(self) -> None:
        large_txt_path = self.workspace / "nested" / "huge.txt"
        large_txt_path.write_text("x\n" * 350_000, encoding="utf-8")
        page = self.runtime.file_view("nested/huge.txt", embed=True)
        self.assertIn('id="codeBody"', page)
        self.assertIn('class="code-table"', page)
        self.assertIn("const chunkBytes=32768;", page)
        self.assertIn("headers:{Range:`bytes=${start}-${end}`}", page)
        self.assertIn('data-preview-title-offset="', page)
        self.assertIn("position:sticky;left:0;z-index:1;background:", page)
        self.assertIn("const progressiveCodeScroll=document.getElementById(\"codeScroll\");", page)
        self.assertIn("const progressiveScrollTarget=progressiveCodeScroll||progressiveViewContainer;", page)
        self.assertIn('.view-container::after{content:"";position:absolute;left:0;bottom:0;width:var(--preview-gutter-width);height:calc(var(--preview-scrollbar-size) + 4px);background:var(--preview-gutter-bg);box-shadow:inset -1px 0 0 var(--preview-gutter-divider);', page)
        self.assertIn('.code-table tbody tr.is-selected .ln,.code-table tbody tr.is-selected .lc{background:var(--preview-selected-line-bg)}', page)
        self.assertNotIn('id="status"', page)
        self.assertNotIn("Loading preview...", page)

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
        self.assertIn('<html data-preview-mode="text" data-preview-gutter-width="', page)
        self.assertIn('data-preview-mode="web" aria-selected="false"', page)
        self.assertIn('data-preview-mode="text" aria-selected="true"', page)
        self.assertIn('HTML preview mode', page)
        self.assertIn('sandbox="allow-same-origin allow-scripts allow-forms allow-popups"', page)
        self.assertIn('/file-raw?path=nested/page.html', page)
        self.assertIn('class="html-preview-text-table"', page)
        self.assertIn("font-family:var(--code-font-family);font-size:var(--message-text-size)", page)
        self.assertIn("position:sticky;left:0;z-index:1;background:", page)
        self.assertIn('data-preview-gutter-width="', page)
        self.assertIn('.html-preview-text-wrap::before{content:"";position:absolute;top:0;bottom:0;left:0;width:var(--preview-gutter-width);background:var(--preview-gutter-bg);box-shadow:inset -1px 0 0 var(--preview-gutter-divider);', page)
        self.assertIn('.html-preview-text-wrap::after{content:"";position:absolute;left:0;bottom:0;width:var(--preview-gutter-width);height:calc(var(--preview-scrollbar-size) + 4px);background:var(--preview-gutter-bg);box-shadow:inset -1px 0 0 var(--preview-gutter-divider);', page)
        self.assertIn('.html-preview-text-table tbody tr.is-selected .ln,.html-preview-text-table tbody tr.is-selected .lc{background:var(--preview-selected-line-bg)}', page)
        self.assertIn("--message-text-size:15px;", page)
        self.assertIn("verticalScrollTarget.scrollTop += event.deltaY;", page)
        self.assertIn("window.__agentIndexApplyHtmlPreviewMode=setMode;", page)
        self.assertIn('setMode("text");', page)
        self.assertIn('data.type!=="agent-index-file-preview-mode"', page)
        self.assertIn('const selectableTable=document.querySelector(".html-preview-text-table");', page)

    def test_file_view_large_html_uses_progressive_text_panel_loading(self) -> None:
        html_path = self.workspace / "nested" / "big.html"
        html_path.write_text("<!doctype html>\n" + ("<div>hello</div>\n" * 40_000), encoding="utf-8")
        page = self.runtime.file_view("nested/big.html", embed=False)
        self.assertNotIn('id="htmlTextStatus"', page)
        self.assertIn('id="htmlTextCodeBody"', page)
        self.assertIn("const chunkBytes=32768;", page)
        self.assertIn("headers:{Range:`bytes=${start}-${end}`}", page)
        self.assertIn("window.__agentIndexApplyHtmlPreviewMode=setMode;", page)
        self.assertNotIn("Loading preview...", page)

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
        self.assertIn(".md-preview-shell{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;background:var(--bg);scrollbar-gutter:auto;padding-top:var(--tpad,0px)}", page)
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

    def test_file_view_markdown_rewrites_local_links_to_file_view(self) -> None:
        markdown_path = self.workspace / "nested" / "notes.md"
        markdown_path.write_text("[Next](./deep/next.md)\n", encoding="utf-8")
        page = self.runtime.file_view(
            "nested/notes.md",
            embed=True,
            pane=True,
            base_path="/session/demo",
            agent_font_mode="gothic",
            agent_text_size=16,
            message_bold=True,
        )
        self.assertIn('const __previewPane = true;', page)
        self.assertIn('const __previewBasePath = "/session/demo";', page)
        self.assertIn('params.set("pane", "1");', page)
        self.assertIn('params.set("base_path", __previewBasePath);', page)
        self.assertIn('params.set("agent_font_mode", __previewAgentFontMode);', page)
        self.assertIn('params.set("message_bold", __previewMessageBold ? "1" : "0");', page)
        self.assertIn('anchor.setAttribute("href", buildPreviewHref(resolved) + suffix);', page)

    def test_file_view_markdown_preserves_absolute_base_paths_for_relative_links(self) -> None:
        markdown_path = self.workspace / "nested" / "notes.md"
        markdown_path.write_text("[Next](./deep/next.md)\n", encoding="utf-8")
        page = self.runtime.file_view(str(markdown_path), embed=True)
        self.assertIn('const normalizedBaseRel = String(baseRel || "").replaceAll("\\\\", "/");', page)
        self.assertIn('const baseIsAbsolute = normalizedBaseRel.startsWith("/");', page)
        self.assertIn('const srcIsAbsolute = withoutQuery.startsWith("/");', page)
        self.assertIn('if (!normalized) return srcIsAbsolute || baseIsAbsolute ? "/" : "";', page)
        self.assertIn('return srcIsAbsolute || baseIsAbsolute ? `/${normalized}` : normalized;', page)

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
