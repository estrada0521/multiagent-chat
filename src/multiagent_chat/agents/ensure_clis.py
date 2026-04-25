"""Prompt-based install of third-party agent CLIs when missing.

Skipped when MULTIAGENT_SKIP_AGENT_CLI_INSTALL=1.
Does not replace vendor auth / API keys.
"""

from __future__ import annotations
import logging

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

from multiagent_chat.agents.registry import AGENTS, ALL_AGENT_NAMES


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_agent_executable(repo_root: Path, agent_name: str) -> str | None:
    """Resolve the canonical agent executable from PATH or standard install roots."""
    base = agent_name.split("-", 1)[0]
    adef = AGENTS.get(base)
    exe_name = adef.exe if adef else agent_name
    found = shutil.which(exe_name)
    if found:
        return found
    if base == "cursor":
        found = shutil.which("cursor-agent")
        if found:
            return found
    if adef:
        for p in adef.fallback_paths:
            candidate = Path(p).expanduser()
            if candidate.is_file():
                return str(candidate)
    if adef and adef.fallback_nvm:
        home = Path.home()
        nvm_bin = Path(os.environ.get("NVM_BIN", "")).expanduser()
        candidates: list[Path] = []
        if nvm_bin.is_dir():
            candidates.append(nvm_bin / exe_name)
        candidates.extend(
            sorted(
                (home / ".nvm" / "versions" / "node").glob(f"*/bin/{exe_name}"),
                reverse=True,
            )
        )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return None


def agent_launch_readiness(repo_root: Path, agent_name: str) -> dict[str, str]:
    """Return launch readiness for New Session / startup gating.

    status:
      - ok
      - missing_cli
      - missing_auth
    """
    base = agent_name.split("-", 1)[0]
    executable = resolve_agent_executable(repo_root, base)
    if not executable:
        disp = AGENTS[base].display_name if base in AGENTS else base
        return {
            "agent": base,
            "status": "missing_cli",
            "error": f"{disp} CLI is not installed on this Mac.",
        }
    return {"agent": base, "status": "ok", "executable": executable}


def _have_brew() -> bool:
    return shutil.which("brew") is not None


def _run_logged(argv: list[str]) -> bool:
    logging.info("multiagent: ensure-agent-clis: %s", ' '.join(argv))
    proc = subprocess.run(argv, text=True)
    return proc.returncode == 0


def _run_shell_logged(command: str) -> bool:
    logging.info("multiagent: ensure-agent-clis: %s", command)
    proc = subprocess.run(["bash", "-lc", command], text=True)
    return proc.returncode == 0


Installer = Callable[[], bool]


def _ensure_local_bin_in_path() -> None:
    """Add ~/.local/bin to PATH (current process) and shell profile if missing."""
    local_bin = Path.home() / ".local" / "bin"
    local_bin_str = str(local_bin)

    # Add to current process PATH
    current_path = os.environ.get("PATH", "")
    if local_bin_str not in current_path.split(os.pathsep):
        os.environ["PATH"] = local_bin_str + os.pathsep + current_path

    # Add to shell profile for future sessions
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        profile = Path.home() / ".zshrc"
    else:
        profile = Path.home() / ".profile"

    path_line = f'export PATH="$HOME/.local/bin:$PATH"'
    try:
        existing = profile.read_text(encoding="utf-8") if profile.is_file() else ""
    except Exception as exc:
        logging.error("Unexpected error: %s", exc, exc_info=True)
        existing = ""
    if ".local/bin" not in existing:
        with open(profile, "a", encoding="utf-8") as f:
            f.write(f"\n# Added by multiagent quickstart\n{path_line}\n")
        logging.info("multiagent: %s に ~/.local/bin を PATH 追加しました", profile.name)


