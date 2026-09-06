from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlashCommandSpec:
    id: str
    slash: str
    desc: str
    has_arg: bool
    path: str
    desktop_only: bool = False
    # When set, selecting the command inserts this text into the composer
    # (like an @-mention) instead of POSTing to a backend route -- for
    # referencing files @-search can't reach, such as dotfiles.
    insert: str = ""


PANE_CONTROL_COMMANDS = (
    SlashCommandSpec(
        id="up", slash="/up", desc="選択中 pane に上移動を送信", has_arg=True, path="/shortcut-command",
    ),
    SlashCommandSpec(
        id="down", slash="/down", desc="選択中 pane に下移動を送信", has_arg=True, path="/shortcut-command",
    ),
    SlashCommandSpec(
        id="left", slash="/left", desc="選択中 pane に左移動を送信", has_arg=True, path="/shortcut-command",
    ),
    SlashCommandSpec(
        id="right", slash="/right", desc="選択中 pane に右移動を送信", has_arg=True, path="/shortcut-command",
    ),
    SlashCommandSpec(
        id="restart", slash="/restart", desc="エージェント再起動", has_arg=False, path="/shortcut-command",
    ),
    SlashCommandSpec(
        id="resume", slash="/resume", desc="エージェント再開", has_arg=False, path="/shortcut-command",
    ),
    SlashCommandSpec(
        id="ctrlc", slash="/ctrlc", desc="エージェントに Ctrl+C 送信", has_arg=False, path="/shortcut-command",
    ),
    SlashCommandSpec(
        id="esc", slash="/esc", desc="エージェントに Esc 送信", has_arg=False, path="/shortcut-command",
    ),
    SlashCommandSpec(
        id="enter", slash="/enter", desc="エージェントに Enter 送信", has_arg=False, path="/shortcut-command",
    ),
)

APPLICATION_COMMANDS = (
    SlashCommandSpec(
        id="nativelog", slash="/nativelog", desc="選択中エージェントのネイティブログをFinderで表示する",
        has_arg=False, path="/native-log", desktop_only=True,
    ),
    SlashCommandSpec(
        id="openpane", slash="/open-pane", desc="選択中エージェントの tmux pane を開く",
        has_arg=False, path="/open-pane", desktop_only=True,
    ),
    SlashCommandSpec(
        id="log", slash="/log", desc="`.agent-window/.log.jsonl` を挿入",
        has_arg=False, path="", insert="`.agent-window/.log.jsonl`",
    ),
)

SLASH_COMMANDS = PANE_CONTROL_COMMANDS + APPLICATION_COMMANDS
PANE_CONTROL_BY_ID = {command.id: command for command in PANE_CONTROL_COMMANDS}


def pane_control_by_id(command_id: str) -> SlashCommandSpec | None:
    return PANE_CONTROL_BY_ID.get((command_id or "").strip().lower())


def public_slash_command_dicts() -> list[dict[str, str | bool]]:
    return [
        {
            "id": c.id,
            "slash": c.slash,
            "desc": c.desc,
            "has_arg": c.has_arg,
            "path": c.path,
            "desktop_only": c.desktop_only,
            "insert": c.insert,
        }
        for c in SLASH_COMMANDS
    ]


PANE_SINGLE_CONTROL_MESSAGES = frozenset(
    {"esc", "ctrlc", "enter", "restart", "resume"},
)
