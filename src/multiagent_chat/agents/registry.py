"""Single source of truth for all agent definitions.

To add a new agent:
  1. Add an AgentDef entry to _register() below
  2. Place the SVG icon file in assets/icons/agents/ (repo root)
  3. That's it — all Python/JS/CSS/shell code reads from here
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentDef:
    name: str
    display_name: str
    icon_file: str
    executable: str = ""
    launch_extra: str = ""
    launch_flags: str = ""
    launch_env: str = ""
    resume_flag: str = ""
    resume_extra_flags: str = ""
    ready_pattern: str = ""
    number_alias: int = 0
    startup_priority: int = 0
    fallback_paths: tuple[str, ...] = ()
    fallback_nvm: bool = False
    selectable: bool = True

    @property
    def exe(self) -> str:
        return self.executable or self.name


AGENTS: dict[str, AgentDef] = {}

AGENT_ICONS_DIR = "assets/icons/agents"

_AGENT_TMUX_COLOR_SUFFIX = "-u NO_COLOR -u CI FORCE_COLOR=1"


def _register(*defs: AgentDef) -> None:
    for d in defs:
        AGENTS[d.name] = d


_register(
    AgentDef(
        name="claude",
        display_name="Claude",
        icon_file="claude-color.svg",
        executable="claude",
        launch_extra=f"env -u CLAUDECODE {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="--continue",
        ready_pattern=r"Claude Code|Tips for getting started|Recent activity",
        number_alias=1,
        fallback_paths=("~/.local/bin/claude",),
    ),
    AgentDef(
        name="codex",
        display_name="Codex",
        icon_file="codex-color.svg",
        executable="codex",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="resume --last",
        ready_pattern=r"OpenAI Codex|model:|Tip: New",
        number_alias=2,
        fallback_nvm=True,
    ),
    AgentDef(
        name="gemini",
        display_name="Gemini",
        icon_file="gemini-color.svg",
        executable="gemini",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="--resume latest",
        ready_pattern=r"Ready \(multiagent\)|Gemini|Type your message",
        number_alias=3,
        fallback_nvm=True,
    ),
    AgentDef(
        name="kimi",
        display_name="Kimi",
        icon_file="kimi.svg",
        executable="kimi",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="--continue",
        ready_pattern=r"Kimi Code CLI|send /help for help information|send /login to login",
        number_alias=10,
        fallback_paths=("~/.local/bin/kimi", "/opt/homebrew/bin/kimi", "/usr/local/bin/kimi"),
    ),
    AgentDef(
        name="copilot",
        display_name="Copilot",
        icon_file="github.svg",
        executable="copilot",
        launch_env="COPILOT_ALLOW_ALL=1",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        launch_flags="--allow-all-tools",
        resume_flag="--continue",
        resume_extra_flags="--allow-all-tools",
        ready_pattern=r"GitHub Copilot|What can I help you with|Ask Copilot",
        number_alias=4,
        startup_priority=10,
        fallback_nvm=True,
    ),
    AgentDef(
        name="cursor",
        display_name="Cursor",
        icon_file="cursor.svg",
        executable="agent",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="--continue",
        ready_pattern=r"Cursor Agent|resume previous session|Output the version number|Bypassing Permissions",
        number_alias=5,
        fallback_paths=("~/.local/bin/agent", "~/.local/bin/cursor-agent"),
    ),
    AgentDef(
        name="opencode",
        display_name="OpenCode",
        icon_file="opencode.svg",
        executable="opencode",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="--continue",
        ready_pattern=r"OpenCode|opencode|/help|/connect|/models",
        number_alias=7,
        fallback_paths=("~/.opencode/bin/opencode",),
    ),
    AgentDef(
        name="qwen",
        display_name="Qwen",
        icon_file="qwen.svg",
        executable="qwen",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="--continue",
        ready_pattern=r"Qwen Code|\? for shortcuts|メッセージを入力|Type your message",
        number_alias=8,
        fallback_paths=("/opt/homebrew/bin/qwen", "/usr/local/bin/qwen", "~/.local/bin/qwen"),
        fallback_nvm=True,
    ),
)


ALL_AGENT_NAMES: list[str] = list(AGENTS.keys())
SELECTABLE_AGENT_NAMES: list[str] = [
    name for name, d in AGENTS.items() if d.selectable
]


def icon_file_map(repo_root: Path) -> dict[str, Path]:
    """Return {agent_name: Path_to_icon} for all agents."""
    base = Path(repo_root).resolve() / AGENT_ICONS_DIR
    return {name: base / Path(a.icon_file).name for name, a in AGENTS.items()}


def icon_filename_map() -> dict[str, str]:
    """Return {agent_name: icon_filename} for all agents."""
    return {name: a.icon_file for name, a in AGENTS.items()}


def number_alias_map() -> dict[int, str]:
    """Return {number: agent_name} for agents with number aliases."""
    return {a.number_alias: name for name, a in AGENTS.items() if a.number_alias}


def generate_agent_message_selectors(suffix: str = "", prefix: str = "") -> str:
    """Generate a generic CSS selector for agent messages.

    Visual agent differences are icon-only. Message CSS therefore targets any
    non-user/non-system message instead of expanding per-agent selectors.
    """
    return f"    {prefix}.message:not(.user):not(.system){suffix}"


def agent_names_js_set() -> str:
    """Return JS Set literal: new Set(["claude", "codex", ...])"""
    items = ", ".join(f'"{n}"' for n in ALL_AGENT_NAMES)
    return f"new Set([{items}])"


def agent_names_js_array() -> str:
    """Return JS array literal: ["claude", "codex", ...]"""
    items = ", ".join(f'"{n}"' for n in SELECTABLE_AGENT_NAMES)
    return f"[{items}]"
