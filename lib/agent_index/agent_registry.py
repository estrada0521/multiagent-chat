"""Single source of truth for all agent definitions.

To add a new agent:
  1. Add an AgentDef entry to _register() below
  2. Place the SVG icon file in agent_icons/ (repo root)
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
    accent_color: str = "#b0b8c0"
    executable: str = ""  # command name; defaults to name if empty
    launch_extra: str = ""  # prepended before exec, e.g. "env -u CLAUDECODE"
    launch_flags: str = ""  # appended after exec on launch
    launch_env: str = ""  # extra env exports, e.g. "COPILOT_ALLOW_ALL=1"
    resume_flag: str = ""  # e.g. "--continue", "resume --last"
    resume_extra_flags: str = ""  # appended after resume_flag
    ready_pattern: str = ""  # regex for wait_for_agent_ready
    number_alias: int = 0  # shortcut number (1=claude, 2=codex, ...)
    startup_priority: int = 0  # higher = start first
    fallback_paths: tuple[str, ...] = ()  # additional search paths (~ expanded)
    fallback_nvm: bool = False  # search NVM node dirs for executable
    thinking_glow_delay: str = "0s"  # CSS animation-delay

    @property
    def exe(self) -> str:
        return self.executable or self.name


AGENTS: dict[str, AgentDef] = {}

# Directory under repo root holding per-agent SVG icons (parallel to sounds/).
AGENT_ICONS_DIR = "agent_icons"

# Tmux / login env often exports NO_COLOR or CI=1; strip those and set FORCE_COLOR so agent TUIs stay colored.
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
        thinking_glow_delay="0s",
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
        thinking_glow_delay="-0.25s",
        fallback_nvm=True,
    ),
    AgentDef(
        name="gemini",
        display_name="Gemini",
        icon_file="gemini-color.svg",
        executable="gemini",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="--resume latest",
        ready_pattern=r"Ready \\(multiagent\\)|Gemini|Type your message",
        number_alias=3,
        thinking_glow_delay="-0.5s",
        fallback_nvm=True,
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
        thinking_glow_delay="-0.75s",
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
        name="grok",
        display_name="Grok",
        icon_file="grok.svg",
        executable="grok",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        ready_pattern=r"Grok|xAI|Type your message|What do you want to do",
        number_alias=6,
    ),
    AgentDef(
        name="opencode",
        display_name="OpenCode",
        icon_file="opencode.svg",
        accent_color="#38bdf8",
        executable="opencode",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="--continue",
        ready_pattern=r"OpenCode|opencode|/help|/connect|/models",
        number_alias=7,
        thinking_glow_delay="-1s",
        fallback_paths=("~/.opencode/bin/opencode",),
    ),
    AgentDef(
        name="qwen",
        display_name="Qwen",
        icon_file="qwen.svg",
        accent_color="#5b6cff",
        executable="qwen",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="--continue",
        ready_pattern=r"Qwen Code|\? for shortcuts|メッセージを入力|Type your message",
        number_alias=8,
        thinking_glow_delay="-1.25s",
        fallback_paths=("/opt/homebrew/bin/qwen", "/usr/local/bin/qwen", "~/.local/bin/qwen"),
        fallback_nvm=True,
    ),
    AgentDef(
        name="aider",
        display_name="Aider",
        icon_file="aider.svg",
        accent_color="#22c55e",
        executable="aider",
        launch_extra=f"env {_AGENT_TMUX_COLOR_SUFFIX}",
        resume_flag="--restore-chat-history",
        ready_pattern=r"Aider|aider>|https://aider\.chat|Repository maps|Git repo|\.aider",
        number_alias=9,
        thinking_glow_delay="-1.5s",
        fallback_paths=("~/.local/bin/aider", "/opt/homebrew/bin/aider", "/usr/local/bin/aider"),
    ),
)

# ---------------------------------------------------------------------------
# Convenience accessors
# ---------------------------------------------------------------------------

ALL_AGENT_NAMES: list[str] = list(AGENTS.keys())


def agent_names_csv() -> str:
    return ",".join(ALL_AGENT_NAMES)


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


def agents_by_startup_priority() -> list[AgentDef]:
    """Return agents sorted by startup_priority descending."""
    return sorted(AGENTS.values(), key=lambda a: a.startup_priority, reverse=True)


def generate_accent_css(theme: str = "default") -> str:
    """Generate CSS custom properties for agent accent colors."""
    lines = []
    for name, a in AGENTS.items():
        lines.append(f"      --{name}-accent: {a.accent_color};")
    return "\n".join(lines)


def generate_agent_message_selectors(suffix: str = "", prefix: str = "") -> str:
    """Generate comma-separated CSS selectors for all agent messages.

    Example: generate_agent_message_selectors(" .md-body") ->
      ".message.claude .md-body,\\n.message.codex .md-body, ..."
    """
    parts = []
    for name in ALL_AGENT_NAMES:
        sel = f"    {prefix}.message.{name}{suffix}"
        parts.append(sel)
    return ",\n".join(parts)


def generate_thinking_glow_css() -> str:
    """Generate thinking glow animation delay CSS."""
    lines = []
    for name, a in AGENTS.items():
        if a.thinking_glow_delay:
            lines.append(
                f"    .message-thinking-glow--{name}  {{ animation-delay: {a.thinking_glow_delay}; }}"
            )
    return "\n".join(lines)


def agent_names_js_set() -> str:
    """Return JS Set literal: new Set(["claude", "codex", ...])"""
    items = ", ".join(f'"{n}"' for n in ALL_AGENT_NAMES)
    return f"new Set([{items}])"


def agent_names_js_array() -> str:
    """Return JS array literal: ["claude", "codex", ...]"""
    items = ", ".join(f'"{n}"' for n in ALL_AGENT_NAMES)
    return f"[{items}]"
