from __future__ import annotations

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


class FileRuntime:
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
    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache"}

    def __init__(self, *, workspace: str | Path):
        self.workspace = os.path.normpath(str(workspace))

    def _resolve_path(self, rel: str, *, allow_workspace_root: bool = False) -> str:
        rel = rel or ""
        if os.path.isabs(rel):
            full = os.path.normpath(rel)
        else:
            full = os.path.normpath(os.path.join(self.workspace, rel.lstrip("/")))
        if allow_workspace_root:
            if full != self.workspace and not full.startswith(self.workspace + os.sep):
                raise PermissionError("outside workspace")
        elif not full.startswith(self.workspace + os.sep):
            raise PermissionError("outside workspace")
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
        if ext in {".html", ".htm", ".pdf"}:
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
        except Exception:
            return False
        return result.returncode == 0

    @staticmethod
    def _editor_command(full: str) -> tuple[list[str], str]:
        configured = (os.environ.get("MULTIAGENT_EXTERNAL_EDITOR") or "").strip()
        if configured:
            if "{path}" in configured:
                return shlex.split(configured.format(path=full)), "custom"
            return shlex.split(configured) + [full], "custom"
        browser_cmd = FileRuntime._pdf_browser_command(full) if full.lower().endswith((".html", ".htm", ".pdf")) else None
        if browser_cmd:
            return browser_cmd, "system"
        if sys.platform == "darwin":
            if FileRuntime._macos_app_exists("CotEditor"):
                return ["open", "-na", "CotEditor", full], "lightweight"
            if FileRuntime._macos_app_exists("Sublime Text"):
                return ["open", "-na", "Sublime Text", full], "lightweight"
            if FileRuntime._macos_app_exists("TextMate"):
                return ["open", "-na", "TextMate", full], "lightweight"
            if FileRuntime._macos_app_exists("BBEdit"):
                return ["open", "-na", "BBEdit", full], "lightweight"
        if shutil.which("code"):
            return ["code", "--new-window", "-g", full], "vscode"
        if sys.platform == "darwin":
            return ["open", "-na", "Visual Studio Code", "--args", "--new-window", "--goto", full], "vscode"
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
            except Exception:
                time.sleep(0.15)

    @staticmethod
    def _shrink_browser_window(app_name: str, process_name: str):
        if sys.platform != "darwin" or not shutil.which("osascript"):
            return
        script = f'''
delay 0.35
tell application "{app_name}" to activate
delay 0.2
tell application "System Events"
    tell process "{process_name}"
        if (count of windows) > 0 then
            set position of front window to {{120, 88}}
            set size of front window to {{720, 1440}}
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
            except Exception:
                time.sleep(0.15)

    def open_in_editor(self, rel: str):
        full = self._resolve_path(rel, allow_workspace_root=True)
        if not os.path.isfile(full):
            raise FileNotFoundError(full)
        ext = os.path.splitext(full)[1].lower()
        if ext not in self.EDITABLE_TEXT_EXTS and ext not in {".html", ".htm", ".pdf"} and not self._is_probably_text_file(full):
            raise ValueError("Only text files can be opened in an external editor.")
        cmd, mode = self._editor_command(full)
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if mode == "vscode":
            self._shrink_vscode_window()
        elif mode == "browser":
            app_name = "Google Chrome"
            process_name = "Google Chrome"
            if any(part == "Chromium" for part in cmd):
                app_name = "Chromium"
                process_name = "Chromium"
            self._shrink_browser_window(app_name, process_name)
        return {"ok": True, "path": rel}

    def list_files(self):
        files = []
        for root, dirs, filenames in os.walk(self.workspace):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in self.SKIP_DIRS)
            depth = root[len(self.workspace):].count(os.sep)
            if depth >= 3:
                dirs.clear()
            for filename in sorted(filenames):
                if filename.startswith("."):
                    continue
                rel = os.path.join(root, filename)[len(self.workspace):].lstrip(os.sep)
                files.append(rel)
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

    def file_view(self, rel: str, *, embed: bool = False, base_path: str = "") -> str:
        full = self._resolve_path(rel)
        if not os.path.exists(full):
            raise FileNotFoundError(full)

        ext = os.path.splitext(rel)[1].lower()
        filename = os.path.basename(rel)
        prefix = (base_path or "").rstrip("/")
        raw_url = f"{prefix}/file-raw?path={url_quote(rel)}"
        pane_bg = "rgb(20, 20, 19)"
        embed_bg = "transparent" if embed else pane_bg
        pane_fg = "rgb(252, 252, 252)"
        pane_muted = "rgb(252, 252, 252)"
        pane_line = "rgba(255,255,255,0.08)"
        base_css = (
            f":root{{color-scheme: dark;}}*{{box-sizing:border-box}}"
            f"html,body{{margin:0;background:{embed_bg};color:{pane_fg};font-family:sans-serif;display:flex;flex-direction:column;height:100vh}}"
            f".hdr{{padding:10px 16px;background:{embed_bg};border-bottom:0.5px solid {pane_line};display:flex;align-items:center;gap:8px;flex-shrink:0}}"
            f".fn{{font-weight:700;font-size:14px;color:{pane_fg}}}.fp{{color:{pane_muted};font-size:12px}}"
        )
        header = "" if embed else (
            f'<div class="hdr"><span>{{icon}}</span><span class="fn">{html_escape(filename)}</span>'
            f'<span class="fp">{html_escape(rel)}</span></div>'
        )

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
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}.wrap{{flex:1;display:flex;align-items:center;justify-content:center;padding:32px;background:{embed_bg}}}'
                f'audio{{width:100%;max-width:500px}}</style></head>'
                f'<body>{header.format(icon="🎵")}<div class="wrap"><audio controls src="{raw_url}"></audio></div></body></html>'
            )
        if ext in self.TEXT_EXTS:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            escaped = self._highlight_text(
                html_escape(content),
                ext,
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
            height = "100vh" if embed else "calc(100vh - 43px)"
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}body{{background:{embed_bg};color:{pane_fg}}}.hdr{{background:{embed_bg};border-bottom-color:{pane_line}}}'
                f'.fn{{color:{pane_fg}}}.fp{{color:{pane_muted}}}pre{{margin:0;padding:16px;white-space:pre;overflow:auto;height:{height};'
                f'font-family:"SF Mono","Fira Code",monospace;font-size:13px;line-height:1.5;background:{embed_bg};color:{pane_fg}}}</style></head>'
                f'<body>{header.format(icon="📄")}<pre>{escaped}</pre></body></html>'
            )
        if ext == ".md":
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            escaped_js = content.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
            md_height = "100vh" if embed else "calc(100vh - 43px)"
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                '<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>'
                f'<style>{base_css}.md{{padding:24px 32px;max-width:860px;overflow:auto;height:{md_height};font-family:-apple-system,sans-serif;font-size:15px;line-height:1.7;background:{embed_bg}}}'
                f'h1,h2{{border-bottom:1px solid {pane_line};padding-bottom:.3em}}'
                'code{font-family:"SF Mono",monospace;font-size:.88em;background:rgba(255,255,255,.09);border-radius:4px;padding:1px 5px}'
                'pre{background:rgba(0,0,0,0.18);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:12px 16px;overflow-x:auto}'
                'pre code{background:none;padding:0}a{color:#58a6ff}'
                'table{border-collapse:collapse;width:100%;font-size:14px;line-height:24px}'
                f'th,td{{border-top:1.5px solid {pane_line};border-bottom:1.5px solid {pane_line};border-left:none;border-right:none;padding:7.5px 4px;font-size:14px;line-height:24px}}'
                'th{background:transparent;font-weight:530;border-top:none;border-bottom-color:rgba(255,255,255,0.28)}'
                'td{font-weight:360}</style></head>'
                f'<body>{header.format(icon="📝")}<div class="md" id="out"></div>'
                f'<script>document.getElementById("out").innerHTML=marked.parse(`{escaped_js}`,{{breaks:true,gfm:true}});</script></body></html>'
            )

        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        escaped = html_escape(content)
        pre_height = "100vh" if embed else "calc(100vh - 43px)"
        return (
            f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}body{{background:{embed_bg};color:{pane_fg};font-family:"SF Mono","Fira Code",monospace;font-size:13px}}'
            f'.hdr{{padding:10px 16px;background:{embed_bg};border-bottom:1px solid {pane_line};display:flex;align-items:center;gap:8px}}'
            f'.fn{{font-weight:700;font-size:14px;color:{pane_fg}}}.fp{{color:{pane_muted};font-size:12px}}'
            f'pre{{margin:0;padding:16px;white-space:pre;overflow:auto;height:{pre_height};background:{embed_bg}}}</style></head>'
            f'<body>{header.format(icon="📄")}<pre>{escaped}</pre></body></html>'
        )
