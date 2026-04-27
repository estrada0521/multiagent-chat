from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

from .runtime_format import (
    _pane_runtime_gemini_with_occurrence_ids,
    _pane_runtime_with_occurrence_ids,
)
from .sync.cursor import _native_path_claim_key
from .thinking_kind import classify_gemini_message_kind, strip_sender_prefix


def _get_process_tree(pid: str) -> set[str]:
    """Get all descendant PIDs for a given PID using `ps`."""
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,ppid"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        children_map = {}
        for line in out.splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2:
                c, p = parts[0], parts[1]
                children_map.setdefault(p, []).append(c)

        pids = {pid}
        q = [pid]
        while q:
            curr = q.pop(0)
            for c in children_map.get(curr, []):
                if c not in pids:
                    pids.add(c)
                    q.append(c)
        return pids
    except Exception:
        return {pid}


def _resolve_native_log_file(
    pane_pid: str,
    log_pattern: str,
    base_name: str = "",
) -> str | None:
    """Find an open file matching log_pattern for pane_pid (including descendants)."""
    pids = _get_process_tree(str(pane_pid).strip())
    if not pids:
        return None

    if base_name == "copilot":
        for pid in pids:
            state_dir = Path.home() / ".copilot" / "session-state"
            if not state_dir.exists():
                continue
            for lock_file in state_dir.glob(f"*/inuse.{pid}.lock"):
                session_dir = lock_file.parent
                log_file = session_dir / "events.jsonl"
                if log_file.exists():
                    return str(log_file)

    try:
        cmd = ["lsof", "-p", ",".join(pids), "-Fn"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
        ranked_candidates: list[tuple[float, str]] = []
        seen_claim_keys: set[str] = set()
        for line in out.splitlines():
            if not line.startswith("n"):
                continue
            path = line[1:]
            if not re.search(log_pattern, path):
                continue
            stat_result: os.stat_result | None = None
            mtime = -1.0
            try:
                stat_result = os.stat(path)
                mtime = stat_result.st_mtime
            except OSError:
                pass
            claim_key = _native_path_claim_key(path, stat_result=stat_result)
            if claim_key in seen_claim_keys:
                continue
            seen_claim_keys.add(claim_key)
            ranked_candidates.append((mtime, path))
        if ranked_candidates:
            ranked_candidates.sort(key=lambda item: item[0], reverse=True)
            return ranked_candidates[0][1]
    except Exception:
        pass
    return None


def pane_pid_opens_file(pane_pid: str, target_path: str) -> bool:
    """True if any process in *pane_pid*'s tree has *target_path* open (realpath match)."""
    try:
        target = os.path.realpath(str(target_path))
    except OSError:
        target = str(target_path)
    pids = _get_process_tree(str(pane_pid).strip())
    if not pids:
        return False
    try:
        cmd = ["lsof", "-p", ",".join(pids), "-Fn"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
        for line in out.splitlines():
            if not line.startswith("n"):
                continue
            path = line[1:]
            try:
                if os.path.realpath(path) == target:
                    return True
            except OSError:
                if path == target:
                    return True
    except Exception:
        pass
    return False


def _parse_native_codex_log(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    """Parse Codex rollout JSONL file."""
    try:
        tail_bytes = 65_536
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - tail_bytes)
            f.seek(start)
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        if start > 0 and lines:
            lines = lines[1:]

        events = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "response_item" and "payload" in data:
                payload = data["payload"]
                ptype = payload.get("type")

                if ptype == "reasoning":
                    summary = payload.get("summary") or []
                    for item in summary:
                        if not isinstance(item, dict):
                            continue
                        text = str(item.get("text") or "").strip()
                        if not text:
                            continue
                        events.append(
                            {
                                "kind": "fixed",
                                "text": f"✦ {text}",
                                "source_id": f"thought:codex:✦ {text}",
                            }
                        )
                elif ptype == "custom_tool_call":
                    name = payload.get("name", "")
                    inp = payload.get("input", "")
                    events.extend(_runtime_tool_events(name, inp, workspace=workspace))
                elif ptype == "function_call":
                    name = payload.get("name", "")
                    args = payload.get("arguments", "")
                    events.extend(_runtime_tool_events(name, args, workspace=workspace))
            if data.get("type") == "event_msg" and "payload" in data:
                payload = data["payload"] or {}
                if payload.get("type") == "agent_reasoning":
                    text = str(payload.get("text") or "").strip()
                    if text:
                        events.append(
                            {
                                "kind": "fixed",
                                "text": f"✦ {text}",
                                "source_id": f"thought:codex:✦ {text}",
                            }
                        )
        return _pane_runtime_gemini_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native codex log {filepath}: {e}")
        return None


_RUNTIME_APPLY_PATCH_FILE_RE = re.compile(
    r"^\*\*\*\s+(Add|Update|Delete)\s+File:\s+(.+?)\s*$",
    re.MULTILINE,
)
_RUNTIME_QUIET_TOOL_NAMES = {"write_stdin", "todowrite", "todoread"}
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
_RUNTIME_ACTION_ING = {
    "Bash": "Bashing",
    "Build": "Building",
    "Clone": "Cloning",
    "Commit": "Committing",
    "Create": "Creating",
    "Delete": "Deleting",
    "Edit": "Editing",
    "Explored": "Exploring",
    "Fetch": "Fetching",
    "Glob": "Globbing",
    "Install": "Installing",
    "Push": "Pushing",
    "Read": "Reading",
    "Run": "Running",
    "Search": "Searching",
    "Spawn": "Spawning",
    "Test": "Testing",
    "Think": "Thinking",
    "Update": "Updating",
    "View": "Viewing",
    "Write": "Writing",
}

_GEMINI_PLAN_PREFIX_RE = re.compile(
    r"^\s*(?:✦\s*)?(?:i\s+will|i['’]ll|i\s+am\s+going\s+to|let\s+me)\b\s*",
    re.IGNORECASE,
)
_GEMINI_PATHLIKE_RE = re.compile(r"(?:^|/)[\w.-]+\.[A-Za-z0-9]+(?:$|[/:#?])|/")


def _runtime_workspace_roots(workspace: str = "") -> list[str]:
    roots: list[str] = []
    for raw_root in (workspace, os.getcwd()):
        root = str(raw_root or "").strip()
        if not root:
            continue
        normalized = os.path.realpath(root)
        if normalized not in roots:
            roots.append(normalized)
    return roots


def _runtime_display_path(value: object, *, workspace: str = "") -> str:
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
    for root in _runtime_workspace_roots(workspace):
        try:
            rel = os.path.relpath(normalized_real, root)
        except Exception:
            continue
        if rel == ".":
            return "."
        if rel != ".." and not rel.startswith(f"..{os.sep}"):
            return rel.replace(os.sep, "/")
    return normalized_real.replace(os.sep, "/")


def _runtime_display_text(action: str, detail: str = "") -> str:
    gerund = _RUNTIME_ACTION_ING.get(str(action or "").strip(), str(action or "").strip() or "Running")
    clean_detail = str(detail or "").strip()
    return f"{gerund} {clean_detail}".strip()


def _runtime_search_detail(pattern: object, target: object = "", *, workspace: str = "") -> str:
    query = str(pattern or "").strip()
    where = _runtime_display_path(target, workspace=workspace)
    if query and where:
        return f"{query} in {where}"
    return query or where


def _runtime_argument_object(arguments: object) -> object:
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


def _runtime_event(label: str, summary: str, *, source_id: str) -> dict:
    return {
        "kind": "fixed",
        "text": _runtime_display_text(label, summary),
        "source_id": source_id,
    }


def _runtime_first_arg(args_obj: object, *keys: str) -> str:
    if not isinstance(args_obj, dict):
        return ""
    for key in keys:
        value = args_obj.get(key)
        if value and isinstance(value, str):
            return value.strip()
    return ""


def _runtime_positional_tokens(tokens: list[str], *, flags_with_values: set[str]) -> list[str]:
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


def _runtime_exec_command_events(command: str, *, workspace: str = "") -> list[dict]:
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
            positional = _runtime_positional_tokens(tokens[1:], flags_with_values=_RUNTIME_RG_FLAGS_WITH_VALUES)
            target = _runtime_display_path(positional[0] if positional else ".", workspace=workspace)
            return [_runtime_event("Explored", target, source_id=f"tool:exec_command:explored:{target[:80]}")]
        positional = _runtime_positional_tokens(tokens[1:], flags_with_values=_RUNTIME_RG_FLAGS_WITH_VALUES)
        if positional:
            pattern = positional[0]
            target = positional[1] if len(positional) > 1 else "."
            summary = _runtime_search_detail(pattern, target, workspace=workspace)
            return [_runtime_event("Search", summary, source_id=f"tool:exec_command:search:{summary[:80]}")]
        return []
    if lower_name in {"grep", "ggrep"}:
        positional = _runtime_positional_tokens(tokens[1:], flags_with_values=_RUNTIME_GREP_FLAGS_WITH_VALUES)
        if positional:
            pattern = positional[0]
            target = positional[1] if len(positional) > 1 else "."
            summary = _runtime_search_detail(pattern, target, workspace=workspace)
            return [_runtime_event("Search", summary, source_id=f"tool:exec_command:search:{summary[:80]}")]
        return []
    if lower_name in {"sed", "cat", "head", "tail", "bat", "nl"}:
        positional = _runtime_positional_tokens(tokens[1:], flags_with_values={"-n"})
        if positional:
            target = positional[-1]
            if "/" in target or "." in target:
                target = _runtime_display_path(target, workspace=workspace)
                return [_runtime_event("Read", target, source_id=f"tool:exec_command:read:{target[:80]}")]
        return []
    if lower_name in {"ls", "find", "fd", "tree"}:
        positional = _runtime_positional_tokens(tokens[1:], flags_with_values=set())
        target = _runtime_display_path(positional[0] if positional else ".", workspace=workspace)
        return [_runtime_event("Explored", target, source_id=f"tool:exec_command:explored:{target[:80]}")]
    if lower_name == "git":
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd == "commit":
            return [_runtime_event("Commit", "", source_id="tool:exec_command:git:commit")]
        if subcmd == "push":
            return [_runtime_event("Push", "", source_id="tool:exec_command:git:push")]
        if subcmd == "clone":
            url = next((t for t in tokens[2:] if not t.startswith("-")), "")
            return [_runtime_event("Clone", url, source_id=f"tool:exec_command:git:clone:{url[:80]}")]
        if subcmd in {"fetch", "pull"}:
            return [_runtime_event("Fetch", "", source_id=f"tool:exec_command:git:{subcmd}")]
        return []
    if lower_name in {"curl", "wget", "http", "httpx"}:
        url = next((t for t in tokens[1:] if not t.startswith("-") and "://" in t), "")
        return [_runtime_event("Fetch", url, source_id=f"tool:exec_command:fetch:{url[:80]}")]
    if lower_name in {"npm", "yarn", "pnpm", "bun"}:
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd in {"install", "add", "i", "ci"}:
            pkg = next((t for t in tokens[2:] if not t.startswith("-")), "")
            return [_runtime_event("Install", pkg, source_id=f"tool:exec_command:install:{lower_name}:{pkg[:60]}")]
        if subcmd in {"run", "build", "start", "compile"}:
            script = next((t for t in tokens[2:] if not t.startswith("-")), "")
            return [_runtime_event("Build", script, source_id=f"tool:exec_command:build:{lower_name}:{script[:60]}")]
        if subcmd in {"test", "t"}:
            return [_runtime_event("Test", "", source_id=f"tool:exec_command:test:{lower_name}")]
        return []
    if lower_name in {"pip", "pip3", "uv"}:
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd == "install":
            pkg = next((t for t in tokens[2:] if not t.startswith("-")), "")
            return [_runtime_event("Install", pkg, source_id=f"tool:exec_command:install:{lower_name}:{pkg[:60]}")]
        return []
    if lower_name == "brew":
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd in {"install", "reinstall"}:
            pkg = next((t for t in tokens[2:] if not t.startswith("-")), "")
            return [_runtime_event("Install", pkg, source_id=f"tool:exec_command:install:brew:{pkg[:60]}")]
        return []
    if lower_name in {"make", "cmake", "ninja", "gradle", "mvn", "msbuild", "bazel"}:
        target = next((t for t in tokens[1:] if not t.startswith("-")), "")
        return [_runtime_event("Build", target, source_id=f"tool:exec_command:build:{lower_name}:{target[:60]}")]
    if lower_name == "cargo":
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd in {"test", "t", "nextest"}:
            return [_runtime_event("Test", "", source_id="tool:exec_command:test:cargo")]
        return [_runtime_event("Build", subcmd, source_id=f"tool:exec_command:build:cargo:{subcmd[:60]}")]
    if lower_name == "go":
        subcmd = tokens[1].lower() if len(tokens) > 1 else ""
        if subcmd == "test":
            return [_runtime_event("Test", "", source_id="tool:exec_command:test:go")]
        if subcmd in {"build", "run", "install"}:
            return [_runtime_event("Build", subcmd, source_id=f"tool:exec_command:build:go:{subcmd}")]
        return []
    if lower_name in {"pytest", "jest", "vitest", "mocha", "rspec", "phpunit"}:
        return [_runtime_event("Test", "", source_id=f"tool:exec_command:test:{lower_name}")]
    return []


def _runtime_named_tool_events(tool_name: str, args_obj: object, *, workspace: str = "") -> list[dict]:
    lower_name = str(tool_name or "").strip().lower()
    if lower_name in _RUNTIME_QUIET_TOOL_NAMES:
        return []
    if lower_name == "exec_command":
        command = _runtime_first_arg(args_obj, "cmd", "command")
        return _runtime_exec_command_events(command, workspace=workspace)
    if lower_name in {"list_mcp_resources", "list_mcp_resource_templates"}:
        target = _runtime_first_arg(args_obj, "server") or "mcp"
        return [_runtime_event("Explored", target, source_id=f"tool:{lower_name}:explored:{target[:80]}")]
    if lower_name in {"read_mcp_resource", "open"}:
        target = _runtime_display_path(_runtime_first_arg(args_obj, "uri", "ref_id", "path"), workspace=workspace)
        if target:
            return [_runtime_event("Read", target, source_id=f"tool:{lower_name}:read:{target[:80]}")]
        return []
    if lower_name in {"find", "search_query"}:
        query = _runtime_first_arg(args_obj, "pattern", "q", "query")
        target = _runtime_first_arg(args_obj, "ref_id")
        summary = _runtime_search_detail(query, target, workspace=workspace)
        if summary:
            return [_runtime_event("Search", summary, source_id=f"tool:{lower_name}:search:{summary[:80]}")]
        return []
    if lower_name in {"grep", "ggrep"}:
        summary = _runtime_search_detail(_runtime_first_arg(args_obj, "pattern", "q", "query"), workspace=workspace)
        if summary:
            return [_runtime_event("Search", summary, source_id=f"tool:{lower_name}:search:{summary[:80]}")]
        return []
    if lower_name in {"view", "view_image"}:
        target = _runtime_display_path(_runtime_first_arg(args_obj, "path"), workspace=workspace)
        if target:
            return [_runtime_event("View", target, source_id=f"tool:view_image:view:{target[:80]}")]
        return []
    # Claude Code native tools
    if lower_name == "bash":
        command = _runtime_first_arg(args_obj, "command", "cmd")
        events = _runtime_exec_command_events(command, workspace=workspace)
        if events:
            return events
        summary = str(command or "").strip()[:80]
        return [_runtime_event("Bash", summary, source_id=f"tool:bash:run:{summary[:80]}")]
    if lower_name in {"read", "notebookread"}:
        target = _runtime_display_path(_runtime_first_arg(args_obj, "file_path", "path", "notebook_path"), workspace=workspace)
        if target:
            return [_runtime_event("Read", target, source_id=f"tool:{lower_name}:read:{target[:80]}")]
        return []
    if lower_name == "write":
        target = _runtime_display_path(_runtime_first_arg(args_obj, "file_path", "path"), workspace=workspace)
        if target:
            return [_runtime_event("Write", target, source_id=f"tool:write:write:{target[:80]}")]
        return []
    if lower_name == "edit":
        target = _runtime_display_path(_runtime_first_arg(args_obj, "file_path", "path"), workspace=workspace)
        if target:
            return [_runtime_event("Edit", target, source_id=f"tool:edit:edit:{target[:80]}")]
        return []
    if lower_name == "notebookedit":
        target = _runtime_display_path(_runtime_first_arg(args_obj, "notebook_path", "path"), workspace=workspace)
        if target:
            return [_runtime_event("Edit", target, source_id=f"tool:notebookedit:edit:{target[:80]}")]
        return []
    if lower_name == "glob":
        pattern = _runtime_first_arg(args_obj, "pattern")
        if pattern:
            return [_runtime_event("Glob", pattern, source_id=f"tool:glob:glob:{pattern[:80]}")]
        return []
    if lower_name in {"websearch", "web_search"}:
        query = _runtime_first_arg(args_obj, "query", "q")
        if query:
            return [_runtime_event("Search", query, source_id=f"tool:{lower_name}:search:{query[:80]}")]
        return []
    if lower_name in {"webfetch", "web_fetch"}:
        url = _runtime_first_arg(args_obj, "url", "uri", "prompt")
        return [_runtime_event("Fetch", url, source_id=f"tool:{lower_name}:fetch:{url[:80]}")]
    if lower_name == "agent":
        desc = _runtime_first_arg(args_obj, "description", "prompt")
        summary = (desc[:60] + "…") if len(desc) > 60 else desc
        return [_runtime_event("Spawn", summary, source_id=f"tool:agent:spawn:{summary[:80]}")]
    return []


def _runtime_tool_summary(arguments: object, *, workspace: str = "") -> str:
    args_obj: object = _runtime_argument_object(arguments)
    if isinstance(args_obj, str):
        text = args_obj.strip()
        if not text:
            return ""
        if text.startswith("*** Begin Patch"):
            return ""
        if os.path.isabs(text):
            return _runtime_display_path(text, workspace=workspace)
        return text[:80]
    if not isinstance(args_obj, dict):
        return ""
    for key in ("cmd", "command", "query", "pattern", "description", "prompt", "path", "file_path", "uri", "ref_id"):
        value = args_obj.get(key)
        if value and isinstance(value, str):
            if key in {"path", "file_path", "uri", "ref_id"}:
                return _runtime_display_path(value, workspace=workspace)[:80]
            return value[:80]
    return ""


def _runtime_apply_patch_ops(arguments: object) -> list[tuple[str, str]]:
    args_obj: object = arguments
    if isinstance(arguments, str):
        text = arguments.strip()
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                args_obj = parsed
            else:
                args_obj = text
        else:
            args_obj = text
    patch_text = ""
    if isinstance(args_obj, dict):
        for key in ("patch", "input", "arguments"):
            value = args_obj.get(key)
            if isinstance(value, str) and "*** Begin Patch" in value:
                patch_text = value
                break
    elif isinstance(args_obj, str) and "*** Begin Patch" in args_obj:
        patch_text = args_obj
    if not patch_text:
        return []
    ops: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    action_map = {"Add": "Create", "Update": "Edit", "Delete": "Delete"}
    for action, raw_path in _RUNTIME_APPLY_PATCH_FILE_RE.findall(patch_text):
        path = str(raw_path or "").strip()
        if not path:
            continue
        verb = action_map.get(action, "Edit")
        item = (verb, path)
        if item in seen:
            continue
        seen.add(item)
        ops.append(item)
    return ops


def _runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    tool_name = str(name or "tool").strip() or "tool"
    if tool_name.lower() == "apply_patch":
        ops = _runtime_apply_patch_ops(arguments)
        if ops:
            events: list[dict] = []
            for verb, path in ops[:8]:
                display_path = _runtime_display_path(path, workspace=workspace)
                events.append(
                    {
                        "kind": "fixed",
                        "text": _runtime_display_text(verb, display_path),
                        "source_id": f"tool:apply_patch:{verb.lower()}:{path[:80]}",
                    }
                )
            remaining = len(ops) - 8
            if remaining > 0:
                events.append(
                    {
                        "kind": "fixed",
                        "text": _runtime_display_text("Edit", f"{remaining} more files"),
                        "source_id": f"tool:apply_patch:extra:{remaining}",
                    }
                )
            return events
    args_obj = _runtime_argument_object(arguments)
    named_events = _runtime_named_tool_events(tool_name, args_obj, workspace=workspace)
    if named_events:
        return named_events
    if tool_name.lower() in _RUNTIME_QUIET_TOOL_NAMES:
        return []
    summary = _runtime_tool_summary(arguments, workspace=workspace)
    detail = f"{tool_name} {summary}".strip()
    return [
        {
            "kind": "fixed",
            "text": _runtime_display_text("Run", detail),
            "source_id": f"tool:{tool_name}:{summary[:40]}",
        }
    ]


def _gemini_message_texts_and_thought(message: dict) -> tuple[list[str], bool]:
    content = message.get("content", []) if isinstance(message, dict) else []
    texts: list[str] = []
    has_thought_part = False
    if isinstance(content, str):
        text = content.strip()
        if text:
            texts.append(text)
    elif isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("thought") is True:
                has_thought_part = True
            text = str(part.get("text") or "").strip()
            if text:
                texts.append(text)
    return texts, has_thought_part


def _gemini_is_pathlike_token(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text.startswith(("/", "./", "../", "~")):
        return True
    if _GEMINI_PATHLIKE_RE.search(text):
        return True
    return bool(re.search(r"\.[A-Za-z0-9]{1,8}(?:$|[#:?])", text))


def _gemini_runtime_token(value: str, *, workspace: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if _gemini_is_pathlike_token(text):
        return _runtime_display_path(text, workspace=workspace)
    return text


def _gemini_clean_plan_text(text: str) -> str:
    body = strip_sender_prefix(str(text or "")).strip()
    if not body:
        return ""
    first_line = body.splitlines()[0].strip()
    first_line = _GEMINI_PLAN_PREFIX_RE.sub("", first_line, count=1).strip()
    first_line = re.sub(r"^(?:to|and|then)\s+", "", first_line, flags=re.IGNORECASE).strip()
    return first_line


def _gemini_runtime_action_detail(text: str, *, workspace: str = "") -> tuple[str, str]:
    body = strip_sender_prefix(str(text or "")).strip()
    first_line = body.splitlines()[0].strip() if body else ""
    lower = first_line.lower()
    if re.search(r"\b(image|screenshot|photo|picture|attached)\b", lower) and re.search(
        r"\b(view|look|inspect|examine|check|read)\b",
        lower,
    ):
        action = "View"
    elif re.search(r"\b(search|find|locate|look\s+for|grep|rg)\b", lower):
        action = "Search"
    elif re.search(r"\b(commit|committing)\b", lower):
        action = "Commit"
    elif re.search(r"\b(test|verify|validate|check\s+whether)\b", lower):
        action = "Test"
    elif re.search(r"\b(run|execute|restart|launch|start)\b", lower):
        action = "Run"
    elif re.search(
        r"\b(update|modify|change|adjust|refine|fix|align|add|remove|replace|ensure|include|clean|simplify|deduplicate)\b",
        lower,
    ):
        action = "Update"
    elif re.search(r"\b(write|create|scaffold|generate|add\s+a\s+new)\b", lower):
        action = "Write"
    elif re.search(r"\b(read|open|inspect|examine|review|check|look\s+at|analy[sz]e)\b", lower):
        action = "Read"
    else:
        action = "Think"

    backticks = [item.strip() for item in re.findall(r"`([^`]+)`", first_line) if item.strip()]
    path_tokens = [item for item in backticks if _gemini_is_pathlike_token(item)]
    non_path_tokens = [item for item in backticks if item not in path_tokens]
    if action == "Search" and len(backticks) >= 2:
        query = non_path_tokens[0] if non_path_tokens else backticks[0]
        target = path_tokens[0] if path_tokens else backticks[-1]
        detail = _runtime_search_detail(query, target, workspace=workspace)
    elif action in {"Read", "Update", "View", "Write"} and path_tokens:
        detail = _gemini_runtime_token(path_tokens[0], workspace=workspace)
    elif backticks:
        detail = " ".join(_gemini_runtime_token(item, workspace=workspace) for item in backticks[:2]).strip()
    elif action == "View" and re.search(r"\b(attached|this)\s+(?:image|screenshot|photo|picture)\b", lower):
        detail = "attached image"
    else:
        detail = _gemini_clean_plan_text(first_line)
        detail = re.sub(
            r"^(?:search(?:\s+for)?|find|locate|read|open|inspect|examine|review|check|update|modify|change|adjust|refine|fix|run|execute|test|verify|validate|write|create)\s+",
            "",
            detail,
            flags=re.IGNORECASE,
        ).strip()
    detail = re.sub(r"\s+", " ", detail).strip(" .")
    if len(detail) > 120:
        detail = f"{detail[:117].rstrip()}..."
    return action, detail


def _parse_native_gemini_log(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    """Parse Gemini session JSONL for runtime-only planning/thought messages."""
    try:
        tail_bytes = 32_768
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - tail_bytes)
            f.seek(start)
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        if start > 0 and lines:
            lines = lines[1:]
        events: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict) or message.get("type") != "gemini":
                continue
            texts, has_thought_part = _gemini_message_texts_and_thought(message)
            if not texts:
                continue
            kind = classify_gemini_message_kind(texts, has_thought_part=has_thought_part)
            first_text = texts[0]
            if kind != "agent-thinking" and not _GEMINI_PLAN_PREFIX_RE.match(strip_sender_prefix(first_text)):
                continue
            action, detail = _gemini_runtime_action_detail(first_text, workspace=workspace)
            msg_id = str(message.get("id") or "").strip()[:12] or str(len(events))
            source_detail = f"{action}:{detail[:80]}"
            events.append(_runtime_event(action, detail, source_id=f"gemini:{msg_id}:{source_detail}"))
        return _pane_runtime_gemini_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native gemini log {filepath}: {e}")
        return None


def _parse_cursor_jsonl_runtime(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    """Extract recent tool_use events from a cursor-tracked JSONL for runtime display."""
    try:
        tail_bytes = 32_768
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - tail_bytes)
            f.seek(start)
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        if start > 0 and lines:
            lines = lines[1:]

        events: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") == "assistant":
                msg = entry.get("message")
                if not isinstance(msg, dict):
                    continue
                for c in (msg.get("content") or []):
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        name = c.get("name", "tool")
                        inp = c.get("input") or {}
                        events.extend(_runtime_tool_events(name, inp, workspace=workspace))

            if entry.get("type") == "tool.execution_start":
                data = entry.get("data") or {}
                name = data.get("toolName", "tool")
                args = data.get("arguments") or {}
                events.extend(_runtime_tool_events(name, args, workspace=workspace))
            if entry.get("type") == "assistant.message":
                data = entry.get("data") or {}
                for tr in (data.get("toolRequests") or []):
                    if not isinstance(tr, dict):
                        continue
                    name = tr.get("name", "tool")
                    args = tr.get("arguments") or {}
                    events.extend(_runtime_tool_events(name, args, workspace=workspace))

            if entry.get("role") == "assistant":
                msg = entry.get("message")
                if not isinstance(msg, dict):
                    continue
                for c in (msg.get("content") or []):
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        name = c.get("name", "tool")
                        inp = c.get("input") or {}
                        events.extend(_runtime_tool_events(name, inp, workspace=workspace))

        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse cursor JSONL runtime {filepath}: {e}")
        return None


def _pane_runtime_new_events(previous: list[dict], current: list[dict]) -> list[dict]:
    if not current:
        return []
    prev_ids = [str((item or {}).get("source_id") or "") for item in (previous or [])]
    cur_ids = [str((item or {}).get("source_id") or "") for item in current]
    max_overlap = min(len(prev_ids), len(cur_ids))
    for overlap in range(max_overlap, 0, -1):
        if prev_ids[-overlap:] == cur_ids[:overlap]:
            return current[overlap:]
    return [] if prev_ids == cur_ids else current
