from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShortcutCommandSpec:
    id: str
    slash: str
    desc: str
    has_arg: bool


def all_commands() -> tuple[ShortcutCommandSpec, ...]:
    return (
        ShortcutCommandSpec(
            id="model",
            slash="/model",
            desc="選択中 pane に /model を送信",
            has_arg=False,
        ),
        ShortcutCommandSpec(
            id="up",
            slash="/up",
            desc="選択中 pane に上移動を送信",
            has_arg=True,
        ),
        ShortcutCommandSpec(
            id="down",
            slash="/down",
            desc="選択中 pane に下移動を送信",
            has_arg=True,
        ),
        ShortcutCommandSpec(
            id="restart",
            slash="/restart",
            desc="エージェント再起動",
            has_arg=False,
        ),
        ShortcutCommandSpec(
            id="resume",
            slash="/resume",
            desc="エージェント再開",
            has_arg=False,
        ),
        ShortcutCommandSpec(
            id="ctrlc",
            slash="/ctrlc",
            desc="エージェントに Ctrl+C 送信",
            has_arg=False,
        ),
        ShortcutCommandSpec(
            id="interrupt",
            slash="/interrupt",
            desc="エージェントに Esc 送信",
            has_arg=False,
        ),
        ShortcutCommandSpec(
            id="enter",
            slash="/enter",
            desc="エージェントに Enter 送信",
            has_arg=False,
        ),
    )


_BY_ID: dict[str, ShortcutCommandSpec] | None = None


def command_by_id(command_id: str) -> ShortcutCommandSpec | None:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = {c.id: c for c in all_commands()}
    return _BY_ID.get((command_id or "").strip().lower())


def public_command_dicts() -> list[dict[str, str | bool]]:
    return [
        {"id": c.id, "slash": c.slash, "desc": c.desc, "has_arg": c.has_arg}
        for c in all_commands()
    ]


PANE_SINGLE_CONTROL_MESSAGES = frozenset(
    {"interrupt", "ctrlc", "enter", "restart", "resume"},
)
