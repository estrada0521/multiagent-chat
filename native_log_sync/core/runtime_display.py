"""ツール呼び出し→ランタイム表示イベント。TOOL_MAP / QUIET_TOOLS は呼び出し側（エージェント別）で必ず渡す。"""

from __future__ import annotations

import json
import os
import re
import shlex
from urllib.parse import unquote, urlparse

from native_log_sync.core import bash_rules


_RUNTIME_RG_FLAGS_WITH_VALUES = {
    "-A", "-B", "-C", "-E", "-F", "-M", "-P", "-T", "-U", "-e", "-f", "-g", "-m", "-t",
    "--after-context", "--before-context", "--context", "--encoding", "--engine", "--file",
    "--glob", "--iglob", "--max-columns", "--max-count", "--path-separator", "--pre",
    "--pre-glob", "--replace", "--sort", "--sortr", "--type", "--type-not",
}
_RUNTIME_GREP_FLAGS_WITH_VALUES = {
    "-A", "-B", "-C", "-E", "-F", "-P", "-e", "-f", "-m",
    "--after-context", "--before-context", "--binary-files", "--color", "--context",
    "--devices", "--directories", "--exclude", "--exclude-dir", "--file", "--include",
    "--label", "--max-count",
}


def runtime_workspace_roots(workspace: str = "") -> list[str]:
    roots: list[str] = []
    for raw_root in (workspace, os.getcwd()):
        root = str(raw_root or "").strip()
        if not root:
            continue
        normalized = os.path.realpath(root)
        if normalized not in roots:
            roots.append(normalized)
    return roots


