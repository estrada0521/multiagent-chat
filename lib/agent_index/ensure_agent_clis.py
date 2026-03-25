"""Best-effort install of third-party agent CLIs when missing from PATH.

Invoked from bin/ensure-multiagent-agent-clis. Skipped when
MULTIAGENT_SKIP_AGENT_CLI_INSTALL=1. Does not replace vendor auth / API keys.
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


def _installers_for(agent: str) -> list[Installer]:
    """Return ordered install attempts (try brew/cask before npm where sensible)."""
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
        # Executable name is grok; several community packages exist — try common npm name.
        out.append(lambda: _run_logged(["npm", "install", "-g", "grok-cli"]))
        return out

    return []


def ensure_node_via_brew() -> bool:
    if shutil.which("npm"):
        return True
    if not _have_brew():
        return False
    return _run_logged(["brew", "install", "node"])


def ensure_agents(
    repo_root: Path,
    agents: Sequence[str] | None,
    *,
    install_cursor_hint: bool = True,
) -> int:
    want = list(agents) if agents else list(ALL_AGENT_NAMES)
    seen: set[str] = set()
    bases: list[str] = []
    for raw in want:
        base = raw.split("-", 1)[0]
        if base not in seen:
            seen.add(base)
            bases.append(base)

    if not shutil.which("npm") and _have_brew():
        print("multiagent: npm が無いため Homebrew で node を入れます…", file=sys.stderr, flush=True)
        if not ensure_node_via_brew():
            print(
                "multiagent: node/npm を入れられませんでした。"
                "手動で Node 20+ をインストールしてから再試行してください。",
                file=sys.stderr,
            )
            return 1

    if not shutil.which("npm"):
        print(
            "multiagent: npm が PATH にありません。Node.js / npm を入れてから再試行してください。",
            file=sys.stderr,
        )
        return 1

    failed: list[str] = []

    for base in bases:
        if base not in ALL_AGENT_NAMES:
            continue
        if resolve_agent_executable(repo_root, base):
            continue

        if base == "cursor":
            if install_cursor_hint:
                print(
                    "multiagent: cursor 用の `agent` CLI は Cursor 側のセットアップが必要です。"
                    "ここではスキップします（未導入なら multiagent が当該ペインを省略します）。",
                    file=sys.stderr,
                    flush=True,
                )
            continue

        strategies = _installers_for(base)
        if not strategies:
            print(
                f"multiagent: {base} の自動インストール手順が未定義です。手動で入れてください。",
                file=sys.stderr,
                flush=True,
            )
            failed.append(base)
            continue

        ok = False
        for step in strategies:
            if step():
                if resolve_agent_executable(repo_root, base):
                    ok = True
                    break
        if not ok:
            failed.append(base)

    if failed:
        names = ", ".join(sorted(set(failed)))
        print(
            f"multiagent: 次のエージェント CLI を解決できませんでした: {names}\n"
            "README や各ベンダーの公式手順で入れてから、不要なエージェントは "
            "`multiagent --agents claude,codex,...` で限定してください。",
            file=sys.stderr,
        )
        return 1

    return 0


def main(argv: list[str]) -> int:
    if os.environ.get("MULTIAGENT_SKIP_AGENT_CLI_INSTALL") == "1":
        return 0
    repo_root = _repo_root()
    agents = argv[1:] if len(argv) > 1 else None
    return ensure_agents(repo_root, agents)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main(sys.argv))
