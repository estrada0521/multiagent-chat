"""Prompt-based install of third-party agent CLIs when missing.

Skipped when MULTIAGENT_SKIP_AGENT_CLI_INSTALL=1.
Does not replace vendor auth / API keys.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

from agent_index.agent_registry import AGENTS, ALL_AGENT_NAMES


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_agent_executable(repo_root: Path, agent_name: str) -> str | None:
    """Mirror bin/multiagent resolve_agent_executable (base name, NVM, fallbacks)."""
    base = agent_name.split("-", 1)[0]
    adef = AGENTS.get(base)
    exe_name = adef.exe if adef else agent_name

    found = shutil.which(exe_name)
    if found:
        return found

    # Homebrew の cursor-cli は `cursor-agent` を PATH に載せる（レジストリの exe は agent）
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


def _have_brew() -> bool:
    return shutil.which("brew") is not None


def _run_logged(argv: list[str]) -> bool:
    print(f"multiagent: ensure-agent-clis: {' '.join(argv)}", file=sys.stderr, flush=True)
    proc = subprocess.run(argv, text=True)
    return proc.returncode == 0


Installer = Callable[[], bool]


def _installers_for_cursor() -> list[Installer]:
    """macOS + Homebrew: Cursor アプリと CLI エージェント（cursor-agent）。"""
    if sys.platform != "darwin" or not _have_brew():
        return []
    return [
        lambda: _run_logged(["brew", "install", "--cask", "cursor"]),
        lambda: _run_logged(["brew", "install", "--cask", "cursor-cli"]),
    ]


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

    if agent == "aider":
        if brew:
            out.append(lambda: _run_logged(["brew", "install", "aider"]))
        out.append(
            lambda: _run_logged([sys.executable, "-m", "pip", "install", "--user", "aider-chat"])
        )
        return out

    if agent == "grok":
        out.append(lambda: _run_logged(["npm", "install", "-g", "grok-cli"]))
        return out

    return []


def try_ensure_node_npm() -> str:
    """Return ok | declined | failed."""
    if shutil.which("npm"):
        return "ok"
    if os.environ.get("MULTIAGENT_ASSUME_YES_DEPS") == "1":
        print(
            "multiagent: （MULTIAGENT_ASSUME_YES_DEPS=1）Node.js / npm を導入します",
            file=sys.stderr,
            flush=True,
        )
    elif not prompt_yes("Node.js / npm をインストールしますか？（このエージェントの CLI 取得に必要です） [y/N] "):
        print("multiagent: Node / npm の導入を見送りました。", file=sys.stderr, flush=True)
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
    print(
        "multiagent: npm が無く、brew/apt/dnf/apk でも導入できませんでした。Node.js を手動で入れてください。",
        file=sys.stderr,
    )
    return "failed"


def prompt_yes(question: str) -> bool:
    if not sys.stdin.isatty():
        print(
            f"multiagent: （TTY ではないためスキップ）{question.strip()} → いいえとして扱います",
            file=sys.stderr,
            flush=True,
        )
        return False
    try:
        reply = input(question).strip().lower()
    except EOFError:
        return False
    return reply in ("y", "yes")


def _may_need_npm_later(agent: str) -> bool:
    """aider / cursor は brew のみ。それ以外は npm 系のフォールバックがありうる。"""
    return agent not in ("aider", "cursor")


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

    for base in bases:
        if base not in ALL_AGENT_NAMES:
            continue
        disp = AGENTS[base].display_name if base in AGENTS else base

        if resolve_agent_executable(repo_root, base):
            print(f"multiagent: {disp} ({base}): 既に CLI あり → スキップ", file=sys.stderr, flush=True)
            continue

        strategies = _installers_for_cursor() if base == "cursor" else _installers_for(base)
        if not strategies:
            if base == "cursor":
                print(
                    "multiagent: Cursor: 自動インストールは macOS + Homebrew のみです。"
                    " それ以外は https://cursor.com から手動で入れてください → スキップ",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(
                    f"multiagent: {base}: 自動インストール手順未定義 → スキップ（手動で入れてください）",
                    file=sys.stderr,
                    flush=True,
                )
            continue

        install_q = (
            f"{disp} を Homebrew でインストールしますか？（`cursor` と `cursor-cli` の cask） [y/N] "
            if base == "cursor"
            else f"{disp} ({base}) の CLI をインストールしますか？ [y/N] "
        )
        if not prompt_yes(install_q):
            print(f"multiagent: {base}: インストールを見送りました", file=sys.stderr, flush=True)
            continue

        if _may_need_npm_later(base) and not shutil.which("npm") and not npm_bootstrapped:
            _npm_st = try_ensure_node_npm()
            if _npm_st == "declined":
                print(
                    f"multiagent: {base}: npm が無いためこのエージェントのインストールをスキップします",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            if _npm_st != "ok":
                return 1
            npm_bootstrapped = True

        ok = False
        for step in strategies:
            if step():
                if resolve_agent_executable(repo_root, base):
                    ok = True
                    break
        if not ok:
            print(
                f"multiagent: {base}: インストールを試みましたが CLI が見つかりません（ネットワークや公式手順を確認）",
                file=sys.stderr,
                flush=True,
            )
            return 1

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
            print(
                "multiagent: エージェント CLI の確認には --interactive を付けてください",
                file=sys.stderr,
            )
        return 0

    return ensure_agents_interactive(repo_root, agents)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main(sys.argv))