def runtime_display_path(value: object, *, workspace: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.match(r"^[a-z][a-z0-9+.-]*://", text, re.IGNORECASE):
        if not text.lower().startswith("file://"):
            return text
        try:
            parsed = urlparse(text)
            text = unquote(parsed.path or "").strip()
        except Exception:
            return text
    if not text:
        return ""
    normalized = os.path.normpath(text)
    if not os.path.isabs(normalized):
        return normalized.replace(os.sep, "/")
    normalized_real = os.path.realpath(normalized)
    for root in runtime_workspace_roots(workspace):
        try:
            rel = os.path.relpath(normalized_real, root)
        except Exception:
            continue
        if rel == ".":
            return "."
        if rel != ".." and not rel.startswith(f"..{os.sep}"):
            return rel.replace(os.sep, "/")
    return normalized_real.replace(os.sep, "/")


def runtime_display_text(action: str, detail: str = "") -> str:
    label = str(action or "").strip() or "Run"
    clean_detail = str(detail or "").strip()
    return f"{label} {clean_detail}".strip()


def runtime_search_detail(pattern: object, target: object = "", *, workspace: str = "") -> str:
    query = str(pattern or "").strip()
    where = runtime_display_path(target, workspace=workspace)
    if query and where:
        return f"{query} in {where}"
    return query or where


def runtime_argument_object(arguments: object) -> object:
    if not isinstance(arguments, str):
        return arguments
    text = arguments.strip()
    if not text:
        return ""
    if not text.startswith("{"):
        return text
    try:
        parsed = json.loads(text)
    except Exception:
        return text
    return parsed


def runtime_event(label: str, summary: str, *, source_id: str) -> dict:
    return {
        "kind": "fixed",
        "text": runtime_display_text(label, summary),
        "source_id": source_id,
    }


def runtime_first_arg(args_obj: object, *keys: str) -> str:
    if not isinstance(args_obj, dict):
        return ""
    for key in keys:
        value = args_obj.get(key)
        if value and isinstance(value, str):
            return value.strip()
    return ""


def runtime_positional_tokens(tokens: list[str], *, flags_with_values: set[str]) -> list[str]:
    positional: list[str] = []
    skip_next = False
    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            positional.extend(tokens[index + 1 :])
            break
        if token in flags_with_values:
            skip_next = True
            continue
        if token.startswith("-") and token != "-":
            continue
        positional.append(token)
    return positional


def runtime_exec_command_events(command: str, *, workspace: str = "") -> list[dict]:
    raw = str(command or "").strip()
    if not raw or "\n" in raw:
        return []
    try:
        tokens = shlex.split(raw, posix=True)
    except Exception:
        return []
    if not tokens:
        return []
    command_name = os.path.basename(tokens[0])
    lower_name = command_name.lower()

    if lower_name == "rg":
        if "--files" in tokens[1:]:
            positional = runtime_positional_tokens(tokens[1:], flags_with_values=_RUNTIME_RG_FLAGS_WITH_VALUES)
            target = runtime_display_path(positional[0] if positional else ".", workspace=workspace)
            return [runtime_event("Explore", target, source_id=f"tool:exec_command:explore:{target[:80]}")]
        positional = runtime_positional_tokens(tokens[1:], flags_with_values=_RUNTIME_RG_FLAGS_WITH_VALUES)
        if positional:
            pattern = positional[0]
            target = positional[1] if len(positional) > 1 else "."
            summary = runtime_search_detail(pattern, target, workspace=workspace)
            return [runtime_event("Search", summary, source_id=f"tool:exec_command:search:{summary[:80]}")]
        return []

    if lower_name in {"grep", "ggrep"}:
        positional = runtime_positional_tokens(tokens[1:], flags_with_values=_RUNTIME_GREP_FLAGS_WITH_VALUES)
        if positional:
            pattern = positional[0]
            target = positional[1] if len(positional) > 1 else "."
            summary = runtime_search_detail(pattern, target, workspace=workspace)
            return [runtime_event("Search", summary, source_id=f"tool:exec_command:search:{summary[:80]}")]
        return []

    if lower_name in bash_rules.READ_COMMANDS:
        positional = runtime_positional_tokens(tokens[1:], flags_with_values={"-n"})
        if positional:
            target = positional[-1]
            if "/" in target or "." in target:
                target = runtime_display_path(target, workspace=workspace)
                return [runtime_event("Read", target, source_id=f"tool:exec_command:read:{target[:80]}")]
        return []

    if lower_name in bash_rules.EXPLORE_COMMANDS:
        positional = runtime_positional_tokens(tokens[1:], flags_with_values=set())
        target = runtime_display_path(positional[0] if positional else ".", workspace=workspace)
        return [runtime_event("Explore", target, source_id=f"tool:exec_command:explore:{target[:80]}")]

    if lower_name == "git":
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd not in bash_rules.GIT_SUBCOMMAND_LABELS:
            return []
        if subcmd == "clone":
            url = next((t for t in tokens[2:] if not t.startswith("-")), "")
            return [runtime_event("Run", f"git clone {url}".strip(), source_id=f"tool:exec_command:git:clone:{url[:80]}")]
        return [runtime_event("Run", f"git {subcmd}", source_id=f"tool:exec_command:git:{subcmd}")]

    if lower_name in bash_rules.HTTP_COMMANDS:
        url = next((t for t in tokens[1:] if not t.startswith("-") and "://" in t), "")
        return [runtime_event("Run", f"{lower_name} {url}".strip(), source_id=f"tool:exec_command:run:{lower_name}:{url[:80]}")]

    if lower_name in bash_rules.JS_PACKAGE_MANAGERS:
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd in bash_rules.PKG_INSTALL_SUBCMDS:
            pkg = next((t for t in tokens[2:] if not t.startswith("-")), "")
            return [runtime_event("Run", f"{lower_name} install {pkg}".strip(), source_id=f"tool:exec_command:run:{lower_name}:install:{pkg[:60]}")]
        if subcmd in bash_rules.PKG_BUILD_SUBCMDS:
            script = next((t for t in tokens[2:] if not t.startswith("-")), "")
            return [runtime_event("Run", f"{lower_name} {subcmd} {script}".strip(), source_id=f"tool:exec_command:run:{lower_name}:{subcmd}:{script[:60]}")]
        if subcmd in bash_rules.PKG_TEST_SUBCMDS:
            return [runtime_event("Run", f"{lower_name} test", source_id=f"tool:exec_command:run:{lower_name}:test")]
        return []

    if lower_name in bash_rules.PY_PACKAGE_MANAGERS:
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd == "install":
            pkg = next((t for t in tokens[2:] if not t.startswith("-")), "")
            return [runtime_event("Run", f"{lower_name} install {pkg}".strip(), source_id=f"tool:exec_command:run:{lower_name}:install:{pkg[:60]}")]
        return []

    if lower_name == "brew":
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd in {"install", "reinstall"}:
            pkg = next((t for t in tokens[2:] if not t.startswith("-")), "")
            return [runtime_event("Run", f"brew {subcmd} {pkg}".strip(), source_id=f"tool:exec_command:run:brew:{subcmd}:{pkg[:60]}")]
        return []

    if lower_name in bash_rules.BUILD_SYSTEMS:
        target = next((t for t in tokens[1:] if not t.startswith("-")), "")
        return [runtime_event("Run", f"{lower_name} {target}".strip(), source_id=f"tool:exec_command:run:{lower_name}:{target[:60]}")]

    if lower_name == "cargo":
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        return [runtime_event("Run", f"cargo {subcmd}".strip(), source_id=f"tool:exec_command:run:cargo:{subcmd[:60]}")]

    if lower_name == "go":
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd in {"test", "build", "run", "install"}:
            return [runtime_event("Run", f"go {subcmd}", source_id=f"tool:exec_command:run:go:{subcmd}")]
        return []

    if lower_name in bash_rules.TEST_RUNNERS:
        return [runtime_event("Run", lower_name, source_id=f"tool:exec_command:run:{lower_name}")]

    return []


def apply_tool_entry(entry, args_obj: object, *, tool_name: str, workspace: str) -> list[dict]:
    label, mode, arg_keys = entry.label, entry.mode, entry.arg_keys
    target_keys = entry.target_keys
    if mode == "path":
        target = runtime_display_path(runtime_first_arg(args_obj, *arg_keys), workspace=workspace)
        if target:
            return [runtime_event(label, target, source_id=f"tool:{tool_name}:{label.lower()}:{target[:80]}")]
        return []
    if mode == "query":
        detail = str(runtime_first_arg(args_obj, *arg_keys) or "").strip()
        if detail or label:
            return [runtime_event(label, detail, source_id=f"tool:{tool_name}:{label.lower()}:{detail[:80]}")]
        return []
    if mode == "search":
        pattern = runtime_first_arg(args_obj, *arg_keys)
        target_raw = runtime_first_arg(args_obj, *target_keys) if target_keys else ""
        summary = runtime_search_detail(pattern, target_raw, workspace=workspace)
        if summary:
            return [runtime_event(label, summary, source_id=f"tool:{tool_name}:search:{summary[:80]}")]
        return []
    return []


def runtime_named_tool_events(
    tool_name: str,
    args_obj: object,
    *,
    workspace: str = "",
    tool_map: dict,
    quiet_tools: frozenset,
) -> list[dict]:
    lower_name = str(tool_name or "").strip().lower()

    if lower_name in quiet_tools:
        return []

    if lower_name == "exec_command":
        command = runtime_first_arg(args_obj, "cmd", "command")
        return runtime_exec_command_events(command, workspace=workspace)

    if lower_name in {"bash", "shell"}:
        command = runtime_first_arg(args_obj, "command", "cmd")
        return runtime_exec_command_events(command, workspace=workspace)

    entry = tool_map.get(lower_name)
    if entry is not None:
        return apply_tool_entry(entry, args_obj, tool_name=lower_name, workspace=workspace)

    return []


def runtime_tool_events(
    name: object,
    arguments: object,
    *,
    workspace: str = "",
    tool_map: dict,
    quiet_tools: frozenset,
) -> list[dict]:
    tool_name = str(name or "tool").strip() or "tool"
    args_obj = runtime_argument_object(arguments)
    return runtime_named_tool_events(
        tool_name, args_obj, workspace=workspace, tool_map=tool_map, quiet_tools=quiet_tools
    )