def _installers_for_cursor() -> list[Installer]:
    """公式 install script を優先し、必要なら Homebrew cask にもフォールバックする。"""
    if sys.platform not in ("darwin", "linux"):
        return []
    installers: list[Installer] = [
        lambda: _run_shell_logged("curl https://cursor.com/install -fsS | bash"),
    ]
    if sys.platform == "darwin" and _have_brew():
        installers.extend(
            [
                lambda: _run_logged(["brew", "install", "--cask", "cursor"]),
                lambda: _run_logged(["brew", "install", "--cask", "cursor-cli"]),
            ]
        )
    return installers


def _installers_for(agent: str) -> list[Installer]:
    brew = _have_brew()
    out: list[Installer] = []

    if agent == "claude":
        if brew:
            out.append(lambda: _run_logged(["brew", "install", "--cask", "claude-code"]))
        out.append(lambda: _run_logged(["npm", "install", "-g", "@anthropic-ai/claude-code"]))
        return out

    if agent == "codex":
        if brew:
            out.append(lambda: _run_logged(["brew", "install", "codex"]))
        out.append(lambda: _run_logged(["npm", "install", "-g", "@openai/codex"]))
        return out

    if agent == "gemini":
        if brew:
            out.append(lambda: _run_logged(["brew", "install", "gemini-cli"]))
        out.append(lambda: _run_logged(["npm", "install", "-g", "@google/gemini-cli"]))
        return out

    if agent == "copilot":
        if brew:
            out.append(lambda: _run_logged(["brew", "install", "copilot-cli"]))
        out.append(lambda: _run_logged(["npm", "install", "-g", "@github/copilot"]))
        return out

    if agent == "kimi":
        if shutil.which("uv"):
            out.append(lambda: _run_logged(["uv", "tool", "install", "--python", "3.13", "kimi-cli"]))
        out.append(lambda: _run_shell_logged("curl -LsSf https://code.kimi.com/install.sh | bash"))
        return out

    if agent == "opencode":
        if brew:
            out.append(lambda: _run_logged(["brew", "install", "opencode"]))
        out.append(lambda: _run_logged(["npm", "install", "-g", "@opencode-ai/cli"]))
        return out

    if agent == "qwen":
        if brew:
            out.append(lambda: _run_logged(["brew", "install", "qwen-code"]))
        out.append(lambda: _run_logged(["npm", "install", "-g", "@qwen-code/qwen-code@latest"]))
        return out

    return []


def try_ensure_node_npm() -> str:
    """Return ok | declined | failed."""
    if shutil.which("npm"):
        return "ok"
    if os.environ.get("MULTIAGENT_ASSUME_YES_DEPS") == "1":
        logging.info("multiagent: （MULTIAGENT_ASSUME_YES_DEPS=1）Node.js / npm を導入します")
    elif not prompt_yes("Node.js / npm をインストールしますか？（このエージェントの CLI 取得に必要です） [y/N] "):
        logging.info("multiagent: Node / npm の導入を見送りました。")
        return "declined"
    if _have_brew():
        return "ok" if _run_logged(["brew", "install", "node"]) and shutil.which("npm") else "failed"
    if shutil.which("apt-get"):
        subprocess.run(
            ["sudo", "apt-get", "update", "-y"],
            text=True,
            check=False,
        )
        return (
            "ok"
            if _run_logged(["sudo", "apt-get", "install", "-y", "nodejs", "npm"])
            and shutil.which("npm")
            else "failed"
        )
    if shutil.which("dnf"):
        return (
            "ok"
            if _run_logged(["sudo", "dnf", "install", "-y", "nodejs", "npm"]) and shutil.which("npm")
            else "failed"
        )
    if shutil.which("apk"):
        return (
            "ok"
            if _run_logged(["sudo", "apk", "add", "--no-cache", "nodejs", "npm"]) and shutil.which("npm")
            else "failed"
        )
    logging.warning("multiagent: npm が無く、brew/apt/dnf/apk でも導入できませんでした。Node.js を手動で入れてください。")
    return "failed"


