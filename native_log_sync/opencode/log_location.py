"""OpenCode: native SQLite DB のパス（セッションは log_readout_messages 側で解決）。"""

from __future__ import annotations

from pathlib import Path


def opencode_db_path() -> Path:
    return Path.home() / ".local" / "share" / "opencode" / "opencode.db"
