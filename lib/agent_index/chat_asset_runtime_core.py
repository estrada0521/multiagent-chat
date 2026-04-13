from __future__ import annotations

import base64
import logging
from pathlib import Path
from urllib.parse import unquote

from .agent_name_core import agent_base_name
from .agent_registry import icon_file_map


class ChatAssetRuntime:
    def __init__(self, *, repo_root: Path | str):
        self.repo_root = Path(repo_root).resolve()
        self.icon_files = icon_file_map(self.repo_root)
        self.font_files = {
            "anthropic-serif-roman.ttf": [
                Path.home() / "Library/Fonts/AnthropicSerif-Romans-Variable-25x258.ttf",
                Path("/Applications/Claude.app/Contents/Resources/fonts/AnthropicSerif-Romans-Variable-25x258.ttf"),
            ],
            "anthropic-serif-italic.ttf": [
                Path.home() / "Library/Fonts/AnthropicSerif-Italics-Variable-25x258.ttf",
                Path("/Applications/Claude.app/Contents/Resources/fonts/AnthropicSerif-Italics-Variable-25x258.ttf"),
            ],
            "anthropic-sans-roman.ttf": [
                Path("/Applications/Claude.app/Contents/Resources/fonts/AnthropicSans-Romans-Variable-25x258.ttf"),
            ],
            "anthropic-sans-italic.ttf": [
                Path("/Applications/Claude.app/Contents/Resources/fonts/AnthropicSans-Italics-Variable-25x258.ttf"),
            ],
            "jetbrains-mono.ttf": [
                Path.home() / "Library/Fonts/JetBrainsMono-Variable.ttf",
                Path("/System/Library/Fonts/Supplemental/JetBrainsMono-Variable.ttf"),
            ],
        }
        self.icon_data_uris = {name: self._icon_data_uri(name) for name in self.icon_files}

    def _icon_data_uri(self, name: str) -> str:
        icon_path = self.icon_files.get(name)
        if not icon_path or not icon_path.exists():
            return ""
        try:
            raw = icon_path.read_bytes()
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return ""
        return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")

    def resolve_font_file(self, name: str) -> Path | None:
        for candidate in self.font_files.get(name, []):
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def resolve_icon_map_key(raw_name: str, icon_files: dict[str, Path]) -> str | None:
        name = unquote((raw_name or "").strip()).lower()
        if not name:
            return None
        if name in icon_files:
            return name
        base = agent_base_name(name)
        if base in icon_files:
            return base
        return None

    def icon_bytes(self, name: str) -> bytes | None:
        key = self.resolve_icon_map_key(name, self.icon_files)
        if not key:
            return None
        path = self.icon_files.get(key)
        if not path or not path.exists():
            return None
        try:
            return path.read_bytes()
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return None

    def font_bytes(self, name: str) -> bytes | None:
        path = self.resolve_font_file(name)
        if not path:
            return None
        try:
            return path.read_bytes()
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return None
