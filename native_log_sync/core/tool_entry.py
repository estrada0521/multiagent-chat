from __future__ import annotations

from typing import NamedTuple


class ToolEntry(NamedTuple):
    label: str
    mode: str
    arg_keys: list[str]
    target_keys: list[str] = []
