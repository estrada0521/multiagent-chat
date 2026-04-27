"""exec_command 内のシェルコマンド名→表示カテゴリ用の集合（エージェント非依存の構文層）。"""

from __future__ import annotations

READ_COMMANDS: frozenset[str] = frozenset({"sed", "cat", "head", "tail", "bat", "nl"})
EXPLORE_COMMANDS: frozenset[str] = frozenset({"ls", "find", "fd", "tree"})
HTTP_COMMANDS: frozenset[str] = frozenset({"curl", "wget", "http", "httpx"})
TEST_RUNNERS: frozenset[str] = frozenset(
    {"pytest", "jest", "vitest", "mocha", "rspec", "phpunit"}
)
BUILD_SYSTEMS: frozenset[str] = frozenset(
    {"make", "cmake", "ninja", "gradle", "mvn", "msbuild", "bazel"}
)
GIT_SUBCOMMAND_LABELS: dict[str, str] = {
    "commit": "Run",
    "push": "Run",
    "clone": "Run",
    "fetch": "Run",
    "pull": "Run",
}
JS_PACKAGE_MANAGERS: frozenset[str] = frozenset({"npm", "yarn", "pnpm", "bun"})
PY_PACKAGE_MANAGERS: frozenset[str] = frozenset({"pip", "pip3", "uv"})
PKG_INSTALL_SUBCMDS: frozenset[str] = frozenset({"install", "add", "i", "ci"})
PKG_BUILD_SUBCMDS: frozenset[str] = frozenset({"run", "build", "start", "compile"})
PKG_TEST_SUBCMDS: frozenset[str] = frozenset({"test", "t"})
