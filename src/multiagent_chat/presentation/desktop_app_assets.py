from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DESKTOP_APP_UI_ROOT = _REPO_ROOT / "desktop_app" / "ui"


def _read_desktop_app_ui_text(*parts: str) -> str:
    path = _DESKTOP_APP_UI_ROOT.joinpath(*parts)
    if not path.is_file():
        return ""
    text = path.read_text()
    return text if text.endswith("\n") else f"{text}\n"


DESKTOP_APP_HUB_HEADER_CSS = _read_desktop_app_ui_text("hub", "header.css")
DESKTOP_APP_CHAT_CSS = _read_desktop_app_ui_text("chat", "tauri.css")
DESKTOP_APP_CHAT_JS = _read_desktop_app_ui_text("chat", "tauri.js")