def prompt_yes(question: str) -> bool:
    if not sys.stdin.isatty():
        logging.info("multiagent: （TTY ではないためスキップ）%s → いいえとして扱います", question.strip())
        return False
    try:
        reply = input(question).strip().lower()
    except EOFError:
        return False
    return reply in ("y", "yes")


def _may_need_npm_later(agent: str) -> bool:
    """cursor は brew のみ。それ以外は npm 系のフォールバックがありうる。"""
    return agent not in ("cursor", "kimi")


def ensure_agents_interactive(repo_root: Path, agents: Sequence[str] | None) -> int:
    want = list(agents) if agents else list(ALL_AGENT_NAMES)
    seen: set[str] = set()
    bases: list[str] = []
    for raw in want:
        base = raw.split("-", 1)[0]
        if base not in seen:
            seen.add(base)
            bases.append(base)

    npm_bootstrapped = False
    npm_unavailable = False

    for base in bases:
        if base not in ALL_AGENT_NAMES:
            continue
        disp = AGENTS[base].display_name if base in AGENTS else base

        if resolve_agent_executable(repo_root, base):
            logging.info("multiagent: %s (%s): 既に CLI あり → スキップ", disp, base)
            continue

        strategies = _installers_for_cursor() if base == "cursor" else _installers_for(base)
        if not strategies:
            if base == "cursor":
                logging.info(
                    "multiagent: Cursor: 自動インストールは macOS / Linux の公式 install script を前提にしています。"
                    " それ以外は https://cursor.com から手動で入れてください → スキップ"
                )
            else:
                logging.warning("multiagent: %s: 自動インストール手順未定義 → スキップ（手動で入れてください）", base)
            continue

        install_q = (
            f"{disp} の CLI をインストールしますか？（公式 install script、macOS では Homebrew fallback あり） [y/N] "
            if base == "cursor"
            else f"{disp} ({base}) の CLI をインストールしますか？ [y/N] "
        )
        if not prompt_yes(install_q):
            logging.info("multiagent: %s: インストールを見送りました", base)
            continue

        if _may_need_npm_later(base) and npm_unavailable:
            logging.warning("multiagent: %s: npm を使えないためこのエージェントのインストールをスキップします", base)
            continue

        if _may_need_npm_later(base) and not shutil.which("npm") and not npm_bootstrapped:
            _npm_st = try_ensure_node_npm()
            if _npm_st == "declined":
                logging.warning("multiagent: %s: npm が無いためこのエージェントのインストールをスキップします", base)
                continue
            if _npm_st != "ok":
                npm_unavailable = True
                logging.warning("multiagent: %s: Node.js / npm の導入に失敗したため、このエージェントはスキップします", base)
                continue
            npm_bootstrapped = True

        ok = False
        for step in strategies:
            if step():
                # Cursor / Kimi may install into ~/.local/bin which may not be in PATH
                if base in ("cursor", "kimi"):
                    _ensure_local_bin_in_path()
                if resolve_agent_executable(repo_root, base):
                    ok = True
                    break
        if not ok:
            logging.warning("multiagent: %s: インストールを試みましたが CLI が見つかりません。quickstart / 起動自体は続行します（必要なら vendor 手順で手動導入してください）", base)
            continue

    return 0


def _filter_argv(argv: list[str]) -> tuple[list[str], bool]:
    interactive = False
    out: list[str] = []
    for a in argv[1:]:
        if a in ("--interactive", "-i"):
            interactive = True
        else:
            out.append(a)
    return out, interactive


def main(argv: list[str]) -> int:
    if os.environ.get("MULTIAGENT_SKIP_AGENT_CLI_INSTALL") == "1":
        return 0
    pos, interactive = _filter_argv(argv)
    repo_root = _repo_root()
    agents = pos if pos else None

    if not interactive:
        if sys.stdin.isatty():
            logging.warning("multiagent: エージェント CLI の確認には --interactive を付けてください")
        return 0

    return ensure_agents_interactive(repo_root, agents)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main(sys.argv))
