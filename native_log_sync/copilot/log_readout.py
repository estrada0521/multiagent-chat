"""Copilot CLI: events.jsonl のランタイム表示とチャット index 同期。"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid

from multiagent_chat.chat.sync.cursor import NativeLogCursor, _advance_native_cursor, _cursor_binding_changed
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.core.jsonl_tail_runtime import parse_jsonl_tail_for_runtime
from native_log_sync.core.runtime_display import runtime_event
from native_log_sync.core.runtime_paths import display_path

GITHUB_TOOLS: frozenset[str] = frozenset(
    {
        "github-mcp-server-actions_list",
        "github-mcp-server-get_commit",
        "github-mcp-server-get_file_contents",
        "github-mcp-server-get_job_logs",
        "github-mcp-server-list_commits",
        "github-mcp-server-search_code",
    }
)

MAIN_LABEL: dict[str, str] = {
    "report_intent": "Intent",
    "bash": "Shell",
    "glob": "Explore",
    "grep": "Search",
    "rg": "Search",
    "view": "Read",
    "apply_patch": "Patch",
    "web_fetch": "Fetch",
    "web_search": "Search",
    "skill": "Skill",
    "create": "Write",
    "edit": "Edit",
    "read_bash": "Bash",
    "write_bash": "Bash",
    "stop_bash": "Bash",
    "list_bash": "Bash",
    "list_agents": "Agents",
    "read_agent": "Agent",
    "task": "Task",
    "sql": "SQL",
    "ask_user": "Ask",
    "store_memory": "Memory",
    "fetch_copilot_cli_documentation": "Docs",
}


def _coerce_args(arguments: object) -> object:
    if not isinstance(arguments, str):
        return arguments
    t = arguments.strip()
    if not t or not t.startswith("{"):
        return t
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return t

_PATCH = re.compile(r"^\*\*\* Update File:\s*(.+)\s*$", re.MULTILINE)


def _patch_target_path(arg: object) -> str:
    text = arg if isinstance(arg, str) else ""
    if isinstance(arg, dict):
        for k in ("patch", "input", "content", "text"):
            v = arg.get(k)
            if isinstance(v, str) and v.strip():
                text = v
                break
    m = _PATCH.search(text)
    return m.group(1).strip() if m else "(patch)"


def _pick(d: object, *keys: str) -> str:
    if not isinstance(d, dict):
        return ""
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _grep_sub(a: dict, *, use_glob: bool) -> str:
    pat = _pick(a, "pattern", "q", "query")
    tgt = _pick(a, "path", "dir_path", "glob") if use_glob else _pick(a, "path", "dir_path")
    if pat and tgt:
        return f"{pat} in {tgt}"
    return pat or tgt


def _gh_sub(raw: str, a: object) -> str:
    if not isinstance(a, dict):
        return raw
    owner = str(a.get("owner") or "").strip()
    repo = str(a.get("repo") or "").strip()
    base = f"{owner}/{repo}".strip("/") if owner or repo else ""
    tail = raw.removeprefix("github-mcp-server-") if raw.startswith("github-mcp-server-") else raw
    q = str(a.get("query") or "").strip()
    path = str(a.get("path") or "").strip()
    sha = str(a.get("sha") or "").strip()
    run_id = a.get("run_id")
    method = str(a.get("method") or "").strip()
    bits = [tail]
    if base:
        bits.append(base)
    if path:
        bits.append(path)
    if sha:
        bits.append(sha[:12])
    if run_id is not None:
        bits.append(f"run {run_id}")
    if q and tail == "search_code":
        bits.append(q[:80] + ("…" if len(q) > 80 else ""))
    if method and tail == "actions_list":
        bits.append(method)
    return " · ".join(bits[:5])


def _copilot_subline(tool_lower: str, tool_raw: str, args: object, *, workspace: str) -> str:
    ws = str(workspace or "")
    a = args

    if tool_lower in GITHUB_TOOLS:
        return _gh_sub(tool_raw, a)

    if tool_lower == "list_agents":
        if isinstance(a, dict):
            return f"include_completed={a.get('include_completed')}"
        return "list"

    if tool_lower == "apply_patch":
        return _patch_target_path(a)

    if not isinstance(a, dict):
        return ""

    if tool_lower == "report_intent":
        intent = str(a.get("intent") or "").strip()
        if not intent:
            return ""
        line = intent.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "bash":
        cmd = str(a.get("command") or a.get("cmd") or "").strip()
        if not cmd:
            return ""
        line = cmd.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "glob":
        pat = str(a.get("pattern") or "").strip()
        td_raw = str(a.get("path") or "").strip()
        td = display_path(td_raw, workspace=ws) if td_raw else ""
        if pat and td:
            return f"{pat} in {td}"
        if pat:
            return pat
        return td or "."

    if tool_lower == "grep":
        sub = _grep_sub(a, use_glob=True)
        return sub

    if tool_lower == "rg":
        return _grep_sub(a, use_glob=False)

    if tool_lower == "view":
        p_raw = _pick(a, "path", "file_path")
        p = display_path(p_raw, workspace=ws) if p_raw else ""
        if not p:
            return ""
        vr = a.get("view_range")
        suf = ""
        if isinstance(vr, list) and len(vr) >= 2:
            suf = f" ({vr[0]}–{vr[1]})"
        return p + suf

    if tool_lower == "web_fetch":
        return _pick(a, "url", "uri")

    if tool_lower == "web_search":
        return _pick(a, "query", "q", "search_term")

    if tool_lower == "skill":
        return str(a.get("skill") or "").strip() or "(skill)"

    if tool_lower == "create":
        return display_path(_pick(a, "path", "file_path"), workspace=ws)

    if tool_lower == "edit":
        return display_path(_pick(a, "path", "file_path"), workspace=ws)

    if tool_lower == "read_bash":
        sid = str(a.get("shellId") or "").strip() or "(shell)"
        return f"read {sid}"

    if tool_lower == "write_bash":
        sid = str(a.get("shellId") or "").strip() or "(shell)"
        inp = str(a.get("input") or "").strip()
        return f"{sid} «{inp[:40]}»" if inp else sid

    if tool_lower == "stop_bash":
        sid = str(a.get("shellId") or "").strip() or "(shell)"
        return f"stop {sid}"

    if tool_lower == "list_bash":
        return "list"

    if tool_lower == "read_agent":
        aid = str(a.get("agent_id") or "").strip() or "(agent)"
        return f"{aid} wait={a.get('wait')}"

    if tool_lower == "task":
        d = _pick(a, "description", "name", "prompt")
        if not d:
            return ""
        line = d.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "sql":
        desc = str(a.get("description") or "").strip()
        q = str(a.get("query") or "").strip()
        head = (desc + ": " if desc else "") + (q.split("\n", 1)[0][:100] if q else "")
        if len(head) > 120:
            head = head[:117] + "..."
        return head.strip() or "SQL"

    if tool_lower == "ask_user":
        q = str(a.get("question") or "").strip()
        if not q:
            return ""
        line = q.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "store_memory":
        subj = str(a.get("subject") or "").strip()
        fact = str(a.get("fact") or "").strip()
        if subj and fact:
            return f"{subj}: {fact[:80]}" + ("…" if len(fact) > 80 else "")
        if subj:
            return subj
        if fact:
            return fact[:100]
        return ""

    if tool_lower == "fetch_copilot_cli_documentation":
        return "Copilot CLI"

    return ""


def iter_tool_calls(entry: dict) -> list[tuple[str, dict]]:
    """tool.execution_start と assistant.message.toolRequests。"""
    out: list[tuple[str, dict]] = []
    if entry.get("type") == "tool.execution_start":
        data = entry.get("data") or {}
        if isinstance(data, dict):
            name = str(data.get("toolName") or "tool").strip()
            args = data.get("arguments")
            if isinstance(args, dict):
                out.append((name, args))
    if entry.get("type") == "assistant.message":
        data = entry.get("data") or {}
        if isinstance(data, dict):
            for tr in data.get("toolRequests") or []:
                if isinstance(tr, dict):
                    name = str(tr.get("name") or "tool").strip()
                    args = tr.get("arguments")
                    if isinstance(args, dict):
                        out.append((name, args))
    return out


def _sid(p: str, t: str) -> str:
    return f"{p}:{(t or '')[:120]}"


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    raw = str(name or "").strip() or "tool"
    lower = raw.lower()
    a = _coerce_args(arguments)

    if lower in GITHUB_TOOLS:
        main = "MCP"
    else:
        main = MAIN_LABEL.get(lower)
    if main is None:
        return []

    sub = _copilot_subline(lower, raw, a, workspace=str(workspace or "")).strip()
    if not sub:
        return []
    return [runtime_event(main, sub, source_id=_sid(f"tool:{lower[:50]}", sub))]


def parse_jsonl_for_runtime(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    return parse_jsonl_tail_for_runtime(
        filepath,
        limit,
        workspace,
        iter_tool_calls=iter_tool_calls,
        tool_events=runtime_tool_events,
        log_label="Copilot events JSONL",
    )


def sync_copilot_assistant_messages(self, agent: str, native_log_path: str | None = None) -> None:
    try:
        resolved_path = str(native_log_path) if native_log_path else ""
        if not resolved_path:
            cursor = self._copilot_cursors.get(agent)
            if cursor and cursor.path and os.path.exists(cursor.path):
                resolved_path = cursor.path
            else:
                from native_log_sync.core.pane_tmux import pane_field, pane_id_for_agent
                from native_log_sync.copilot.log_location import resolve_path

                pane_id = pane_id_for_agent(self, agent)
                pane_pid = pane_field(self, pane_id, "#{pane_pid}")
                if pane_id and pane_pid:
                    resolved_path = resolve_path(self, agent, pane_id, pane_pid)
                if not resolved_path or not os.path.exists(resolved_path):
                    return

        file_size = os.path.getsize(resolved_path)
        prev_cursor = self._copilot_cursors.get(agent)
        offset = _advance_native_cursor(self._copilot_cursors, agent, resolved_path, file_size)
        if offset is None:
            if _cursor_binding_changed(prev_cursor, self._copilot_cursors.get(agent)):
                self.save_sync_state()
            return

        _assistant_appended = False
        with open(resolved_path, "r", encoding="utf-8") as f:
            f.seek(offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                etype = str(entry.get("type") or "").strip()
                if etype != "assistant.message":
                    continue
                data = entry.get("data") if isinstance(entry, dict) else {}
                if not isinstance(data, dict):
                    data = {}
                content = str(data.get("content") or "").strip()
                if not content:
                    continue
                msg_id = str(data.get("messageId") or entry.get("id") or "").strip()
                if msg_id and msg_id in self._synced_msg_ids:
                    continue
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                jsonl_entry = {
                    "timestamp": timestamp,
                    "session": self.session_name,
                    "sender": agent,
                    "targets": ["user"],
                    "message": f"[From: {agent}]\n{content}",
                    "msg_id": msg_id or uuid.uuid4().hex[:12],
                }
                append_jsonl_entry(self.index_path, jsonl_entry)
                if msg_id:
                    self._synced_msg_ids.add(msg_id)
                _assistant_appended = True

        self._copilot_cursors[agent] = NativeLogCursor(path=resolved_path, offset=file_size)
        self.save_sync_state()
        if _assistant_appended:
            self._agent_last_turn_done_ts[agent] = time.time()
            ev = self._agent_turn_done_events.get(agent)
            if ev is not None:
                ev.set()
    except Exception as exc:
        logging.error("Failed to sync Copilot message for %s: %s", agent, exc, exc_info=True)
