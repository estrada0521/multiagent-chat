from __future__ import annotations
import logging
import re
import uuid

import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from ..runtime.state import load_hub_settings, sanitize_hub_external_editor_choice


class FileRuntime:
    INLINE_PROGRESSIVE_PREVIEW_MAX_BYTES = 512 * 1024
    RAW_STREAM_CHUNK_BYTES = 64 * 1024
    PROGRESSIVE_TEXT_PREVIEW_CHUNK_BYTES = 32 * 1024
    FILE_LIST_CACHE_TTL_SECONDS = 45
    FILE_SEARCH_MAX_LIMIT = 200
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
    MARKDOWN_EXTS = frozenset({".md", ".markdown"})
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

    def __init__(
        self,
        *,
        workspace: str | Path,
        allowed_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
        repo_root: str | Path | None = None,
    ):
        self.workspace = os.path.realpath(os.path.normpath(str(workspace)))
        self.repo_root = os.path.realpath(os.path.normpath(str(repo_root))) if repo_root else None
        roots = [self.workspace]
        for candidate in allowed_roots or ():
            if not candidate:
                continue
            resolved = os.path.realpath(os.path.normpath(str(candidate)))
            if resolved not in roots:
                roots.append(resolved)
        self.allowed_roots = tuple(roots)
        self._file_list_cache: list[dict] | None = None
        self._file_list_cache_at = 0.0
        self._file_list_cache_lock = threading.Lock()

    def _is_allowed_path(self, full: str) -> bool:
        for root in self.allowed_roots:
            if full == root or full.startswith(root + os.sep):
                return True
        return False

    @staticmethod
    def _native_log_home_root_paths() -> tuple[Path, ...]:
        home = Path.home()
        roots = (
            home / ".cursor",
            home / ".claude",
            home / ".codex",
            home / ".gemini",
            home / ".copilot",
            home / ".qwen",
            home / ".local" / "share" / "opencode",
        )
        out: list[Path] = []
        for r in roots:
            try:
                out.append(r.resolve())
            except OSError:
                continue
        return tuple(out)

    def _is_native_log_home_path(self, full: str) -> bool:
        try:
            fp = Path(full).resolve()
        except OSError:
            return False
        for root in self._native_log_home_root_paths():
            try:
                fp.relative_to(root)
                return True
            except ValueError:
                continue
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
        result = {}
        for rel in paths:
            try:
                full = self._resolve_path(rel, allow_workspace_root=True)
                result[rel] = os.path.exists(full)
            except (PermissionError, Exception):
                result[rel] = False
        return result

    @classmethod
    def content_type_for_rel(cls, rel: str) -> str:
        ext = os.path.splitext(rel)[1].lower()
        return cls.MIME_TYPES.get(ext, "application/octet-stream")

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
        if ext in self.PDF_EXTS:
            return False
        return ext in self.EDITABLE_TEXT_EXTS or self._is_probably_text_file(full)

    def openability(self, rel: str) -> dict[str, str | bool | None]:
        full = self._resolve_path(rel, allow_workspace_root=True)
        if not os.path.isfile(full):
            raise FileNotFoundError(rel)
        ext = os.path.splitext(full)[1].lower()
        if ext in self.PDF_EXTS:
            return {"editable": False, "media_kind": "pdf"}
        if ext in self.IMAGE_EXTS:
            return {"editable": False, "media_kind": "image"}
        if ext in self.VIDEO_EXTS:
            return {"editable": False, "media_kind": "video"}
        if ext in self.AUDIO_EXTS:
            return {"editable": False, "media_kind": "audio"}
        editable = ext in self.EDITABLE_TEXT_EXTS or self._is_probably_text_file(full)
        return {"editable": bool(editable), "media_kind": None}

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

    def _preferred_external_editor(self) -> str:
        if not self.repo_root:
            return "vscode"
        try:
            settings = load_hub_settings(self.repo_root)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return "vscode"
        preferred_raw = str(settings.get("external_editor", "vscode") or "vscode").strip()
        return sanitize_hub_external_editor_choice(preferred_raw, allow_markedit=False)

    def _preferred_markdown_external_editor(self) -> str:
        if not self.repo_root:
            return "markedit"
        try:
            settings = load_hub_settings(self.repo_root)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return "markedit"
        raw = str(settings.get("external_editor_markdown", "markedit") or "markedit").strip()
        token = sanitize_hub_external_editor_choice(raw, allow_markedit=True)
        if token == "markedit" and not FileRuntime._macos_app_exists("MarkEdit"):
            return self._preferred_external_editor()
        return token

    def _preferred_editor_token_for_path(self, full: str) -> str:
        ext = os.path.splitext(full)[1].lower()
        if ext in self.MARKDOWN_EXTS:
            return self._preferred_markdown_external_editor()
        return self._preferred_external_editor()

    def _editor_command(self, full: str, line: int = 0, *, preferred: str | None = None) -> tuple[list[str], str]:
        configured = (os.environ.get("MULTIAGENT_EXTERNAL_EDITOR") or "").strip()
        if configured:
            if "{path}" in configured:
                return shlex.split(configured.format(path=full)), "custom"
            return shlex.split(configured) + [full], "custom"
        use_pref = preferred if preferred is not None else self._preferred_external_editor()
        use_pref = str(use_pref or "vscode").strip() or "vscode"
        if use_pref.lower() == "markedit" and sys.platform == "darwin" and FileRuntime._macos_app_exists("MarkEdit"):
            return ["open", "-a", "MarkEdit", full], "lightweight"
        preferred = use_pref
        if preferred.startswith("app:") and sys.platform == "darwin":
            app_name = preferred[4:].strip()
            app_name_lc = app_name.lower()
            if app_name and FileRuntime._macos_app_exists(app_name):
                if app_name_lc in {"visual studio code", "vscode"}:
                    if shutil.which("code"):
                        if line > 0:
                            return ["code", "-g", f"{full}:{line}"], "vscode"
                        return ["code", full], "vscode"
                    if line > 0:
                        return ["open", "-a", "Visual Studio Code", "--args", "--goto", f"{full}:{line}"], "vscode"
                    return ["open", "-a", "Visual Studio Code", full], "vscode"
                if app_name_lc == "coteditor":
                    if line > 0:
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
                    return ["open", "-a", "CotEditor", full], "lightweight"
                return ["open", "-a", app_name, full], "lightweight"
        if preferred == "system":
            if sys.platform == "darwin":
                return ["open", full], "system"
            if shutil.which("xdg-open"):
                return ["xdg-open", full], "system"
        if preferred == "coteditor" and sys.platform == "darwin" and FileRuntime._macos_app_exists("CotEditor"):
            if line > 0:
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
            return ["open", "-a", "CotEditor", full], "lightweight"
        if shutil.which("code"):
            if line > 0:
                return ["code", "-g", f"{full}:{line}"], "vscode"
            return ["code", full], "vscode"
        if sys.platform == "darwin" and FileRuntime._macos_app_exists("Visual Studio Code"):
            if line > 0:
                return ["open", "-a", "Visual Studio Code", "--args", "--goto", f"{full}:{line}"], "vscode"
            return ["open", "-a", "Visual Studio Code", full], "vscode"
        if sys.platform == "darwin":
            if FileRuntime._macos_app_exists("CotEditor"):
                if line > 0:
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
                return ["open", "-a", "CotEditor", full], "lightweight"
            if FileRuntime._macos_app_exists("Sublime Text"):
                st_target = f"{full}:{line}" if line > 0 else full
                return ["open", "-a", "Sublime Text", st_target], "lightweight"
            if FileRuntime._macos_app_exists("TextMate"):
                return ["open", "-a", "TextMate", full], "lightweight"
            if FileRuntime._macos_app_exists("BBEdit"):
                return ["open", "-a", "BBEdit", full], "lightweight"
            return ["open", full], "system"
        if shutil.which("xdg-open"):
            return ["xdg-open", full], "system"
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

    def _spawn_open_os_default(self, full: str) -> None:
        if sys.platform == "darwin":
            subprocess.Popen(
                ["open", full],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        elif shutil.which("xdg-open"):
            subprocess.Popen(
                ["xdg-open", full],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        else:
            raise ValueError("No handler available to open this file with the system default.")

    def open_in_editor(self, rel: str, line: int = 0, *, allow_native_log_home: bool = False):
        rel_raw = str(rel or "").strip()
        if not rel_raw:
            raise ValueError("path required")
        if allow_native_log_home:
            if not (rel_raw.startswith("~") or os.path.isabs(rel_raw)):
                raise ValueError("allow_native_log_home requires an absolute path")
            full = os.path.realpath(os.path.expanduser(rel_raw))
            if not self._is_native_log_home_path(full):
                raise PermissionError(full)
        else:
            full = self._resolve_path(rel_raw, allow_workspace_root=True)
        if not os.path.isfile(full):
            raise FileNotFoundError(full)
        ext = os.path.splitext(full)[1].lower()
        media_exts = self.IMAGE_EXTS | set(self.VIDEO_EXTS.keys()) | set(self.AUDIO_EXTS.keys())
        os_default_exts = media_exts | self.PDF_EXTS
        if ext in os_default_exts:
            self._spawn_open_os_default(full)
            return {"ok": True, "path": rel}
        if ext not in self.EDITABLE_TEXT_EXTS and ext not in {".html", ".htm"} and not self._is_probably_text_file(full):
            raise ValueError("Only text files can be opened in an external editor.")
        editor_token = self._preferred_editor_token_for_path(full)
        cmd, _mode = self._editor_command(full, line=line, preferred=editor_token)
        popen_kw: dict = {}
        if cmd and cmd[0] == "code" and self.workspace:
            try:
                popen_kw["cwd"] = self.workspace
            except Exception:
                pass
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            **popen_kw,
        )
        return {"ok": True, "path": rel}

    def _git_show_bytes(self, rev_path: str) -> bytes | None:
        try:
            proc = subprocess.run(
                ["git", "-C", self.workspace, "show", rev_path],
                capture_output=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout if proc.stdout is not None else b""

    @staticmethod
    def _blob_looks_binary(blob: bytes) -> bool:
        if not blob:
            return False
        return b"\x00" in blob[:8192]

    @staticmethod
    def _darwin_antigravity_executable() -> str | None:
        if sys.platform != "darwin":
            return None
        for candidate in (
            "/Applications/Antigravity.app/Contents/Resources/app/bin/antigravity",
            str(Path.home() / "Applications/Antigravity.app/Contents/Resources/app/bin/antigravity"),
        ):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return None

    def _spawn_vscode_diff(self, left: str, right: str) -> None:
        left_abs = str(Path(left).resolve())
        right_abs = str(Path(right).resolve())
        diff_tail = ["--diff", left_abs, right_abs]
        ws = self.workspace
        candidates: list[list[str]] = []

        custom = (os.environ.get("MULTIAGENT_DIFF_EDITOR") or "").strip()
        if custom:
            try:
                prefix = shlex.split(custom)
                if prefix:
                    candidates.append(prefix + diff_tail)
            except ValueError:
                pass

        seen: set[tuple[str, ...]] = set()

        def _add(cmd: list[str]) -> None:
            key = tuple(cmd)
            if key in seen:
                return
            seen.add(key)
            candidates.append(cmd)

        for name in ("agy", "antigravity"):
            found = shutil.which(name)
            if found:
                _add([found, ws, *diff_tail])
                _add([found, *diff_tail])

        bundle = self._darwin_antigravity_executable()
        if bundle and not shutil.which("agy") and not shutil.which("antigravity"):
            _add([bundle, ws, *diff_tail])
            _add([bundle, *diff_tail])

        if shutil.which("code"):
            _add(["code", *diff_tail])
            _add(["code", ws, *diff_tail])

        if sys.platform == "darwin":
            if FileRuntime._macos_app_exists("Antigravity"):
                _add(["open", "-na", "Antigravity", "--args", ws, *diff_tail])
                _add(["open", "-na", "Antigravity", "--args", *diff_tail])
            if FileRuntime._macos_app_exists("Visual Studio Code"):
                _add(["open", "-na", "Visual Studio Code", "--args", ws, *diff_tail])
                _add(["open", "-na", "Visual Studio Code", "--args", *diff_tail])

        if not candidates:
            raise ValueError(
                "External diff needs a VS Code–compatible CLI: install Google Antigravity ('agy'), "
                "VS Code ('code'), or set MULTIAGENT_DIFF_EDITOR to a command (e.g. agy)."
            )
        cmd = candidates[0]
        popen_kw: dict = {}
        if cmd[0] != "open" and ws:
            try:
                popen_kw["cwd"] = ws
            except Exception:
                pass
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            **popen_kw,
        )

    def open_diff_in_editor(self, rel: str, *, commit_hash: str = "") -> dict:
        rel = str(rel or "").strip().lstrip("/")
        if not rel:
            raise ValueError("path required")
        commit_hash = str(commit_hash or "").strip()
        full = self._resolve_path(rel, allow_workspace_root=True)

        if not commit_hash:
            old_b = self._git_show_bytes(f"HEAD:{rel}")
            old_bytes = old_b if old_b is not None else b""
            if os.path.isfile(full):
                with open(full, "rb") as fh:
                    new_bytes = fh.read()
            else:
                new_bytes = b""
        else:
            old_b = self._git_show_bytes(f"{commit_hash}~1:{rel}")
            new_b = self._git_show_bytes(f"{commit_hash}:{rel}")
            old_bytes = old_b if old_b is not None else b""
            new_bytes = new_b if new_b is not None else b""

        if self._blob_looks_binary(old_bytes) or self._blob_looks_binary(new_bytes):
            raise ValueError("Binary files cannot be opened in the external diff view.")
        if not old_bytes and not new_bytes:
            raise FileNotFoundError(rel)

        suffix = Path(rel).suffix or ".txt"
        safe_stem = re.sub(r"[^\w\-.]+", "_", Path(rel).name)[:96] or "file"
        token = uuid.uuid4().hex[:12]
        tmp_root = Path(self.workspace) / ".multiagent-chat-diff"
        try:
            tmp_root.mkdir(mode=0o700, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"Cannot create diff cache directory in workspace: {exc}") from exc
        gitignore_path = tmp_root / ".gitignore"
        if not gitignore_path.exists():
            try:
                gitignore_path.write_text(
                    "# Ephemeral diff snapshots (multiagent-chat). Safe to delete this folder.\n*\n!.gitignore\n",
                    encoding="utf-8",
                )
            except OSError:
                pass

        left_path = tmp_root / f"{safe_stem}.base.{token}{suffix}"
        left_path.write_bytes(old_bytes)

        if not commit_hash and os.path.isfile(full):
            right_arg = os.path.abspath(full)
        else:
            right_path = tmp_root / f"{safe_stem}.work.{token}{suffix}"
            right_path.write_bytes(new_bytes)
            right_arg = str(right_path.resolve())

        self._spawn_vscode_diff(str(left_path.resolve()), right_arg)
        return {"ok": True, "path": rel, "mode": "diff", "commit_hash": commit_hash}

    def _list_files_via_git(self) -> list[str] | None:
        try:
            proc = subprocess.run(
                [
                    "git",
                    "-C",
                    self.workspace,
                    "ls-files",
                    "-z",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=4.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        raw = proc.stdout.decode("utf-8", errors="replace")
        paths: list[str] = []
        seen: set[str] = set()
        for item in raw.split("\x00"):
            rel = str(item or "").replace("\\", "/").strip("/")
            if not rel or rel in seen:
                continue
            parts = Path(rel).parts[:-1]
            if any(part in self.SKIP_DIRS for part in parts):
                continue
            full = os.path.realpath(os.path.join(self.workspace, rel))
            if not self._is_allowed_path(full):
                continue
            seen.add(rel)
            paths.append(rel)
        return sorted(paths, key=lambda value: value.casefold())

    def _list_files_via_walk(self) -> list[str]:
        paths: list[str] = []
        for root, dirs, filenames in os.walk(self.workspace):
            dirs[:] = sorted(d for d in dirs if d != ".git")
            for filename in sorted(filenames):
                full = os.path.join(root, filename)
                resolved = os.path.realpath(full)
                if not self._is_allowed_path(resolved):
                    continue
                rel = os.path.relpath(full, self.workspace).replace("\\", "/")
                if rel:
                    paths.append(rel)
        paths.sort(key=lambda value: value.casefold())
        return paths

    def list_files(self, *, force_refresh: bool = False):
        now = time.time()
        if not force_refresh:
            with self._file_list_cache_lock:
                if (
                    self._file_list_cache is not None
                    and (now - self._file_list_cache_at) <= self.FILE_LIST_CACHE_TTL_SECONDS
                ):
                    return [dict(item) for item in self._file_list_cache]
        paths = self._list_files_via_walk()
        files = [{"path": rel, "size": None} for rel in paths]
        with self._file_list_cache_lock:
            self._file_list_cache = files
            self._file_list_cache_at = time.time()
        return [dict(item) for item in files]

    def search_files(self, query: str = "", limit: int = 60, *, force_refresh: bool = False):
        def hydrate_size(entry: dict) -> dict:
            result = dict(entry)
            if result.get("size") is not None:
                return result
            rel = str(result.get("path") or "")
            if not rel:
                result["size"] = None
                return result
            try:
                full = self._resolve_path(rel, allow_workspace_root=True)
            except PermissionError:
                result["size"] = None
                return result
            try:
                result["size"] = os.path.getsize(full) if os.path.isfile(full) else None
            except OSError:
                result["size"] = None
            return result

        def ranking_penalty(path_lower: str) -> int:
            parts = [part for part in str(path_lower or "").split("/") if part]
            penalty = 0
            if parts and parts[0].startswith("."):
                penalty += 1
            noisy_dirs = {
                "node_modules",
                ".venv",
                "venv",
                "__pycache__",
                ".mypy_cache",
                "site-packages",
                "target",
                "build",
                "dist",
                "tmp",
            }
            for part in parts[:-1]:
                if part in noisy_dirs:
                    penalty += 3
                elif part.endswith(".app"):
                    penalty += 2
                elif part.startswith("."):
                    penalty += 1
            return penalty

        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError):
            normalized_limit = 60
        normalized_limit = max(1, min(self.FILE_SEARCH_MAX_LIMIT, normalized_limit))
        entries = self.list_files(force_refresh=force_refresh)
        needle = str(query or "").strip().lower()
        if not needle:
            preferred_text_exts = self.EDITABLE_TEXT_EXTS | {".md"}
            ranked_default = sorted(
                entries,
                key=lambda entry: (
                    ranking_penalty(str(entry.get("path") or "").lower()),
                    0
                    if os.path.splitext(str(entry.get("path") or "").lower())[1] in preferred_text_exts
                    else 1,
                    str(entry.get("path") or "").count("/"),
                    len(str(entry.get("path") or "")),
                    str(entry.get("path") or "").lower(),
                ),
            )
            return [hydrate_size(entry) for entry in ranked_default[:normalized_limit]]

        ranked: list[tuple[tuple[int, int, int, int, str], dict]] = []
        for entry in entries:
            path = str(entry.get("path") or "")
            if not path:
                continue
            path_lower = path.lower()
            base_lower = os.path.basename(path_lower)
            penalty = ranking_penalty(path_lower)
            score: tuple[int, int, int, int, str] | None = None
            if base_lower == needle or path_lower == needle:
                score = (0, penalty, 0, len(path_lower), path_lower)
            elif base_lower.startswith(needle):
                score = (1, penalty, 0, len(base_lower), path_lower)
            else:
                base_hit = base_lower.find(needle)
                if base_hit >= 0:
                    score = (2, penalty, base_hit, len(base_lower), path_lower)
                else:
                    path_hit = path_lower.find(needle)
                    if path_hit >= 0:
                        score = (3, penalty, path_hit, len(path_lower), path_lower)
            if score is not None:
                ranked.append((score, entry))

        ranked.sort(key=lambda item: item[0])
        return [hydrate_size(item[1]) for item in ranked[:normalized_limit]]

    def list_dir(self, rel: str = ""):
        normalized_rel = str(rel or "").replace("\\", "/").strip("/")
        full = self._resolve_path(normalized_rel, allow_workspace_root=True)
        if not os.path.isdir(full):
            raise NotADirectoryError(full)
        entries = []
        with os.scandir(full) as scanner:
            for entry in scanner:
                name = entry.name
                if not name or name in {".", ".."}:
                    continue
                child_rel = f"{normalized_rel}/{name}" if normalized_rel else name
                try:
                    child_real = os.path.realpath(entry.path)
                except OSError:
                    continue
                if not self._is_allowed_path(child_real):
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=True)
                except OSError:
                    continue
                if is_dir:
                    if name in self.SKIP_DIRS:
                        continue
                    entries.append({"name": name, "path": child_rel, "kind": "dir"})
                    continue
                try:
                    if not entry.is_file(follow_symlinks=True):
                        continue
                except OSError:
                    continue
                try:
                    size = entry.stat(follow_symlinks=True).st_size
                except OSError:
                    size = None
                entries.append({"name": name, "path": child_rel, "kind": "file", "size": size})
        entries.sort(key=lambda item: (item.get("kind") != "dir", str(item.get("name") or "").casefold()))
        return entries

    def file_view(
        self,
        rel: str,
        *,
        embed: bool = False,
        pane: bool = False,
        base_path: str = "",
        agent_font_mode: str = "serif",
        agent_font_family: str | None = None,
        agent_text_size: int | None = None,
        message_bold: bool = False,
        force_progressive_text: bool = False,
    ) -> str:
        from .view import render_file_view

        return render_file_view(
            self,
            rel,
            embed=embed,
            pane=pane,
            base_path=base_path,
            agent_font_mode=agent_font_mode,
            agent_font_family=agent_font_family,
            agent_text_size=agent_text_size,
            message_bold=message_bold,
            force_progressive_text=force_progressive_text,
        )
