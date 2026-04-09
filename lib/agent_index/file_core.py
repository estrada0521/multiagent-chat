from __future__ import annotations
import logging

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from html import escape as html_escape
from pathlib import Path
from urllib.parse import quote as url_quote

from .file_preview_3d import render_3d_preview


class FileRuntime:
    INLINE_PROGRESSIVE_PREVIEW_MAX_BYTES = 512 * 1024
    RAW_STREAM_CHUNK_BYTES = 64 * 1024
    PROGRESSIVE_TEXT_PREVIEW_CHUNK_BYTES = 128 * 1024
    MIME_TYPES = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".ico": "image/x-icon",
        ".pdf": "application/pdf",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".obj": "text/plain; charset=utf-8",
        ".stl": "model/stl",
        ".step": "application/step",
        ".stp": "application/step",
    }
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}
    TEXT_EXTS = {".py", ".js", ".json", ".yaml", ".yml", ".sh", ".sql", ".html", ".css", ".tex", ".txt", ".csv", ".log"}
    EDITABLE_TEXT_EXTS = TEXT_EXTS | {".md", ".ts", ".tsx", ".jsx", ".toml", ".ini", ".cfg", ".conf", ".rst", ".env"}
    PDF_EXTS = {".pdf"}
    VIDEO_EXTS = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
    }
    AUDIO_EXTS = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
    }
    MODEL_3D_EXTS = {".obj", ".stl", ".step", ".stp"}
    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache"}

    def __init__(self, *, workspace: str | Path, allowed_roots: list[str | Path] | tuple[str | Path, ...] | None = None):
        self.workspace = os.path.realpath(os.path.normpath(str(workspace)))
        roots = [self.workspace]
        for candidate in allowed_roots or ():
            if not candidate:
                continue
            resolved = os.path.realpath(os.path.normpath(str(candidate)))
            if resolved not in roots:
                roots.append(resolved)
        self.allowed_roots = tuple(roots)

    def _is_allowed_path(self, full: str) -> bool:
        for root in self.allowed_roots:
            if full == root or full.startswith(root + os.sep):
                return True
        return False

    def _resolve_path(self, rel: str, *, allow_workspace_root: bool = False) -> str:
        rel = rel or ""
        if rel.startswith("~"):
            full = os.path.realpath(os.path.expanduser(rel))
        elif os.path.isabs(rel):
            full = os.path.realpath(os.path.normpath(rel))
        else:
            full = os.path.realpath(os.path.join(self.workspace, rel.lstrip("/")))
        if not self._is_allowed_path(full):
            raise PermissionError(full)
        return full

    def files_exist(self, paths: list[str]) -> dict[str, bool]:
        """Check which paths exist within the workspace."""
        result = {}
        for rel in paths:
            try:
                full = self._resolve_path(rel, allow_workspace_root=True)
                result[rel] = os.path.exists(full)
            except (PermissionError, Exception):
                result[rel] = False
        return result

    def file_raw(self, rel: str):
        full = self._resolve_path(rel)
        ext = os.path.splitext(rel)[1].lower()
        with open(full, "rb") as f:
            raw = f.read()
        return self.MIME_TYPES.get(ext, "application/octet-stream"), raw

    @classmethod
    def content_type_for_rel(cls, rel: str) -> str:
        ext = os.path.splitext(rel)[1].lower()
        return cls.MIME_TYPES.get(ext, "application/octet-stream")

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024.0 or unit == "TB":
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{size} B"

    @staticmethod
    def _parse_single_range(range_header: str, size: int):
        if not range_header:
            return 0, max(0, size - 1), False
        if size <= 0 or not range_header.startswith("bytes="):
            raise ValueError("invalid range")
        spec = range_header[6:].strip()
        if not spec or "," in spec or "-" not in spec:
            raise ValueError("invalid range")
        start_raw, end_raw = spec.split("-", 1)
        if not start_raw:
            suffix_length = int(end_raw or "0")
            if suffix_length <= 0:
                raise ValueError("invalid range")
            start = max(0, size - suffix_length)
            end = size - 1
        else:
            start = int(start_raw)
            end = size - 1 if not end_raw else int(end_raw)
            if start < 0 or end < start or start >= size:
                raise ValueError("invalid range")
            end = min(end, size - 1)
        return start, end, True

    def raw_response_metadata(self, rel: str, range_header: str = "") -> dict:
        full = self._resolve_path(rel)
        size = os.path.getsize(full)
        try:
            start, end, is_partial = self._parse_single_range(range_header, size)
        except ValueError:
            return {
                "status": 416,
                "size": size,
                "content_type": self.content_type_for_rel(rel),
                "full_path": full,
            }
        if size == 0:
            start = 0
            end = -1
            is_partial = False
        length = 0 if end < start else (end - start + 1)
        return {
            "status": 206 if is_partial else 200,
            "size": size,
            "start": start,
            "end": end,
            "length": length,
            "is_partial": is_partial,
            "content_type": self.content_type_for_rel(rel),
            "content_range": f"bytes {start}-{end}/{size}" if is_partial else "",
            "full_path": full,
        }

    @classmethod
    def stream_raw_response(cls, metadata: dict, write):
        length = int(metadata.get("length", 0) or 0)
        if length <= 0:
            return
        full_path = str(metadata.get("full_path") or "")
        start = int(metadata.get("start", 0) or 0)
        with open(full_path, "rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = handle.read(min(cls.RAW_STREAM_CHUNK_BYTES, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                if write(chunk) is False:
                    break

    def file_content(self, rel: str):
        full = self._resolve_path(rel, allow_workspace_root=True)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        ext = os.path.splitext(rel)[1].lstrip(".")
        return {"content": content, "ext": ext}

    @staticmethod
    def _is_probably_text_file(full: str) -> bool:
        try:
            with open(full, "rb") as f:
                sample = f.read(4096)
        except OSError:
            return False
        if not sample:
            return True
        if b"\x00" in sample:
            return False
        return True

    def can_open_in_editor(self, rel: str) -> bool:
        full = self._resolve_path(rel, allow_workspace_root=True)
        if not os.path.isfile(full):
            return False
        ext = os.path.splitext(full)[1].lower()
        if ext == ".pdf":
            return self._pdf_browser_command(full) is not None
        return ext in self.EDITABLE_TEXT_EXTS or self._is_probably_text_file(full)

    @staticmethod
    def _pdf_browser_command(full: str) -> list[str] | None:
        uri = Path(full).resolve().as_uri()
        if sys.platform == "darwin":
            if FileRuntime._macos_app_exists("Safari"):
                return ["open", "-a", "Safari", uri]
            return None
        if shutil.which("xdg-open"):
            return ["xdg-open", full]
        return None

    @staticmethod
    def _macos_app_exists(app_name: str) -> bool:
        if sys.platform != "darwin" or not shutil.which("osascript"):
            return False
        try:
            result = subprocess.run(
                ["osascript", "-e", f'id of application "{app_name}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return False
        return result.returncode == 0

    @staticmethod
    def _editor_command(full: str, line: int = 0) -> tuple[list[str], str]:
        configured = (os.environ.get("MULTIAGENT_EXTERNAL_EDITOR") or "").strip()
        if configured:
            if "{path}" in configured:
                return shlex.split(configured.format(path=full)), "custom"
            return shlex.split(configured) + [full], "custom"
        browser_cmd = FileRuntime._pdf_browser_command(full) if full.lower().endswith(".pdf") else None
        if browser_cmd:
            return browser_cmd, "system"
        line_arg = f":{line}" if line > 0 else ""
        if sys.platform == "darwin":
            if FileRuntime._macos_app_exists("CotEditor"):
                if line > 0:
                    # Use AppleScript to open at specific line
                    script = (
                        f'tell application "CotEditor"\n'
                        f'  activate\n'
                        f'  open POSIX file "{full}"\n'
                        f'  tell front document\n'
                        f'    jump to line {line}\n'
                        f'  end tell\n'
                        f'end tell'
                    )
                    return ["osascript", "-e", script], "lightweight"
                return ["open", "-na", "CotEditor", full], "lightweight"
            if FileRuntime._macos_app_exists("Sublime Text"):
                return ["open", "-na", "Sublime Text", f"{full}{line_arg}"], "lightweight"
            if FileRuntime._macos_app_exists("TextMate"):
                return ["open", "-na", "TextMate", full], "lightweight"
            if FileRuntime._macos_app_exists("BBEdit"):
                return ["open", "-na", "BBEdit", full], "lightweight"
        if shutil.which("code"):
            return ["code", "--new-window", "-g", f"{full}{line_arg}"], "vscode"
        if sys.platform == "darwin":
            return ["open", "-na", "Visual Studio Code", "--args", "--new-window", "--goto", f"{full}{line_arg}"], "vscode"
        return ["xdg-open", full], "system"

    @staticmethod
    def _shrink_vscode_window():
        if sys.platform != "darwin" or not shutil.which("osascript"):
            return
        script = '''
delay 0.35
tell application "Visual Studio Code" to activate
delay 0.2
        tell application "System Events"
            tell process "Code"
                if (count of windows) > 0 then
                    set position of front window to {108, 96}
                    set size of front window to {760, 560}
                end if
            end tell
        end tell
'''
        deadline = time.time() + 4.0
        while time.time() < deadline:
            try:
                subprocess.Popen(
                    ["osascript", "-e", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                time.sleep(0.15)

    def open_in_editor(self, rel: str, line: int = 0):
        full = self._resolve_path(rel, allow_workspace_root=True)
        if not os.path.isfile(full):
            raise FileNotFoundError(full)
        ext = os.path.splitext(full)[1].lower()
        if ext not in self.EDITABLE_TEXT_EXTS and ext not in {".html", ".htm", ".pdf"} and not self._is_probably_text_file(full):
            raise ValueError("Only text files can be opened in an external editor.")
        cmd, mode = self._editor_command(full, line=line)
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if mode == "vscode":
            self._shrink_vscode_window()
        return {"ok": True, "path": rel}

    def list_files(self):
        files = []
        for root, dirs, filenames in os.walk(self.workspace):
            dirs[:] = sorted(d for d in dirs if d not in self.SKIP_DIRS)
            depth = root[len(self.workspace):].count(os.sep)
            if depth >= 3:
                dirs.clear()
            for filename in sorted(filenames):
                full = os.path.join(root, filename)
                rel = full[len(self.workspace):].lstrip(os.sep)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = None
                files.append({
                    "path": rel,
                    "size": size,
                })
        return files

    @staticmethod
    def _highlight_text(escaped_text: str, ext: str, *, theme_comment: str, theme_keyword: str, theme_string: str,
                        theme_number: str, theme_func: str, theme_type: str, theme_prop: str,
                        theme_tag: str, theme_punct: str, theme_builtin: str) -> str:
        def hl(pattern, replacement, value):
            parts = re.split(r"(<[^>]*>)", value)
            return "".join(re.sub(pattern, replacement, chunk) if not chunk.startswith("<") else chunk for chunk in parts)

        if ext in {".py", ".sh", ".yaml", ".yml"}:
            escaped_text = re.sub(r"(^[ \t]*#[^\n]*)", rf'<span style="color:{theme_comment}">\1</span>', escaped_text, flags=re.MULTILINE)
        elif ext in {".js", ".ts", ".css", ".sql", ".json"}:
            escaped_text = re.sub(r"(//[^\n]*)", rf'<span style="color:{theme_comment}">\1</span>', escaped_text)
        elif ext == ".tex":
            escaped_text = re.sub(r"(^[ \t]*%[^\n]*)", rf'<span style="color:{theme_comment}">\1</span>', escaped_text, flags=re.MULTILINE)

        escaped_text = hl(r'("(?:[^"\\<\n]|\\.)*"|\'(?:[^\'\\<\n]|\\.)*\')', rf'<span style="color:{theme_string}">\1</span>', escaped_text)
        escaped_text = hl(r"(?<![\w#])(-?\d+(?:\.\d+)?)", rf'<span style="color:{theme_number}">\1</span>', escaped_text)

        if ext in {".json", ".yaml", ".yml"}:
            escaped_text = hl(r"(^[ \t-]*)([A-Za-z_][\w.-]*)(\s*:)", rf'\1<span style="color:{theme_prop}">\2</span>\3', escaped_text)
        if ext == ".tex":
            escaped_text = hl(r"(\\[A-Za-z@]+)", rf'<span style="color:{theme_tag}">\1</span>', escaped_text)
        if ext == ".html":
            escaped_text = hl(r"(&lt;/?)([A-Za-z][\w:-]*)", rf'\1<span style="color:{theme_tag}">\2</span>', escaped_text)
            escaped_text = hl(r"([A-Za-z_:][\w:.-]*)(=)(&quot;.*?&quot;)", rf'<span style="color:{theme_prop}">\1</span>\2<span style="color:{theme_string}">\3</span>', escaped_text)
        if ext == ".css":
            escaped_text = hl(r"(^[ \t]*)([.#]?[A-Za-z_-][\w:-]*)(\s*\{)", rf'\1<span style="color:{theme_tag}">\2</span>\3', escaped_text)
            escaped_text = hl(r"([A-Za-z-]+)(\s*:)", rf'<span style="color:{theme_prop}">\1</span>\2', escaped_text)
        if ext in {".py", ".js", ".sh", ".sql"}:
            escaped_text = hl(r"(^[ \t]*@[\w.]+)", rf'<span style="color:{theme_tag}">\1</span>', escaped_text)

        escaped_text = hl(r"\b(def|class|import|from|return|if|else|elif|for|while|try|except|with|as|yield|await|async|function|const|let|var|type|interface|enum|public|private|protected|static|readonly|do|switch|case|default|break|continue|new|delete|typeof|instanceof|void|this|super|in|of|null|undefined|true|false)\b", rf'<span style="color:{theme_keyword}">\1</span>', escaped_text)
        escaped_text = hl(r"\b(str|int|float|bool|list|dict|tuple|set|None|self|cls|SELECT|FROM|WHERE|GROUP|ORDER|BY|JOIN|LEFT|RIGHT|INNER|OUTER|LIMIT|INSERT|UPDATE|DELETE|CREATE|TABLE|VALUES)\b", rf'<span style="color:{theme_type}">\1</span>', escaped_text)
        escaped_text = hl(r"\b(print|len|range|echo|printf|console|log)\b", rf'<span style="color:{theme_builtin}">\1</span>', escaped_text)
        escaped_text = hl(r"\b([A-Za-z_][\w]*)(?=\()", rf'<span style="color:{theme_func}">\1</span>', escaped_text)
        escaped_text = hl(r"(?<=\.)\b([A-Za-z_][\w]*)\b", rf'<span style="color:{theme_prop}">\1</span>', escaped_text)
        escaped_text = hl(r"([{}()[\],.:;=+\-/*<>])", rf'<span style="color:{theme_punct}">\1</span>', escaped_text)
        return escaped_text

    def file_view(
        self,
        rel: str,
        *,
        embed: bool = False,
        base_path: str = "",
        agent_font_mode: str = "serif",
        agent_font_family: str | None = None,
        agent_text_size: int | None = None,
    ) -> str:
        full = self._resolve_path(rel)
        if not os.path.exists(full):
            raise FileNotFoundError(full)

        ext = os.path.splitext(rel)[1].lower()
        filename = os.path.basename(rel)
        prefix = (base_path or "").rstrip("/")
        raw_url = f"{prefix}/file-raw?path={url_quote(rel)}"
        size = os.path.getsize(full)
        agent_font_mode = "gothic" if str(agent_font_mode or "").strip().lower() == "gothic" else "serif"
        default_agent_font_family = (
            '"anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Meiryo", sans-serif'
            if agent_font_mode == "gothic"
            else '"anthropicSerif", "anthropicSerif Fallback", "Anthropic Serif", "Hiragino Mincho ProN", "Yu Mincho", "YuMincho", "Noto Serif JP", Georgia, "Times New Roman", Times, serif'
        )
        code_font_family = (
            '"jetbrainsMono", "JetBrains Mono", "Cascadia Code", "Fira Code", "SF Mono", '
            '"SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, "Liberation Mono", monospace'
        )
        agent_font_family = str(agent_font_family or default_agent_font_family).strip() or default_agent_font_family
        try:
            resolved_text_size = int(agent_text_size or 13)
        except (TypeError, ValueError):
            resolved_text_size = 13
        resolved_text_size = max(11, min(18, resolved_text_size))
        resolved_line_height = resolved_text_size + 9
        pane_bg = "rgb(10, 10, 10)"
        embed_bg = "transparent" if embed else pane_bg
        pane_fg = "rgb(252, 252, 252)"
        pane_muted = "rgb(252, 252, 252)"
        pane_line = "rgba(255,255,255,0.08)"
        font_base = prefix or ""
        font_face_css = (
            f'@font-face{{font-family:"anthropicSerif";src:url("{font_base}/font/anthropic-serif-roman.ttf") format("truetype");font-style:normal;font-weight:300 800;font-display:swap}}'
            f'@font-face{{font-family:"anthropicSerif";src:url("{font_base}/font/anthropic-serif-italic.ttf") format("truetype");font-style:italic;font-weight:300 800;font-display:swap}}'
            f'@font-face{{font-family:"anthropicSans";src:url("{font_base}/font/anthropic-sans-roman.ttf") format("truetype");font-style:normal;font-weight:300 800;font-display:swap}}'
            f'@font-face{{font-family:"anthropicSans";src:url("{font_base}/font/anthropic-sans-italic.ttf") format("truetype");font-style:italic;font-weight:300 800;font-display:swap}}'
            f'@font-face{{font-family:"jetbrainsMono";src:local("JetBrains Mono"),local("JetBrainsMono-Regular"),url("{font_base}/font/jetbrains-mono.ttf") format("truetype-variations"),url("{font_base}/font/jetbrains-mono.ttf") format("truetype");font-style:normal;font-weight:100 800;font-display:swap}}'
        )
        base_css = (
            f':root{{color-scheme: dark;--agent-font-family:{agent_font_family};--code-font-family:{code_font_family};--message-text-size:{resolved_text_size}px;--message-text-line-height:{resolved_line_height}px;}}'
            f"{font_face_css}"
            f"*{{box-sizing:border-box}}"
            f"html,body{{margin:0;background:{embed_bg};color:{pane_fg};font-family:var(--agent-font-family);display:flex;flex-direction:column;height:100vh;font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:360;font-synthesis-weight:none;font-synthesis-style:none;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;font-optical-sizing:auto;font-variation-settings:\"wght\" 360}}"
            f".hdr{{padding:10px 16px;background:{embed_bg};border-bottom:0.5px solid {pane_line};display:flex;align-items:center;gap:8px;flex-shrink:0}}"
            f".fn{{font-weight:700;font-size:14px;color:{pane_fg}}}.fp{{color:{pane_muted};font-size:12px}}"
        )
        header = "" if embed else (
            f'<div class="hdr"><span>{{icon}}</span><span class="fn">{html_escape(filename)}</span>'
            f'<span class="fp">{html_escape(rel)}</span></div>'
        )

        def build_text_table_markup(text_content: str, *, text_ext: str) -> tuple[str, int]:
            escaped = self._highlight_text(
                html_escape(text_content),
                text_ext,
                theme_comment="#5c6370",
                theme_keyword="#c678dd",
                theme_string="#98c379",
                theme_number="#d19a66",
                theme_func="#61afef",
                theme_type="#e5c07b",
                theme_prop="#56b6c2",
                theme_tag="#e06c75",
                theme_punct="#7f848e",
                theme_builtin="#56b6c2",
            )
            highlighted_lines = escaped.split("\n")
            line_count = max(1, len(highlighted_lines))
            gutter_width = len(str(line_count)) * 9 + 12
            table_rows = "".join(
                f'<tr><td class="ln">{idx}</td><td class="lc"><pre>{line if line else " "}</pre></td></tr>'
                for idx, line in enumerate(highlighted_lines, start=1)
            )
            return table_rows, gutter_width

        if ext in self.IMAGE_EXTS:
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}.wrap{{flex:1;overflow:auto;display:flex;align-items:center;justify-content:center;padding:16px;background:{embed_bg}}}'
                f'img{{max-width:100%;max-height:100%;object-fit:contain}}</style></head>'
                f'<body>{header.format(icon="🖼️")}<div class="wrap"><img src="{raw_url}" alt="{html_escape(filename)}"></div></body></html>'
            )
        if ext in self.PDF_EXTS:
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}.wrap{{flex:1;min-height:0;background:{embed_bg}}}iframe{{width:100%;height:100%;border:0;background:{embed_bg}}}</style></head>'
                f'<body>{header.format(icon="📕")}<div class="wrap"><iframe src="{raw_url}" title="{html_escape(filename)}"></iframe></div></body></html>'
            )
        if ext in self.VIDEO_EXTS:
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}.wrap{{flex:1;display:flex;align-items:center;justify-content:center;background:{embed_bg}}}'
                f'video{{max-width:100%;max-height:100%}}</style></head>'
                f'<body>{header.format(icon="🎬")}<div class="wrap"><video controls src="{raw_url}"></video></div></body></html>'
            )
        if ext in self.AUDIO_EXTS:
            audio_js = (
                'const audio=document.getElementById("audioPreview");'
                'const cv=document.getElementById("blobCanvas");'
                'const ctx=cv?cv.getContext("2d"):null;'
                'let frame=0,analyser=null,aCtx=null,freqData=null,bands=[0,0,0,0];'
                # DPR-aware sizing
                'const fit=()=>{'
                '  if(!cv)return;const dpr=Math.max(1,devicePixelRatio||1);'
                '  const s=Math.min(cv.clientWidth,cv.clientHeight)||200;'
                '  cv.width=Math.round(s*dpr);cv.height=Math.round(s*dpr);'
                '  if(ctx)ctx.setTransform(dpr,0,0,dpr,0,0);'
                '};'
                # AnalyserNode
                'const ensureAudio=async()=>{'
                '  if(analyser)return;try{'
                '  const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return;'
                '  aCtx=new AC();analyser=aCtx.createAnalyser();analyser.fftSize=128;'
                '  analyser.smoothingTimeConstant=0.82;'
                '  freqData=new Uint8Array(analyser.frequencyBinCount);'
                '  const src=aCtx.createMediaElementSource(audio);'
                '  src.connect(analyser);analyser.connect(aCtx.destination);'
                '  }catch(_){}'
                '};'
                # Get 4 frequency bands
                'const getBands=()=>{'
                '  if(!analyser||!freqData){bands=[0,0,0,0];return;}'
                '  analyser.getByteFrequencyData(freqData);'
                '  const n=freqData.length;const q=Math.floor(n/4);'
                '  for(let b=0;b<4;b++){'
                '    let sum=0;for(let i=b*q;i<(b+1)*q&&i<n;i++)sum+=freqData[i];'
                '    bands[b]=bands[b]*0.6+(sum/(q*255))*0.4;'
                '  }'
                '};'
                # Draw blob
                'const draw=()=>{'
                '  if(!ctx||!cv)return;fit();'
                '  const s=Math.min(cv.clientWidth,cv.clientHeight)||200;'
                '  const cx=s/2,cy=s/2;'
                '  const playing=!audio.paused&&!audio.ended;'
                '  const progress=audio.duration?audio.currentTime/audio.duration:0;'
                '  const t=performance.now()*0.001;'
                '  if(playing)getBands();'
                '  ctx.clearRect(0,0,s,s);'
                # Base radius
                '  const baseR=s*0.28;'
                '  const energyBoost=playing?(bands[0]*0.3+bands[1]*0.2)*baseR:0;'
                '  const breathe=Math.sin(t*0.8)*baseR*0.015;'
                '  const R=baseR+energyBoost+breathe;'
                # Control points
                '  const N=24;'
                '  const pts=[];'
                '  for(let i=0;i<N;i++){'
                '    const angle=(i/N)*Math.PI*2;'
                # Idle deformation: very subtle, nearly circular
                '    let deform=0;'
                '    deform+=Math.sin(angle*2+t*1.2)*0.02;'
                '    deform+=Math.sin(angle*3-t*0.9)*0.012;'
                '    deform+=Math.sin(angle*5+t*2.1)*0.006;'
                # Audio-reactive: strong deformation only when playing
                '    if(playing){'
                '      deform+=Math.sin(angle*2+t*3)*bands[0]*0.25;'
                '      deform+=Math.sin(angle*4-t*2.5)*bands[1]*0.18;'
                '      deform+=Math.sin(angle*6+t*4)*bands[2]*0.12;'
                '      deform+=Math.sin(angle*10-t*5)*bands[3]*0.08;'
                '    }'
                '    const r=R*(1+deform);'
                '    pts.push([cx+Math.cos(angle)*r, cy+Math.sin(angle)*r]);'
                '  }'
                # Smooth closed curve
                '  ctx.beginPath();'
                '  for(let i=0;i<N;i++){'
                '    const p0=pts[(i-1+N)%N],p1=pts[i],p2=pts[(i+1)%N],p3=pts[(i+2)%N];'
                '    const cp1x=p1[0]+(p2[0]-p0[0])/6;'
                '    const cp1y=p1[1]+(p2[1]-p0[1])/6;'
                '    const cp2x=p2[0]-(p3[0]-p1[0])/6;'
                '    const cp2y=p2[1]-(p3[1]-p1[1])/6;'
                '    if(i===0)ctx.moveTo(p1[0],p1[1]);'
                '    ctx.bezierCurveTo(cp1x,cp1y,cp2x,cp2y,p2[0],p2[1]);'
                '  }'
                '  ctx.closePath();'
                # Gradient fill
                '  const gAngle=progress*Math.PI*2-Math.PI/2;'
                '  const gR=R*1.2;'
                '  const grad=ctx.createLinearGradient('
                '    cx+Math.cos(gAngle)*gR, cy+Math.sin(gAngle)*gR,'
                '    cx+Math.cos(gAngle+Math.PI)*gR, cy+Math.sin(gAngle+Math.PI)*gR'
                '  );'
                '  const alpha=playing?0.35+bands[0]*0.25:0.18;'
                '  grad.addColorStop(0, "rgba(252,252,252,"+alpha.toFixed(3)+")");'
                '  grad.addColorStop(0.5, "rgba(220,220,220,"+(alpha*0.7).toFixed(3)+")");'
                '  grad.addColorStop(1, "rgba(200,200,200,"+(alpha*0.5).toFixed(3)+")");'
                '  ctx.fillStyle=grad;'
                '  ctx.fill();'
                # Stroke
                '  ctx.strokeStyle="rgba(252,252,252,"+(playing?0.25+bands[1]*0.3:0.1).toFixed(3)+")";'
                '  ctx.lineWidth=1;'
                '  ctx.stroke();'
                # Inner glow
                '  if(playing&&(bands[0]>0.1||bands[1]>0.1)){'
                '    ctx.save();ctx.globalAlpha=Math.min(0.15,bands[0]*0.2);'
                '    ctx.filter="blur("+Math.round(8+bands[0]*12)+"px)";'
                '    ctx.fillStyle="rgba(252,252,252,1)";ctx.fill();'
                '    ctx.restore();'
                '  }'
                '};'
                # Animation loop
                'const tick=()=>{draw();frame=requestAnimationFrame(tick);};'
                # Events
                'audio.addEventListener("play",async()=>{'
                '  await ensureAudio();if(aCtx&&aCtx.state==="suspended")await aCtx.resume();'
                '});'
                # Start immediately
                'fit();tick();'
            )
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}.wrap{{flex:1;display:flex;align-items:center;justify-content:center;padding:32px;background:{embed_bg}}}'
                f'.audio-shell{{width:100%;max-width:500px;display:flex;flex-direction:column;align-items:center;gap:14px}}'
                f'#blobCanvas{{width:200px;height:200px;display:block}}'
                f'audio{{width:100%;max-width:500px;min-width:0}}'
                f'</style></head>'
                f'<body>{header.format(icon="🎵")}<div class="wrap"><div class="audio-shell">'
                f'<canvas id="blobCanvas" width="200" height="200"></canvas>'
                f'<audio id="audioPreview" controls src="{raw_url}"></audio></div></div>'
                f'<script>{audio_js}</script></body></html>'
            )
        if ext in self.MODEL_3D_EXTS:
            return render_3d_preview(
                ext=ext,
                filename=filename,
                header_html=header.format(icon="🧊"),
                raw_url=raw_url,
                base_css=base_css,
                embed_bg=embed_bg,
                pane_muted=pane_muted,
                pane_line=pane_line,
            )
        if ext in {".html", ".htm"}:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            table_rows, gutter_width = build_text_table_markup(content, text_ext=".html")
            tabs_markup = "" if embed else (
                '<div class="html-preview-tabs" role="tablist" aria-label="HTML preview mode">'
                '<button class="html-preview-tab active" type="button" data-preview-mode="web" aria-selected="true">Web</button>'
                '<button class="html-preview-tab" type="button" data-preview-mode="text" aria-selected="false">Text</button>'
                '</div>'
            )
            toggle_js = (
                'const root=document.documentElement;'
                'const buttons=Array.from(document.querySelectorAll("[data-preview-mode]"));'
                'const panels=Array.from(document.querySelectorAll("[data-preview-panel]"));'
                'const setMode=(mode)=>{'
                'const nextMode=mode==="text"?"text":"web";'
                'root.dataset.previewMode=nextMode;'
                'window.__agentIndexHtmlPreviewMode=nextMode;'
                'buttons.forEach((button)=>{const active=button.dataset.previewMode===nextMode;button.classList.toggle("active",active);button.setAttribute("aria-selected",active?"true":"false");});'
                'panels.forEach((panel)=>panel.classList.toggle("active",panel.dataset.previewPanel===nextMode));'
                '};'
                'window.__agentIndexApplyHtmlPreviewMode=setMode;'
                'window.addEventListener("message",(event)=>{'
                'if(event.origin!==window.location.origin)return;'
                'const data=event.data||{};'
                'if(data.type!=="agent-index-file-preview-mode")return;'
                'setMode(data.mode);'
                '});'
                'const bindButtons=()=>{'
                'buttons.forEach((button)=>button.addEventListener("click",()=>setMode(button.dataset.previewMode||"web")));'
                '};'
                'bindButtons();'
                'const viewContainer=document.getElementById("htmlTextViewContainer");'
                'const codeScroll=document.getElementById("htmlTextCodeScroll");'
                'const verticalBiasWheel=(event)=>{'
                'if(!viewContainer||!codeScroll)return;'
                'const absX=Math.abs(event.deltaX||0);'
                'const absY=Math.abs(event.deltaY||0);'
                'if(absX<0.5||absY<=absX*1.2)return;'
                'event.preventDefault();'
                'viewContainer.scrollTop += event.deltaY;'
                '};'
                'codeScroll?.addEventListener("wheel",verticalBiasWheel,{passive:false});'
                'setMode("web");'
            )
            return (
                f'<!DOCTYPE html><html data-preview-mode="web"><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}'
                f'.html-preview-shell{{flex:1;min-height:0;display:flex;flex-direction:column;background:{embed_bg}}}'
                f'.html-preview-tabs{{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid {pane_line};background:rgba(20,20,19,0.88);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}}'
                '.html-preview-tab{appearance:none;border:1px solid rgba(255,255,255,0.08);background:transparent;color:rgba(252,252,252,0.68);border-radius:999px;padding:6px 12px;font:inherit;font-size:12px;line-height:1;cursor:pointer;transition:color .14s ease,border-color .14s ease,background .14s ease}'
                '.html-preview-tab.active{color:rgb(252,252,252);background:rgba(255,255,255,0.06);border-color:rgba(255,255,255,0.16)}'
                '.html-preview-panels{flex:1;min-height:0;position:relative}'
                '.html-preview-panel{display:none;width:100%;height:100%}'
                '.html-preview-panel.active{display:flex}'
                '.html-preview-panel-web iframe{width:100%;height:100%;border:0;background:white}'
                '.html-preview-panel-text{min-height:0;flex-direction:column}'
                '.html-preview-text-wrap{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;background:transparent;overscroll-behavior-y:contain;scrollbar-gutter:stable both-edges}'
                '.html-preview-text-scroll{width:100%;overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain;scrollbar-gutter:stable both-edges;padding-bottom:10px}'
                '.html-preview-text-table{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:360;font-synthesis-weight:none;font-synthesis-style:none;font-variation-settings:"wght" 360}'
                '.html-preview-text-table td{padding:0;vertical-align:top}'
                f'.html-preview-text-table .ln{{padding:0 8px 0 4px;min-width:{gutter_width}px;text-align:right;color:rgba(255,255,255,0.34);user-select:none;border-right:1px solid {pane_line};font-variant-numeric:tabular-nums;line-height:var(--message-text-line-height);font-family:var(--code-font-family);font-size:var(--message-text-size)}}'
                '.html-preview-text-table .lc{padding-left:12px;padding-right:min(7vw,52px)}'
                '.html-preview-text-table .lc pre{margin:0;min-height:var(--message-text-line-height);line-height:var(--message-text-line-height);font:inherit;white-space:pre}'
                '.html-preview-text-table tbody tr:last-child .ln,.html-preview-text-table tbody tr:last-child .lc pre{padding-bottom:min(26vh,200px)}'
                '</style></head>'
                f'<body>{header.format(icon="🌐")}<div class="html-preview-shell">{tabs_markup}'
                '<div class="html-preview-panels">'
                f'<div class="html-preview-panel html-preview-panel-web active" data-preview-panel="web"><iframe src="{raw_url}" title="{html_escape(filename)}" sandbox="allow-same-origin allow-scripts allow-forms allow-popups"></iframe></div>'
                f'<div class="html-preview-panel html-preview-panel-text" data-preview-panel="text"><div class="html-preview-text-wrap" id="htmlTextViewContainer"><div class="html-preview-text-scroll" id="htmlTextCodeScroll"><table class="html-preview-text-table" role="presentation"><tbody>{table_rows}</tbody></table></div></div></div>'
                f'</div><script>{toggle_js}</script></div></body></html>'
            )
        is_text_like = ext in self.EDITABLE_TEXT_EXTS or self._is_probably_text_file(full)
        if is_text_like and size > self.INLINE_PROGRESSIVE_PREVIEW_MAX_BYTES:
            chunk_bytes = self.PROGRESSIVE_TEXT_PREVIEW_CHUNK_BYTES
            border = "rgba(255,255,255,0.08)"
            muted = "rgba(252,252,252,0.72)"
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                "<style>"
                f"{base_css}"
                "body{display:flex;flex-direction:column}"
                f".shell{{display:flex;flex-direction:column;min-height:100%;background:{embed_bg}}}"
                f".wrap{{flex:1;min-height:100%;overflow:auto;padding:0 0 min(28vh,220px)}}"
                f".status{{position:sticky;top:0;z-index:1;padding:8px 14px;background:linear-gradient(to bottom, rgba(20,20,19,0.96), rgba(20,20,19,0.72));border-bottom:1px solid {border};color:{muted};font-size:12px}}"
                f'.viewer{{margin:0;padding:14px 16px min(26vh,200px);white-space:pre-wrap;word-break:break-word;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:360;color:{pane_fg};font-synthesis-weight:none;font-synthesis-style:none;font-variation-settings:"wght" 360}}'
                "</style></head><body>"
                "<div class=\"shell\">"
                "<div class=\"wrap\" id=\"wrap\">"
                "<div class=\"status\" id=\"status\">Loading preview...</div>"
                "<pre class=\"viewer\" id=\"viewer\"></pre>"
                "</div>"
                "<script>"
                f"const rawUrl={json.dumps(raw_url)};"
                f"const fileExt={json.dumps(ext)};"
                f"const totalBytes={size};"
                f"const chunkBytes={chunk_bytes};"
                "const wrap=document.getElementById('wrap');"
                "const viewer=document.getElementById('viewer');"
                "const status=document.getElementById('status');"
                "const decoder=new TextDecoder();"
                "let offset=0;let loading=false;let done=false;"
                "const setStatus=(text)=>{status.textContent=text;};"
                "const escapeHtml=(text)=>String(text||'').replace(/[&<>\"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[char]||char));"
                "const applyOutsideTags=(value,pattern,replacement)=>value.split(/(<[^>]*>)/g).map((part)=>part.startsWith('<')?part:part.replace(pattern,replacement)).join('');"
                "const highlightText=(text,ext)=>{"
                " let out=escapeHtml(text);"
                " if(['.py','.sh','.yaml','.yml'].includes(ext)){out=out.replace(/(^[ \\t]*#[^\\n]*)/gm,'<span style=\"color:#5c6370\">$1</span>');}"
                " else if(['.js','.ts','.css','.sql','.json'].includes(ext)){out=out.replace(/(\\/\\/[^\\n]*)/g,'<span style=\"color:#5c6370\">$1</span>');}"
                " else if(ext==='.tex'){out=out.replace(/(^[ \\t]*%[^\\n]*)/gm,'<span style=\"color:#5c6370\">$1</span>');}"
                " out=applyOutsideTags(out,/(\"(?:[^\"\\\\<\\n]|\\\\.)*\"|'(?:[^'\\\\<\\n]|\\\\.)*')/g,'<span style=\"color:#98c379\">$1</span>');"
                " out=applyOutsideTags(out,/(^|[^\\w#])(-?\\d+(?:\\.\\d+)?)/g,'$1<span style=\"color:#d19a66\">$2</span>');"
                " if(['.json','.yaml','.yml'].includes(ext)){out=applyOutsideTags(out,/(^[ \\t-]*)([A-Za-z_][\\w.-]*)(\\s*:)/gm,'$1<span style=\"color:#56b6c2\">$2</span>$3');}"
                " if(ext==='.tex'){out=applyOutsideTags(out,/(\\\\[A-Za-z@]+)/g,'<span style=\"color:#e06c75\">$1</span>');}"
                " if(ext==='.html'){out=applyOutsideTags(out,/(&lt;\\/?)([A-Za-z][\\w:-]*)/g,'$1<span style=\"color:#e06c75\">$2</span>');out=applyOutsideTags(out,/([A-Za-z_:][\\w:.-]*)(=)(&quot;.*?&quot;)/g,'<span style=\"color:#56b6c2\">$1</span>$2<span style=\"color:#98c379\">$3</span>');}"
                " if(ext==='.css'){out=applyOutsideTags(out,/(^[ \\t]*)([.#]?[A-Za-z_-][\\w:-]*)(\\s*\\{)/gm,'$1<span style=\"color:#e06c75\">$2</span>$3');out=applyOutsideTags(out,/([A-Za-z-]+)(\\s*:)/g,'<span style=\"color:#56b6c2\">$1</span>$2');}"
                " if(['.py','.js','.sh','.sql'].includes(ext)){out=applyOutsideTags(out,/(^[ \\t]*@[\\w.]+)/gm,'<span style=\"color:#e06c75\">$1</span>');}"
                " out=applyOutsideTags(out,/\\b(def|class|import|from|return|if|else|elif|for|while|try|except|with|as|yield|await|async|function|const|let|var|type|interface|enum|public|private|protected|static|readonly|do|switch|case|default|break|continue|new|delete|typeof|instanceof|void|this|super|in|of|null|undefined|true|false)\\b/g,'<span style=\"color:#c678dd\">$1</span>');"
                " out=applyOutsideTags(out,/\\b(str|int|float|bool|list|dict|tuple|set|None|self|cls|SELECT|FROM|WHERE|GROUP|ORDER|BY|JOIN|LEFT|RIGHT|INNER|OUTER|LIMIT|INSERT|UPDATE|DELETE|CREATE|TABLE|VALUES)\\b/g,'<span style=\"color:#e5c07b\">$1</span>');"
                " out=applyOutsideTags(out,/\\b(print|len|range|echo|printf|console|log)\\b/g,'<span style=\"color:#56b6c2\">$1</span>');"
                " out=applyOutsideTags(out,/\\b([A-Za-z_][\\w]*)(?=\\()/g,'<span style=\"color:#61afef\">$1</span>');"
                " out=applyOutsideTags(out,/([{}()[\\],.:;=+\\-/*<>])/g,'<span style=\"color:#7f848e\">$1</span>');"
                " return out;"
                "};"
                "const maybeLoad=()=>{if(done||loading)return;if((wrap.scrollTop+wrap.clientHeight)>=(wrap.scrollHeight-320)){void loadNext();}};"
                "const loadNext=async()=>{"
                " if(done||loading)return;"
                " loading=true;"
                " const start=offset;const end=Math.min(totalBytes-1,start+chunkBytes-1);"
                " setStatus(`Loading ${Math.min(totalBytes,end+1).toLocaleString()} / ${totalBytes.toLocaleString()} bytes...`);"
                " try{"
                "  const res=await fetch(rawUrl,{cache:'no-store',headers:{Range:`bytes=${start}-${end}`}});"
                "  if(!(res.ok||res.status===206)) throw new Error('preview failed');"
                "  const buf=await res.arrayBuffer();"
                "  if(buf.byteLength===0){done=true;setStatus(`Loaded ${offset.toLocaleString()} / ${totalBytes.toLocaleString()} bytes`);return;}"
                "  offset += buf.byteLength;"
                "  const finalChunk = offset >= totalBytes;"
                "  const textChunk=decoder.decode(buf,{stream:!finalChunk});"
                "  viewer.insertAdjacentHTML('beforeend',highlightText(textChunk,fileExt));"
                "  if(finalChunk){const tail=decoder.decode();if(tail)viewer.insertAdjacentHTML('beforeend',highlightText(tail,fileExt));done=true;setStatus(`Loaded ${totalBytes.toLocaleString()} bytes`);}else{setStatus(`Loaded ${offset.toLocaleString()} / ${totalBytes.toLocaleString()} bytes`);}"
                " }catch(err){setStatus('Preview load failed.');}"
                " finally{loading=false;if(!done && wrap.scrollHeight <= wrap.clientHeight + 48){setTimeout(maybeLoad,0);}}"
                "};"
                "wrap.addEventListener('scroll',maybeLoad,{passive:true});"
                "window.addEventListener('resize',maybeLoad,{passive:true});"
                "void loadNext();"
                "</script>"
                "</div></body></html>"
            )
        if ext in self.TEXT_EXTS:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            table_rows, gutter_width = build_text_table_markup(content, text_ext=ext)
            height = "100vh" if embed else "calc(100vh - 43px)"
            vertical_bias_js = (
                'const viewContainer=document.getElementById("viewContainer");'
                'const codeScroll=document.getElementById("codeScroll");'
                'const verticalBiasWheel=(event)=>{'
                'if(!viewContainer||!codeScroll)return;'
                'const absX=Math.abs(event.deltaX||0);'
                'const absY=Math.abs(event.deltaY||0);'
                'if(absX<0.5||absY<=absX*1.2)return;'
                'event.preventDefault();'
                'viewContainer.scrollTop += event.deltaY;'
                '};'
                'codeScroll?.addEventListener("wheel",verticalBiasWheel,{passive:false});'
            )
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}body{{background:{embed_bg};color:{pane_fg}}}'
                f'.hdr{{background:{embed_bg};border-bottom-color:{pane_line}}}'
                f'.fn{{color:{pane_fg}}}.fp{{color:{pane_muted}}}'
                f'.view-container{{height:{height};overflow-y:auto;overflow-x:hidden;background:{embed_bg};overscroll-behavior-y:contain;scrollbar-gutter:stable both-edges}}'
                '.code-scroll{width:100%;overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain;scrollbar-gutter:stable both-edges;padding-bottom:10px}'
                '.code-table{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;'
                'font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:360;'
                'font-synthesis-weight:none;font-synthesis-style:none;font-variation-settings:"wght" 360}'
                '.code-table td{padding:0;vertical-align:top}'
                f'.code-table .ln{{padding:0 8px 0 4px;min-width:{gutter_width}px;text-align:right;color:rgba(255,255,255,0.34);'
                f'user-select:none;border-right:1px solid {pane_line};font-variant-numeric:tabular-nums;line-height:var(--message-text-line-height);font-family:var(--code-font-family);font-size:var(--message-text-size)}}'
                '.code-table .lc{padding-left:12px;padding-right:min(7vw,52px)}'
                '.code-table .lc pre{margin:0;min-height:var(--message-text-line-height);line-height:var(--message-text-line-height);font:inherit;white-space:pre}'
                '.code-table tbody tr:last-child .ln,.code-table tbody tr:last-child .lc pre{padding-bottom:min(26vh,200px)}'
                '</style></head>'
                f'<body>{header.format(icon="📄")}'
                f'<div class="view-container" id="viewContainer"><div class="code-scroll" id="codeScroll"><table class="code-table" role="presentation"><tbody>{table_rows}</tbody></table></div></div><script>{vertical_bias_js}</script></body></html>'
            )
        if ext == ".md":
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            content_json = json.dumps(content)
            rel_json = json.dumps(rel.replace("\\", "/"))
            prefix_json = json.dumps(prefix)
            has_fenced_code = "```" in content
            has_math = bool(re.search(r"(\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$\$[\s\S]+?\$\$|(?<!\$)\$[^$\n]+\$)", content))
            prism_aliases = {
                "py": "python",
                "python": "python",
                "js": "javascript",
                "javascript": "javascript",
                "node": "javascript",
                "ts": "typescript",
                "typescript": "typescript",
                "tsx": "typescript",
                "sh": "bash",
                "bash": "bash",
                "shell": "bash",
                "zsh": "bash",
                "json": "json",
                "yaml": "yaml",
                "yml": "yaml",
                "css": "css",
                "html": "markup",
                "xml": "markup",
                "svg": "markup",
                "sql": "sql",
            }
            prism_langs: list[str] = []
            if has_fenced_code:
                for match in re.finditer(r"```([^\n`]*)", content):
                    raw_lang = str(match.group(1) or "").strip().split(" ", 1)[0].strip().lower()
                    if not raw_lang:
                        continue
                    resolved_lang = prism_aliases.get(raw_lang)
                    if not resolved_lang or resolved_lang in prism_langs:
                        continue
                    prism_langs.append(resolved_lang)
            markdown_head_tags = ['<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>']
            if has_fenced_code:
                markdown_head_tags.extend([
                    '<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>',
                ])
                markdown_head_tags.extend(
                    f'<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-{lang}.min.js"></script>'
                    for lang in prism_langs
                )
            if has_math:
                markdown_head_tags.extend([
                    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">',
                    '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>',
                    '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>',
                ])
            markdown_head_libs = "".join(markdown_head_tags)
            return (
                f'<!DOCTYPE html><html data-preview-theme="dark" data-agent-font-mode="{agent_font_mode}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>{html_escape(filename)}</title>'
                f'{markdown_head_libs}'
                f'<style>{base_css}'
                f':root{{--bg:{pane_bg};--text:{pane_fg};--meta:rgba(252,252,252,0.62);--line:{pane_line};--line-strong:rgba(255,255,255,0.12);--inline-code-fg:rgb(196,201,209);--code-block-bg:rgba(255,255,255,0.03);--code-block-border:rgba(255,255,255,0.08);--code-block-shadow:none;--code-copy-bg:rgba(0,0,0,0.34);--code-copy-hover-bg:rgba(255,255,255,0.06);--message-text-size:{resolved_text_size}px;--message-text-line-height:{resolved_line_height}px;--link:#58a6ff;--agent-font-family:{agent_font_family};}}'
                ':root[data-preview-theme="light"]{--bg:rgb(255,255,255);--text:rgb(20,20,19);--meta:rgba(20,20,19,0.56);--line:rgba(20,20,19,0.10);--line-strong:rgba(20,20,19,0.18);--inline-code-fg:rgb(52,52,52);--code-block-bg:rgba(20,20,19,0.035);--code-block-border:rgba(20,20,19,0.08);--code-copy-bg:rgba(255,255,255,0.88);--code-copy-hover-bg:rgba(20,20,19,0.06);--link:#245bdb}'
                'body{background:var(--bg);color:var(--text)}'
                '.md-preview-shell{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;background:var(--bg)}'
                '.md-body{padding:14px 16px 18px;flex:1;min-width:0;overflow-x:hidden;font-family:var(--agent-font-family);font-style:normal;font-size:var(--message-text-size,13px);line-height:var(--message-text-line-height,22px);font-weight:360;color:var(--text);font-synthesis-weight:none;font-synthesis-style:none;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;font-optical-sizing:auto;font-variation-settings:"wght" 360}'
                'html[data-agent-font-mode="gothic"] .md-body{letter-spacing:-0.01em;font-variation-settings:"wght" 360,"opsz" 16}'
                '.md-body>*:first-child{margin-top:0}.md-body>*:last-child{margin-bottom:0}'
                '.md-body,.md-body p,.md-body li,.md-body li p,.md-body blockquote,.md-body blockquote p{white-space:normal;overflow-wrap:anywhere;word-break:normal}'
                '.md-body p{margin:0 0 .6em}'
                '.md-body h1,.md-body h2,.md-body h3,.md-body h4{margin:.8em 0 .3em;font-weight:600;font-variation-settings:"wght" 530;font-synthesis:weight;line-height:1.2}'
                'html[data-agent-font-mode="gothic"] .md-body h1,html[data-agent-font-mode="gothic"] .md-body h2,html[data-agent-font-mode="gothic"] .md-body h3,html[data-agent-font-mode="gothic"] .md-body h4{font-weight:700;font-variation-settings:"wght" 700,"opsz" 16}'
                '.md-body h1{font-size:22px}.md-body h2{font-size:18px}.md-body h3{font-size:1.05em}.md-body h4{font-size:1em}'
                '.md-body ul,.md-body ol{margin:.4em 0 .6em;padding-left:1.5em}.md-body li{margin:.15em 0;line-height:calc(var(--message-text-line-height,22px) + 2px)}.md-body li p{margin:0}'
                '.md-body :not(pre)>code{font-family:var(--code-font-family);font-style:normal;font-size:0.92em;font-weight:450;font-synthesis-weight:none;font-variation-settings:normal;letter-spacing:normal;color:var(--inline-code-fg);line-height:inherit;background:transparent;border:none;border-radius:0;padding:0}'
                '.katex{font-family:KaTeX_Main,Times New Roman,serif;font-size:19px;font-weight:400;line-height:23px}'
                '.table-scroll{display:block;width:100%;max-width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;margin:.5em 0}.table-scroll>table{width:100%;margin:0}'
                '.katex-display{display:block;margin:1.2em 0;width:100%;max-width:100%;padding-inline:0;overflow-x:auto;overflow-y:hidden;text-align:left;-webkit-overflow-scrolling:touch}.katex-display>.katex{display:table;width:max-content;max-width:none;margin:0 auto}'
                '.md-body pre{display:block;width:100%;max-width:100%;box-sizing:border-box;position:relative;background:var(--code-block-bg);border:1px solid var(--code-block-border);border-radius:14px;padding:14px 16px;margin:0;overflow-x:auto;overflow-y:hidden;white-space:pre;word-break:normal;box-shadow:var(--code-block-shadow);-webkit-overflow-scrolling:touch}'
                '.md-body .code-block-wrap{position:relative;display:block;margin:14px 0;overflow-x:hidden}'
                '.md-body .code-block-wrap .code-copy-btn{position:absolute;top:8px;right:8px;z-index:1;width:30px;height:30px;padding:0;border:1px solid var(--code-block-border);border-radius:9px;background:var(--code-copy-bg);color:var(--meta);cursor:pointer;display:flex;align-items:center;justify-content:center;opacity:0;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);transition:opacity .15s,background .15s,color .15s,border-color .15s}'
                '.md-body .code-block-wrap:hover .code-copy-btn{opacity:1}@media (pointer:coarse){.md-body .code-block-wrap .code-copy-btn{opacity:.72}}'
                '.md-body .code-block-wrap .code-copy-btn:hover{background:var(--code-copy-hover-bg);color:var(--text);border-color:var(--line-strong)}.md-body .code-block-wrap .code-copy-btn svg{width:15px;height:15px}'
                '.md-body pre code{font-family:var(--code-font-family);font-style:normal;font-size:var(--message-text-size);font-weight:360;font-synthesis-weight:none;font-variation-settings:"wght" 360;letter-spacing:normal;line-height:var(--message-text-line-height);color:var(--text);background:none;border:none;padding:0;border-radius:0;white-space:pre;word-break:normal;overflow-wrap:normal}'
                '.md-body pre code .token.comment,.md-body pre code .token.prolog,.md-body pre code .token.doctype,.md-body pre code .token.cdata{color:rgb(100,110,130)}'
                '.md-body pre code .token.punctuation{color:rgb(150,160,175)}'
                '.md-body pre code .token.property,.md-body pre code .token.tag,.md-body pre code .token.boolean,.md-body pre code .token.number,.md-body pre code .token.constant,.md-body pre code .token.symbol{color:rgb(140,170,210)}'
                '.md-body pre code .token.selector,.md-body pre code .token.attr-name,.md-body pre code .token.string,.md-body pre code .token.char,.md-body pre code .token.builtin{color:rgb(160,190,200)}'
                '.md-body pre code .token.operator,.md-body pre code .token.entity,.md-body pre code .token.url,.md-body pre code .token.variable{color:rgb(170,180,195)}'
                '.md-body pre code .token.atrule,.md-body pre code .token.attr-value,.md-body pre code .token.keyword{color:rgb(130,160,200)}'
                '.md-body pre code .token.function,.md-body pre code .token.class-name{color:rgb(175,195,220)}'
                '.md-body pre code .token.regex,.md-body pre code .token.important{color:rgb(190,170,140)}'
                '.md-body pre code .token.decorator{color:rgb(140,170,210)}'
                ':root[data-preview-theme="light"] .md-body pre code .token.comment,:root[data-preview-theme="light"] .md-body pre code .token.prolog,:root[data-preview-theme="light"] .md-body pre code .token.doctype,:root[data-preview-theme="light"] .md-body pre code .token.cdata{color:rgb(126,132,145)}'
                ':root[data-preview-theme="light"] .md-body pre code .token.punctuation{color:rgb(108,116,128)}'
                ':root[data-preview-theme="light"] .md-body pre code .token.property,:root[data-preview-theme="light"] .md-body pre code .token.tag,:root[data-preview-theme="light"] .md-body pre code .token.boolean,:root[data-preview-theme="light"] .md-body pre code .token.number,:root[data-preview-theme="light"] .md-body pre code .token.constant,:root[data-preview-theme="light"] .md-body pre code .token.symbol{color:rgb(48,92,176)}'
                ':root[data-preview-theme="light"] .md-body pre code .token.selector,:root[data-preview-theme="light"] .md-body pre code .token.attr-name,:root[data-preview-theme="light"] .md-body pre code .token.string,:root[data-preview-theme="light"] .md-body pre code .token.char,:root[data-preview-theme="light"] .md-body pre code .token.builtin{color:rgb(40,122,113)}'
                ':root[data-preview-theme="light"] .md-body pre code .token.operator,:root[data-preview-theme="light"] .md-body pre code .token.entity,:root[data-preview-theme="light"] .md-body pre code .token.url,:root[data-preview-theme="light"] .md-body pre code .token.variable{color:rgb(88,95,104)}'
                ':root[data-preview-theme="light"] .md-body pre code .token.atrule,:root[data-preview-theme="light"] .md-body pre code .token.attr-value,:root[data-preview-theme="light"] .md-body pre code .token.keyword{color:rgb(86,76,176)}'
                ':root[data-preview-theme="light"] .md-body pre code .token.function,:root[data-preview-theme="light"] .md-body pre code .token.class-name{color:rgb(23,87,152)}'
                ':root[data-preview-theme="light"] .md-body pre code .token.regex,:root[data-preview-theme="light"] .md-body pre code .token.important{color:rgb(149,92,35)}'
                ':root[data-preview-theme="light"] .md-body pre code .token.decorator{color:rgb(48,92,176)}'
                '.md-body code.language-diff{display:flex;flex-direction:column;gap:0}'
                '.md-body .diff-add{background:rgb(2,40,2);color:rgb(250,230,100);display:block;margin:0 -16px;padding:0 16px;line-height:20px}.md-body .diff-add .diff-sign{color:rgb(34,197,94)}'
                '.md-body .diff-del{background:rgb(61,1,0);display:block;margin:0 -16px;padding:0 16px;line-height:20px}.md-body .diff-del .diff-sign{color:rgb(239,68,68)}'
                ':root[data-preview-theme="light"] .md-body .diff-add{background:rgb(233,247,233);color:rgb(41,73,41)}:root[data-preview-theme="light"] .md-body .diff-add .diff-sign{color:rgb(38,134,74)}'
                ':root[data-preview-theme="light"] .md-body .diff-del{background:rgb(252,236,236);color:rgb(104,39,39)}:root[data-preview-theme="light"] .md-body .diff-del .diff-sign{color:rgb(186,63,63)}'
                '.md-body blockquote{border-left:3px solid rgba(255,255,255,0.2);margin:.5em 0;padding:.3em .8em;opacity:.85}'
                '.md-body hr{border:none;border-top:1px solid var(--line);margin:.8em 0}'
                '.md-body img{display:block;max-width:100%;max-height:60vh;width:auto;height:auto;margin:12px 0;border-radius:10px}'
                '.md-body table{display:table;table-layout:auto;border-collapse:collapse;width:100%;margin:.5em 0;font-size:var(--message-text-size,13px);line-height:21px}'
                '.md-body th,.md-body td{white-space:nowrap;border-top:1.5px solid rgba(255,255,255,0.12);border-bottom:1.5px solid rgba(255,255,255,0.12);border-left:none;border-right:none;padding:7.5px 12px !important;text-align:left;font-size:var(--message-text-size,13px);line-height:21px}'
                '.md-body th{background:transparent;font-weight:530;border-top:none;border-bottom-color:rgba(255,255,255,0.28)}.md-body td{font-weight:360}'
                ':root[data-preview-theme="light"] .md-body blockquote{border-left-color:rgba(20,20,19,0.18);opacity:1}'
                ':root[data-preview-theme="light"] .md-body th,:root[data-preview-theme="light"] .md-body td{border-top-color:rgba(20,20,19,0.12);border-bottom-color:rgba(20,20,19,0.12)}'
                ':root[data-preview-theme="light"] .md-body th{border-bottom-color:rgba(20,20,19,0.22)}'
                '.md-body a{color:var(--link);text-decoration:none}.md-body a:hover{text-decoration:underline}.md-body strong{font-weight:530}.md-body em{font-style:italic}'
                '</style></head>'
                f'<body>{header.format(icon="📝")}<div class="md-preview-shell"><div class="md-body" id="out"></div></div>'
                f'''<script>
const __mdText = {content_json};
const __mdRel = {rel_json};
const __fileBase = {prefix_json};
const __rawBase = `${{__fileBase}}/file-raw?path=`;
const __root = document.documentElement;
const __isExternalSrc = (src) => /^(https?:|data:|blob:|file:|\\/\\/)/i.test(src || "");
const __normalizeMdPath = (baseRel, src) => {{
  const cleanSrc = String(src || "").trim();
  if (!cleanSrc || __isExternalSrc(cleanSrc) || cleanSrc.startsWith("#")) return cleanSrc;
  const withoutQuery = cleanSrc.split(/[?#]/, 1)[0];
  const baseParts = String(baseRel || "").split("/").slice(0, -1);
  const rawParts = withoutQuery.startsWith("/")
    ? withoutQuery.replace(/^\\/+/, "").split("/")
    : baseParts.concat(withoutQuery.split("/"));
  const out = [];
  for (const part of rawParts) {{
    if (!part || part === ".") continue;
    if (part === "..") {{
      if (out.length) out.pop();
      continue;
    }}
    out.push(part);
  }}
  return out.join("/");
}};
const __rewriteMarkdownImages = (root) => {{
  root.querySelectorAll("img").forEach((img) => {{
    const src = img.getAttribute("src") || "";
    if (!src || __isExternalSrc(src)) return;
    const resolved = __normalizeMdPath(__mdRel, src);
    if (!resolved) return;
    img.setAttribute("src", __rawBase + encodeURIComponent(resolved));
  }});
}};
const escapeHtml = (value) => String(value || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const mathRenderOptions = {{
  delimiters: [
    {{left: "$$", right: "$$", display: true}},
    {{left: "$", right: "$", display: false}},
    {{left: "\\\\[", right: "\\\\]", display: true}}
  ],
  ignoredClasses: ["no-math"],
  throwOnError: false
}};
const renderMarkdown = (text) => {{
  if (typeof marked === "undefined") return "<pre>" + escapeHtml(text) + "</pre>";
  try {{
    const mathBlocks = [];
    let placeholderCount = 0;
    const codeBlocks = [];
    let codeCount = 0;
    let processedText = String(text || "").replace(/(```[\\s\\S]*?```|`[^`\\n]+`)/g, (match) => {{
      const id = `code-placeholder-${{codeCount++}}`;
      codeBlocks.push({{ id, content: match }});
      return `\\x00CODE:${{id}}\\x00`;
    }});
    processedText = processedText.replace(/(?<!\\$)\\$([A-Z_][A-Z0-9_]+)/g, '<span class="no-math">&#36;$1</span>');
    processedText = processedText.replace(/\\$([{{(]][^}})\\n]*[}})])/g, '<span class="no-math">&#36;$1</span>');
    processedText = processedText.replace(/(\\\\\\[[\\s\\S]+?\\\\\\]|\\\\\\([\\s\\S]+?\\\\\\)|\\$\\$[\\s\\S]+?\\$\\$|\\$[\\s\\S]+?\\$)/g, (match) => {{
      const id = `math-placeholder-${{placeholderCount++}}`;
      mathBlocks.push({{ id, content: match }});
      return `<span class="MATH_SAFE_BLOCK" data-id="${{id}}"></span>`;
    }});
    processedText = processedText.replace(/\\x00CODE:(code-placeholder-\\d+)\\x00/g, (_, id) => {{
      const block = codeBlocks.find((entry) => entry.id === id);
      return block ? block.content : "";
    }});
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = marked.parse(processedText, {{ breaks: true, gfm: true }});
    tempDiv.querySelectorAll(".MATH_SAFE_BLOCK").forEach((span) => {{
      const block = mathBlocks.find((entry) => entry.id === span.dataset.id);
      if (block) span.outerHTML = block.content;
    }});
    if (mathBlocks.length) {{
      const marker = document.createElement("span");
      marker.className = "math-render-needed";
      marker.hidden = true;
      tempDiv.prepend(marker);
    }}
    if (typeof Prism !== "undefined") {{
      tempDiv.querySelectorAll('code[class*="language-"]').forEach((codeEl) => {{
        if (codeEl.classList.contains("language-diff")) return;
        Prism.highlightElement(codeEl);
      }});
    }}
    tempDiv.querySelectorAll("code.language-diff").forEach((codeEl) => {{
      const raw = codeEl.textContent || "";
      codeEl.innerHTML = raw.split("\\n").map((line) => {{
        if (line.startsWith("+")) return `<span class="diff-add"><span class="diff-sign">+</span>${{escapeHtml(line.slice(1))}}</span>`;
        if (line.startsWith("-")) return `<span class="diff-del"><span class="diff-sign">-</span>${{escapeHtml(line.slice(1))}}</span>`;
        return escapeHtml(line);
      }}).join("\\n");
    }});
    const copySvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    tempDiv.querySelectorAll("pre").forEach((pre) => {{
      const wrap = document.createElement("div");
      wrap.className = "code-block-wrap";
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);
      wrap.insertAdjacentHTML("beforeend", `<button class="code-copy-btn" type="button" title="Copy">${{copySvg}}</button>`);
    }});
    return tempDiv.innerHTML;
  }} catch (_) {{
    return "<pre>" + escapeHtml(text) + "</pre>";
  }}
}};
const ensureWideTables = (scope = document) => {{
  scope.querySelectorAll(".md-body table").forEach((table) => {{
    if (table.closest(".table-scroll")) return;
    const parent = table.parentNode;
    if (!parent) return;
    const scroll = document.createElement("div");
    scroll.className = "table-scroll";
    parent.insertBefore(scroll, table);
    scroll.appendChild(table);
  }});
}};
const applyPreviewTheme = (theme) => {{
  const nextTheme = theme === "light" ? "light" : "dark";
  __root.setAttribute("data-preview-theme", nextTheme);
}};
window.__agentIndexApplyPreviewTheme = applyPreviewTheme;
const renderMathInScope = (scope) => {{
  if (!scope || !scope.querySelector(".math-render-needed") || typeof renderMathInElement !== "function") return;
  renderMathInElement(scope, mathRenderOptions);
  scope.querySelectorAll(".math-render-needed").forEach((marker) => marker.remove());
}};
const copyText = async (text) => {{
  if (navigator.clipboard?.writeText) {{
    await navigator.clipboard.writeText(text);
    return;
  }}
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "absolute";
  area.style.left = "-9999px";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}};
const codeCopySvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
const codeCheckSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
document.addEventListener("click", async (event) => {{
  const btn = event.target.closest(".code-copy-btn");
  if (!btn) return;
  const wrap = btn.closest(".code-block-wrap");
  if (!wrap) return;
  const code = wrap.querySelector("code") || wrap.querySelector("pre") || wrap;
  try {{
    await copyText(code.textContent || "");
    btn.innerHTML = codeCheckSvg;
    btn.title = "Copied";
    setTimeout(() => {{ 
      btn.innerHTML = codeCopySvg;
      btn.title = "Copy"; 
    }}, 1500);
  }} catch (_) {{}}
}});
window.addEventListener("message", (event) => {{
  const data = event?.data;
  if (!data || data.type !== "agent-index-file-preview-theme") return;
  applyPreviewTheme(data.theme);
}});
const out = document.getElementById("out");
out.innerHTML = renderMarkdown(__mdText);
__rewriteMarkdownImages(out);
ensureWideTables(out);
renderMathInScope(out);
applyPreviewTheme("dark");
</script></body></html>'''
            )

        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        escaped = html_escape(content)
        pre_height = "100vh" if embed else "calc(100vh - 43px)"
        return (
            f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}body{{background:{embed_bg};color:{pane_fg};font-family:var(--code-font-family);font-size:13px}}'
            f'.hdr{{padding:10px 16px;background:{embed_bg};border-bottom:1px solid {pane_line};display:flex;align-items:center;gap:8px}}'
            f'.fn{{font-weight:700;font-size:14px;color:{pane_fg}}}.fp{{color:{pane_muted};font-size:12px}}'
            f'pre{{margin:0;padding:16px;white-space:pre;overflow:auto;height:{pre_height};background:{embed_bg}}}</style></head>'
            f'<body>{header.format(icon="📄")}<pre>{escaped}</pre></body></html>'
        )
