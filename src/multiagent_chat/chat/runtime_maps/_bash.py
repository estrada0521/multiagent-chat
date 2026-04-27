"""Bash / exec_command → runtime label rules.

These tables control how shell commands appear in the running indicator.
Changing a label here affects every agent that executes bash commands.

The parser in runtime_parse._runtime_exec_command_events reads these sets
and dicts to decide the label; the detail text (file path, URL, etc.) is
extracted from the command arguments by the parser itself.
"""
from __future__ import annotations

# ── Simple file-read commands ─────────────────────────────────────────────────
# Last file-like positional arg displayed as "Read <file>"
READ_COMMANDS: frozenset[str] = frozenset({"sed", "cat", "head", "tail", "bat", "nl"})

# ── Directory exploration commands ────────────────────────────────────────────
# First positional arg (or cwd) displayed as "Explore <dir>"
EXPLORE_COMMANDS: frozenset[str] = frozenset({"ls", "find", "fd", "tree"})

# ── HTTP / network fetch ───────────────────────────────────────────────────────
# URL argument displayed as "Run <cmd> <url>"
HTTP_COMMANDS: frozenset[str] = frozenset({"curl", "wget", "http", "httpx"})

# ── Test runners ──────────────────────────────────────────────────────────────
# Displayed as "Run <runner>"
TEST_RUNNERS: frozenset[str] = frozenset(
    {"pytest", "jest", "vitest", "mocha", "rspec", "phpunit"}
)

# ── Build systems ─────────────────────────────────────────────────────────────
# Target displayed as "Run <system> <target>"
BUILD_SYSTEMS: frozenset[str] = frozenset(
    {"make", "cmake", "ninja", "gradle", "mvn", "msbuild", "bazel"}
)

# ── git subcommands ───────────────────────────────────────────────────────────
# Subcommand name → label  (detail is built by the parser)
GIT_SUBCOMMAND_LABELS: dict[str, str] = {
    "commit": "Run",
    "push":   "Run",
    "clone":  "Run",
    "fetch":  "Run",
    "pull":   "Run",
}

# ── Package managers ──────────────────────────────────────────────────────────
JS_PACKAGE_MANAGERS: frozenset[str] = frozenset({"npm", "yarn", "pnpm", "bun"})
PY_PACKAGE_MANAGERS: frozenset[str] = frozenset({"pip", "pip3", "uv"})

PKG_INSTALL_SUBCMDS: frozenset[str] = frozenset({"install", "add", "i", "ci"})
PKG_BUILD_SUBCMDS: frozenset[str] = frozenset({"run", "build", "start", "compile"})
PKG_TEST_SUBCMDS: frozenset[str] = frozenset({"test", "t"})
