from __future__ import annotations
import fcntl
import logging

import json
import os
import re
import shlex
import subprocess
import time
import uuid
from collections import deque
from datetime import datetime as dt_datetime
from pathlib import Path
import shutil
from urllib.parse import quote

from .agent_registry import AGENTS, ALL_AGENT_NAMES, generate_agent_message_selectors
from .instance_core import agents_from_tmux_env_output
from .instance_core import resolve_target_agents as resolve_target_agent_names
from .jsonl_append import append_jsonl_entry
from .state_core import load_hub_settings as load_shared_hub_settings
from .state_core import load_session_thinking_totals as load_shared_session_thinking_totals



def _agent_base_name(agent: str) -> str:
    return re.sub(r"-\d+$", "", (agent or "").strip().lower())



def _pane_runtime_tag_occurrences(events: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    normalized: list[dict] = []
    for event in events:
        source_id = str((event or {}).get("source_id") or "").strip()
        if not source_id:
            continue
        counts[source_id] = counts.get(source_id, 0) + 1
        normalized.append({
            **event,
            "source_id": f"{source_id}#{counts[source_id]}",
        })
    return normalized


def _pane_runtime_with_occurrence_ids(events: list[dict], *, limit: int) -> list[dict]:
    normalized = _pane_runtime_tag_occurrences(events)
    return normalized[-max(1, int(limit)) :]


def _pane_runtime_gemini_with_occurrence_ids(events: list[dict], *, limit: int) -> list[dict]:
    """Like _pane_runtime_with_occurrence_ids, but keep a ✦ thought visible when possible.

    A long run of tool-only rows after the latest thought would otherwise push every ✦ event
    out of the tail window; ensure the most recent thought is always included in the returned list.
    """
    tagged = _pane_runtime_tag_occurrences(events)
    lim = max(1, int(limit))
    if len(tagged) <= lim:
        return tagged
    
    tail = tagged[-lim:]
    if any("✦" in str((e or {}).get("text") or "") for e in tail):
        return tail
    
    last_thought = None
    for i in range(len(tagged) - 1, -1, -1):
        if "✦" in str((tagged[i] or {}).get("text") or ""):
            last_thought = tagged[i]
            break
    
    if not last_thought:
        return tail
    
    # Return [latest_thought] + the last (lim - 1) items to keep window size consistent
    return [last_thought] + tagged[-(lim - 1) :]


def _get_process_tree(pid: str) -> set[str]:
    """Get all descendant PIDs for a given PID using `ps`."""
    try:
        out = subprocess.run(["ps", "-eo", "pid,ppid"], capture_output=True, text=True, check=True).stdout
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

def _resolve_native_log_file(pane_pid: str, log_pattern: str, base_name: str = "") -> str | None:
    """Find an open file matching log_pattern that belongs to the given pane_pid or its descendants."""
    pids = _get_process_tree(str(pane_pid).strip())
    if not pids:
        return None
    
    # Special handling for Copilot: look for inuse.[PID].lock files
    if base_name == "copilot":
        for pid in pids:
            # Check ~/.copilot/session-state/*/inuse.[PID].lock
            state_dir = Path.home() / ".copilot" / "session-state"
            if state_dir.exists():
                for lock_file in state_dir.glob(f"*/inuse.{pid}.lock"):
                    session_dir = lock_file.parent
                    log_file = session_dir / "events.jsonl"
                    if log_file.exists():
                        return str(log_file)

    try:
        # -a: AND, -d ^txt,cwd,rtd: exclude non-files, -Fn: output filenames
        cmd = ["lsof", "-p", ",".join(pids), "-Fn"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
        for line in out.splitlines():
            if line.startswith("n"):
                path = line[1:]
                if re.search(log_pattern, path):
                    return path
    except Exception:
        pass
    return None

def _parse_native_codex_log(filepath: str, limit: int) -> list[dict] | None:
    """Parse Codex rollout JSONL file."""
    try:
        events = []
        with open(filepath, "r", encoding="utf-8") as f:
            # We don't need to read the whole file if it's huge, but typically rollouts are small enough for tail-like logic.
            # To be safe, we just read lines and keep the last `limit` + recent thoughts.
            lines = f.readlines()
            
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
                
                if ptype == "message" and payload.get("role") == "assistant":
                    content = payload.get("content", [])
                    if content and content[0].get("type") == "output_text":
                        text = content[0].get("text", "").strip()
                        if text:
                            events.append({
                                "kind": "fixed",
                                "text": f"✦ {text}",
                                "source_id": f"thought:codex:✦ {text}"
                            })
                elif ptype == "custom_tool_call":
                    name = payload.get("name", "")
                    inp = payload.get("input", "")
                    if name:
                        events.append({
                            "kind": "fixed",
                            "text": f"Ran {name} {inp}",
                            "source_id": f"tool:codex:Ran {name} {inp}"
                        })
                elif ptype == "function_call":
                    name = payload.get("name", "")
                    args = payload.get("arguments", "")
                    if name:
                        events.append({
                            "kind": "fixed",
                            "text": f"Ran {name} {args}",
                            "source_id": f"tool:codex:Ran {name} {args}"
                        })
        return _pane_runtime_gemini_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native codex log {filepath}: {e}")
        return None

def _copilot_tool_summary(tool_name: str, args: dict) -> str:
    """Pick the most informative one-line summary for a Copilot tool invocation."""
    name = (tool_name or "tool").strip()
    a = args if isinstance(args, dict) else {}
    # Prefer an explicit description (bash, sql)
    desc = str(a.get("description") or "").strip()
    if desc:
        return f"{name} {desc}"
    # Per-tool argument picks
    if name == "bash":
        cmd = str(a.get("command") or "").strip().splitlines()
        return f"bash {cmd[0]}" if cmd else "bash"
    if name in ("view", "create", "edit"):
        path = str(a.get("path") or "").strip()
        return f"{name} {path}" if path else name
    if name in ("grep", "glob"):
        pattern = str(a.get("pattern") or "").strip()
        return f"{name} {pattern}" if pattern else name
    if name == "ask_user":
        q = str(a.get("question") or "").strip()
        return f"ask_user {q}" if q else "ask_user"
    if name == "report_intent":
        intent = str(a.get("intent") or "").strip()
        return intent or "report_intent"
    if name == "web_fetch":
        url = str(a.get("url") or "").strip()
        return f"web_fetch {url}" if url else "web_fetch"
    if name == "task":
        prompt = str(a.get("prompt") or a.get("name") or "").strip().splitlines()
        return f"task {prompt[0]}" if prompt else "task"
    if name == "read_bash":
        shell_id = str(a.get("shellId") or "").strip()
        return f"read_bash {shell_id}" if shell_id else "read_bash"
    # Generic fallback: first truthy argument value
    for v in a.values():
        text = str(v or "").strip().splitlines()
        if text and text[0]:
            return f"{name} {text[0]}"
    return name


def _parse_native_copilot_log(filepath: str, limit: int) -> list[dict] | None:
    """Parse Copilot events.jsonl log."""
    try:
        events = []
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = data.get("type")
            edata = data.get("data", {}) or {}
            if etype == "assistant.message":
                content = str(edata.get("content") or "").strip().splitlines()
                msg_id = str(edata.get("messageId") or "").strip()
                if content and content[0]:
                    events.append({
                        "kind": "fixed",
                        "text": f"● {content[0]}",
                        "source_id": f"msg:copilot:{msg_id}" if msg_id else f"msg:copilot:{content[0]}",
                    })
            elif etype == "tool.execution_start":
                tool_name = str(edata.get("toolName") or "").strip()
                args = edata.get("arguments") or {}
                summary = _copilot_tool_summary(tool_name, args)
                call_id = str(edata.get("toolCallId") or "").strip()
                events.append({
                    "kind": "fixed",
                    "text": f"● {summary}",
                    "source_id": f"tool:copilot:{call_id}" if call_id else f"tool:copilot:{summary}",
                })
        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native copilot log {filepath}: {e}")
        return None

def _parse_native_claude_log(filepath: str, limit: int) -> list[dict] | None:
    """Parse Claude telemetry JSON log."""
    try:
        # Claude telemetry JSON files are a series of JSON objects, one per line.
        events = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                event_data = data.get("event_data", {})
                event_name = event_data.get("event_name", "")
                
                if event_name == "tengu_tool_call":
                    meta_str = event_data.get("additional_metadata", "{}")
                    try:
                        meta = json.loads(meta_str)
                    except:
                        meta = {}
                    tool_name = meta.get("tool_name", "tool")
                    tool_input = meta.get("tool_input", "")
                    events.append({
                        "kind": "fixed",
                        "text": f"Ran {tool_name} {tool_input}",
                        "source_id": f"tool:claude:Ran {tool_name} {tool_input}"
                    })
                # Note: Claude's thoughts are not usually in telemetry, they are in history.jsonl.
                # For pure tool tracking, telemetry works well. For thoughts, we might miss them here.
                # In this fallback, we just return the tool events.
        
        # Tag occurrences
        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native claude log {filepath}: {e}")
        return None

def _parse_native_gemini_log(session_name: str, repo_root: Path | str, agent: str, limit: int) -> list[dict] | None:
    """Parse Gemini wrapper normalized events."""
    try:
        log_dir = Path(repo_root) / "logs" / "multiagent" / "normalized-events" / "gemini-direct"
        if not log_dir.exists():
            return None

        candidates = sorted(log_dir.glob("*.jsonl"), key=os.path.getmtime)
        filepath = None
        for cand in reversed(candidates):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    first_line = f.readline()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("session") == session_name and data.get("sender") == agent:
                            filepath = cand
                            break
            except Exception:
                pass
            
        if not filepath:
            return None
            
        events = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "thought":
                    text = str(data.get("text") or "").strip()
                    events.append({
                        "kind": "fixed",
                        "text": f"✦ {text}",
                        "source_id": f"thought:gemini:✦ {text}"
                    })
                elif data.get("type") == "tool":
                    name = str(data.get("name") or "").strip()
                    args = str(data.get("args") or "").strip()
                    events.append({
                        "kind": "fixed",
                        "text": f"Ran {name} {args}",
                        "source_id": f"tool:gemini:Ran {name} {args}"
                    })
        return _pane_runtime_gemini_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error(f"Failed to parse native gemini log: {e}")
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


def _agent_markdown_selectors(*suffixes: str, prefix: str = "") -> str:
    """Generate .message.{agent} .md-body selectors for the given suffixes."""
    parts = []
    suffix_list = suffixes or ("",)
    for name in ALL_AGENT_NAMES:
        base = f'    {prefix}.message.{name} .md-body'
        for suffix in suffix_list:
            parts.append(f"{base}{suffix}")
    return ",\n".join(parts)

def _bh_agent_detail_selectors(prefix: str = "") -> str:
    """Generate .message.{agent} .md-body {p,li,h1..h4,blockquote} selectors."""
    return _agent_markdown_selectors(
        " p",
        " li",
        " h1",
        " h2",
        " h3",
        " h4",
        " blockquote",
        prefix=prefix,
    )
from .state_core import update_thinking_totals_from_statuses as update_shared_thinking_totals_from_statuses


class ChatRuntime:
    PUBLIC_LIGHT_MESSAGE_CHAR_LIMIT = 1500
    PUBLIC_LIGHT_CODE_THRESHOLD = 800
    PUBLIC_LIGHT_ATTACHMENT_PREVIEW_LIMIT = 2

    def __init__(
        self,
        *,
        index_path: Path | str,
        limit: int,
        filter_agent: str,
        session_name: str,
        follow_mode: bool,
        port: int,
        agent_send_path: Path | str,
        workspace: str,
        log_dir: str,
        targets: list[str],
        tmux_socket: str,
        hub_port: int,
        repo_root: Path | str,
        session_is_active: bool,
    ):
        self.index_path = Path(index_path)
        self.commit_state_path = self.index_path.parent / ".agent-index-commit-state.json"
        self.limit = int(limit)
        self.filter_agent = (filter_agent or "").strip().lower()
        self.session_name = session_name
        self.follow_mode = bool(follow_mode)
        self.port = int(port)
        self.agent_send_path = str(agent_send_path)
        self.workspace = workspace
        self.log_dir = log_dir
        self.targets = list(targets or [])
        self.tmux_socket = tmux_socket
        self.hub_port = int(hub_port)
        self.repo_root = Path(repo_root).resolve()
        self.session_is_active = bool(session_is_active)
        self.server_instance = uuid.uuid4().hex
        self.tmux_prefix = ["tmux"]
        if self.tmux_socket:
            if "/" in self.tmux_socket:
                self.tmux_prefix.extend(["-S", self.tmux_socket])
            else:
                self.tmux_prefix.extend(["-L", self.tmux_socket])
        self._caffeinate_proc = None
        self._pane_snapshots = {}
        self._pane_last_change = {}
        self._pane_runtime_matches = {}
        self._pane_runtime_state = {}
        self._pane_native_log_paths = {}
        self._pane_runtime_event_seq = 0
        self.running_grace_seconds = 2.0
        self._caffeinate_args = ["caffeinate", "-s"]
        try:
            settings = self.load_chat_settings()
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            settings = {}
        saved_limit = settings.get("message_limit")
        if saved_limit is not None and int(saved_limit) > 0:
            self.limit = int(saved_limit)
        if bool(settings.get("chat_awake", False)):
            self.ensure_caffeinate_active()

    def load_chat_settings(self) -> dict:
        cap = self.limit if self.limit > 0 else 2000
        return load_shared_hub_settings(self.repo_root, message_limit_cap=cap)

    @staticmethod
    def _font_family_stack(selection: str, role: str) -> str:
        value = str(selection or "").strip()
        sans_stack = '"anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Meiryo", sans-serif'
        serif_stack = '"anthropicSerif", "anthropicSerif Fallback", "Anthropic Serif", "Hiragino Mincho ProN", "Yu Mincho", "YuMincho", "Noto Serif JP", Georgia, "Times New Roman", Times, serif'
        default_stack = sans_stack if role == "user" else serif_stack
        if value == "preset-gothic":
            return sans_stack
        if value == "preset-mincho":
            return serif_stack
        if value.startswith("system:"):
            family = value.split(":", 1)[1].strip()
            if family:
                return f'"{family}", {default_stack}'
        return default_stack

    @classmethod
    def chat_font_settings_inline_style(cls, settings: dict) -> str:
        user_family = cls._font_family_stack(settings.get("user_message_font", "preset-gothic"), "user")
        agent_family = cls._font_family_stack(settings.get("agent_message_font", "preset-mincho"), "agent")
        agent_font_mode = str(settings.get("agent_font_mode", "serif") or "serif").strip().lower()
        if agent_font_mode == "gothic":
            thinking_body_variation = '"wght" 360, "opsz" 16'
            thinking_keyword_variation = '"wght" 530, "opsz" 16'
            thinking_letter_spacing = "-0.01em"
        else:
            thinking_body_variation = '"wght" 360'
            thinking_keyword_variation = '"wght" 530'
            thinking_letter_spacing = "0"
        theme = str(settings.get("theme", "black-hole") or "black-hole").strip().lower()
        try:
            message_text_size = max(11, min(18, int(settings.get("message_text_size", 13))))
        except Exception:
            message_text_size = 13
        try:
            message_max_width = max(400, min(2000, int(settings.get("message_max_width", 900))))
        except Exception:
            message_max_width = 900
        try:
            user_opacity = max(0.2, min(1.0, float(settings.get("user_message_opacity_blackhole", 1.0))))
        except Exception:
            user_opacity = 1.0
        try:
            agent_opacity = max(0.2, min(1.0, float(settings.get("agent_message_opacity_blackhole", 1.0))))
        except Exception:
            agent_opacity = 1.0
        if theme == "black-hole":
            user_color = f"rgba(252, 252, 252, {user_opacity:.2f})"
            agent_color = f"rgba(252, 252, 252, {agent_opacity:.2f})"
        else:
            # Light themes should inherit dark foreground tones.
            user_color = f"rgba(26, 30, 36, {user_opacity:.2f})"
            agent_color = f"rgba(26, 30, 36, {agent_opacity:.2f})"
        
        bold_style = ""
        if settings.get("bold_mode"):
            bold_style = f"""
    .message.user .md-body,
    .message.user .md-body p,
    .message.user .md-body li,
    .message.user .md-body li p,
    .message.user .md-body blockquote,
    .message.user .md-body blockquote p,
    {_agent_markdown_selectors("", " p", " li", " li p", " blockquote", " blockquote p")} {{
      font-weight: 620 !important;
      font-variation-settings: normal !important;
      font-synthesis: weight !important;
      font-synthesis-weight: auto !important;
      -webkit-font-smoothing: antialiased;
    }}
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4,
    {_agent_markdown_selectors(" h1", " h2", " h3", " h4")} {{
      font-weight: 700 !important;
      font-variation-settings: normal !important;
      font-synthesis: weight !important;
      font-synthesis-weight: auto !important;
      -webkit-font-smoothing: antialiased;
    }}
    .message-thinking-container,
    .message-thinking-container .message-thinking-label,
    .message-thinking-container .message-thinking-label-primary,
    .message-thinking-container .message-thinking-runtime-line,
    .message-thinking-container .message-thinking-label-live,
    .message-thinking-container .message-thinking-label-preview,
    .camera-mode-thinking {{
      font-weight: 620 !important;
      font-variation-settings: normal !important;
      font-synthesis: weight !important;
      font-synthesis-weight: auto !important;
      -webkit-font-smoothing: antialiased;
    }}
    .message-thinking-runtime-keyword {{
      font-weight: 700 !important;
      font-variation-settings: normal !important;
      font-synthesis: weight !important;
      font-synthesis-weight: auto !important;
      -webkit-font-smoothing: antialiased;
    }}
    """
        return f"""
    :root {{
      --message-text-size: {message_text_size}px;
      --message-text-line-height: {message_text_size + 9}px;
      --message-max-width: {message_max_width}px;
      --user-message-blackhole-color: {user_color};
      --agent-message-blackhole-color: {agent_color};
      --agent-thinking-font-family: {agent_family};
      --agent-thinking-body-variation: {thinking_body_variation};
      --agent-thinking-keyword-variation: {thinking_keyword_variation};
      --agent-thinking-letter-spacing: {thinking_letter_spacing};
    }}
    .shell {{
      max-width: var(--message-max-width) !important;
    }}
    .composer {{
      width: min(var(--message-max-width), calc(100vw - 24px)) !important;
      max-width: var(--message-max-width) !important;
    }}
    .composer-main-shell {{
      max-width: var(--message-max-width) !important;
    }}
    .statusline {{
      width: min(var(--message-max-width), calc(100vw - 16px)) !important;
    }}
    .brief-editor-panel {{
      width: min(92vw, var(--message-max-width)) !important;
      max-width: var(--message-max-width) !important;
    }}
    .message.user .md-body {{
      font-family: {user_family} !important;
      color: var(--user-message-blackhole-color) !important;
    }}
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4,
    .message.user .md-body blockquote {{
      color: var(--user-message-blackhole-color) !important;
    }}
    {generate_agent_message_selectors(" .md-body")} {{
      font-family: {agent_family} !important;
      color: var(--agent-message-blackhole-color) !important;
    }}
    {_bh_agent_detail_selectors(prefix="")} {{
      color: var(--agent-message-blackhole-color) !important;
    }}
    {bold_style}
    """


    def load_thinking_totals(self) -> dict[str, int]:
        return load_shared_session_thinking_totals(self.repo_root, self.session_name, self.workspace)

    def append_system_entry(self, message: str, *, agent: str = "", **extra) -> dict:
        entry = {
            "timestamp": dt_datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session": self.session_name,
            "sender": "system",
            "targets": [],
            "message": message,
            "msg_id": uuid.uuid4().hex[:12],
        }
        if agent:
            entry["agent"] = agent
        entry.update(extra)
        append_jsonl_entry(self.index_path, entry)
        return entry

    def _read_commit_state_locked(self, handle) -> dict:
        handle.seek(0)
        raw = handle.read().strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return {}

    @staticmethod
    def _commit_state_payload(commit: dict) -> dict:
        return {
            "last_commit_hash": commit["hash"],
            "last_commit_short": commit["short"],
            "last_commit_subject": commit["subject"],
        }

    def _write_commit_state_locked(self, handle, commit: dict) -> None:
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(self._commit_state_payload(commit), ensure_ascii=False))
        handle.flush()

    def has_logged_commit_entry(self, commit_hash: str, *, recent_limit: int = 256) -> bool:
        commit_hash = (commit_hash or "").strip()
        if not commit_hash or not self.index_path.exists():
            return False
        try:
            recent_lines: deque[str] = deque(maxlen=max(32, int(recent_limit)))
            with self.index_path.open("r", encoding="utf-8") as f:
                for line in f:
                    recent_lines.append(line)
            for line in reversed(recent_lines):
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if entry.get("kind") != "git-commit":
                    continue
                if (entry.get("commit_hash") or "").strip() == commit_hash:
                    return True
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
        return False

    def start_direct_provider_run(self, provider: str, prompt: str, reply_to: str = "", provider_model: str = "") -> tuple[int, dict]:
        provider_name = (provider or "").strip().lower()
        prompt = (prompt or "").strip()
        reply_to = (reply_to or "").strip()
        provider_model = (provider_model or "").strip()
        if not self.session_is_active:
            return 409, {"ok": False, "error": "archived session is read-only"}
        supported_providers = {"gemini", "ollama"}
        if provider_name not in supported_providers:
            return 400, {"ok": False, "error": f"unsupported direct provider: {provider_name}"}
        if not prompt:
            return 400, {"ok": False, "error": "message is required"}
        bin_dir = Path(self.agent_send_path).parent
        runner_map = {
            "gemini": "multiagent-gemini-direct-run",
            "ollama": "multiagent-ollama-direct-run",
        }
        runner = bin_dir / runner_map[provider_name]
        if not runner.is_file():
            return 500, {"ok": False, "error": f"{runner_map[provider_name]} not found"}
        env = os.environ.copy()
        env["MULTIAGENT_SESSION"] = self.session_name
        env["MULTIAGENT_WORKSPACE"] = self.workspace
        env["MULTIAGENT_LOG_DIR"] = self.log_dir
        env["MULTIAGENT_BIN_DIR"] = str(bin_dir)
        env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
        env.pop("TMUX", None)
        env.pop("TMUX_PANE", None)
        command = [
            str(runner),
            "--session",
            self.session_name,
            "--workspace",
            self.workspace,
            "--sender",
            provider_name,
            "--target",
            "user",
            "--prompt-sender",
            "user",
            "--prompt-target",
            provider_name,
        ]
        if self.log_dir:
            command.extend(["--log-dir", self.log_dir])
        if reply_to:
            command.extend(["--reply-to", reply_to])
        if provider_model:
            command.extend(["--model", provider_model])
        try:
            proc = subprocess.Popen(
                command,
                cwd=self.workspace or None,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
                close_fds=True,
            )
            if proc.stdin is not None:
                proc.stdin.write(prompt)
                if not prompt.endswith("\n"):
                    proc.stdin.write("\n")
                proc.stdin.close()
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return 500, {"ok": False, "error": str(exc)}
        return 200, {"ok": True, "mode": "provider-direct", "provider": provider_name}

    def read_commit_state(self) -> dict:
        if not self.commit_state_path.exists():
            return {}
        try:
            with self.commit_state_path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                try:
                    return self._read_commit_state_locked(handle)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return {}

    def write_commit_state(self, commit: dict) -> None:
        try:
            self.commit_state_path.parent.mkdir(parents=True, exist_ok=True)
            with self.commit_state_path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    self._write_commit_state_locked(handle, commit)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            pass

    def _record_git_commit_locked(self, handle, commit: dict, *, agent: str = "") -> bool:
        if self.has_logged_commit_entry(commit["hash"]):
            self._write_commit_state_locked(handle, commit)
            return False
        self.append_system_entry(
            f"Commit: {commit['short']} {commit['subject']}",
            kind="git-commit",
            commit_hash=commit["hash"],
            commit_short=commit["short"],
            agent=agent,
        )
        self._write_commit_state_locked(handle, commit)
        return True

    def record_git_commit(self, *, commit_hash: str, commit_short: str, subject: str, agent: str = "") -> bool:
        commit = {
            "hash": (commit_hash or "").strip(),
            "short": (commit_short or "").strip(),
            "subject": str(subject or "").strip(),
        }
        if not commit["hash"] or not commit["short"] or not commit["subject"]:
            return False
        try:
            self.commit_state_path.parent.mkdir(parents=True, exist_ok=True)
            with self.commit_state_path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    return self._record_git_commit_locked(handle, commit, agent=agent)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return False

    def current_git_commit(self) -> dict | None:
        try:
            result = subprocess.run(
                ["git", "-C", self.workspace, "log", "-1", "--format=%H%x1f%h%x1f%s"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return None
        if result.returncode != 0:
            return None
        line = result.stdout.strip()
        if not line:
            return None
        parts = line.split("\x1f", 2)
        if len(parts) != 3:
            return None
        return {"hash": parts[0], "short": parts[1], "subject": parts[2]}

    def git_commits_since(self, base_hash: str) -> list[dict] | None:
        try:
            result = subprocess.run(
                ["git", "-C", self.workspace, "log", "--reverse", "--format=%H%x1f%h%x1f%s", f"{base_hash}..HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return None
        if result.returncode != 0:
            return None
        commits = []
        for line in result.stdout.splitlines():
            parts = line.split("\x1f", 2)
            if len(parts) != 3:
                continue
            commits.append({"hash": parts[0], "short": parts[1], "subject": parts[2]})
        return commits

    def ensure_commit_announcements(self) -> None:
        current = self.current_git_commit()
        if not current:
            return
        try:
            self.commit_state_path.parent.mkdir(parents=True, exist_ok=True)
            with self.commit_state_path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    state = self._read_commit_state_locked(handle)
                    last_hash = state.get("last_commit_hash", "")
                    if not last_hash:
                        self._write_commit_state_locked(handle, current)
                        return
                    if last_hash == current["hash"]:
                        return
                    commits = self.git_commits_since(last_hash)
                    if commits is None:
                        commits = [current]
                    if not commits:
                        self._write_commit_state_locked(handle, current)
                        return
                    for commit in commits:
                        self._record_git_commit_locked(handle, commit)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)

    def matches(self, entry: dict) -> bool:
        if not self.filter_agent:
            return True
        if entry.get("sender", "").lower() == self.filter_agent:
            return True
        return any(t.lower() == self.filter_agent for t in entry.get("targets", []))

    @staticmethod
    def attachment_paths(message: str) -> list[str]:
        text = str(message or "")
        return [match.strip() for match in re.findall(r"\[Attached:\s*([^\]]+)\]", text)]

    def _matched_entries(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        entries = []
        with self.index_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if self.matches(entry):
                    entries.append(entry)
        return entries

    def _entry_window(
        self,
        *,
        limit_override: int | None = None,
        before_msg_id: str = "",
        around_msg_id: str = "",
    ) -> tuple[list[dict], bool]:
        entries = self._matched_entries()
        target_around = around_msg_id.strip()
        l = limit_override if limit_override is not None else self.limit
        if target_around:
            idx = next((i for i, entry in enumerate(entries) if str(entry.get("msg_id") or "") == target_around), -1)
            if idx >= 0:
                if l and l > 0:
                    half = max(0, l // 2)
                    start = max(0, idx - half)
                    end = min(len(entries), start + l)
                    start = max(0, end - l)
                    has_older = start > 0
                    return entries[start:end], has_older
                return entries, idx > 0
        if before_msg_id:
            target = before_msg_id.strip()
            idx = next((i for i, entry in enumerate(entries) if str(entry.get("msg_id") or "") == target), -1)
            if idx < 0:
                return [], False
            entries = entries[:idx]
        has_older = False
        if l and l > 0:
            has_older = len(entries) > l
            return entries[-l:], has_older
        return entries, False

    def _light_entry(self, entry: dict) -> dict:
        summary = dict(entry)
        message = str(summary.get("message") or "")
        attached_paths = self.attachment_paths(message)
        if attached_paths:
            summary["attached_paths"] = attached_paths
        body_only = re.sub(r"(?:\n)?\[Attached:\s*[^\]]+\]", "", message).strip()
        heavy_code = "```" in body_only and len(body_only) > self.PUBLIC_LIGHT_CODE_THRESHOLD
        truncated = len(body_only) > self.PUBLIC_LIGHT_MESSAGE_CHAR_LIMIT
        if not truncated and not heavy_code:
            return summary
        preview = body_only[:self.PUBLIC_LIGHT_MESSAGE_CHAR_LIMIT].rstrip()
        notes = ["[Public preview truncated. Load full message.]"]
        if attached_paths:
            preview_paths = attached_paths[:self.PUBLIC_LIGHT_ATTACHMENT_PREVIEW_LIMIT]
            notes.extend([f"[Attached: {path}]" for path in preview_paths])
            remaining = len(attached_paths) - len(preview_paths)
            if remaining > 0:
                notes.append(f"(+{remaining} more attachments)")
        summary["message"] = (preview + ("\n\n" if preview else "") + "\n".join(notes)).strip()
        summary["deferred_body"] = True
        summary["message_length"] = len(message)
        return summary

    def read_entries(
        self,
        limit_override: int | None = None,
        before_msg_id: str = "",
        around_msg_id: str = "",
        light_mode: bool = False,
    ) -> list[dict]:
        entries, _has_older = self._entry_window(
            limit_override=limit_override,
            before_msg_id=before_msg_id,
            around_msg_id=around_msg_id,
        )
        if light_mode:
            return [self._light_entry(entry) for entry in entries]
        return entries

    def entry_by_id(self, msg_id: str, *, light_mode: bool = False):
        target = (msg_id or "").strip()
        if not target:
            return None
        for entry in reversed(self._matched_entries()):
            if str(entry.get("msg_id") or "") != target:
                continue
            return self._light_entry(entry) if light_mode else entry
        return None

    def normalized_events_for_msg(self, msg_id: str) -> dict | None:
        entry = self.entry_by_id(msg_id, light_mode=False)
        if entry is None:
            return None
        rel = str(entry.get("normalized_event_path") or "").strip()
        if not rel:
            return {"entry": entry, "events": [], "path": "", "missing": True}
        base = self.index_path.parent.resolve()
        path = (base / rel).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            return {"entry": entry, "events": [], "path": rel, "missing": True}
        if not path.exists():
            return {"entry": entry, "events": [], "path": rel, "missing": True}
        events: list[dict] = []
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f):
                text = line.strip()
                if not text:
                    continue
                try:
                    events.append(json.loads(text))
                except json.JSONDecodeError:
                    events.append({"event": "raw.line", "seq": idx, "text": text})
        return {"entry": entry, "events": events, "path": rel, "missing": False}

    def provider_runtime_state(self) -> dict:
        path = self.index_path.parent / ".provider-runtime.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def session_metadata(self) -> dict:
        session_slug = quote(self.session_name, safe="")
        return {
            "server_instance": self.server_instance,
            "session": self.session_name,
            "active": self.session_is_active,
            "source": str(self.index_path),
            "workspace": self.workspace,
            "log_dir": self.log_dir,
            "port": self.port,
            "hub_port": self.hub_port,
            "session_path": f"/session/{session_slug}/",
            "follow_path": f"/session/{session_slug}/?follow=1",
        }

    def payload(
        self,
        limit_override: int | None = None,
        before_msg_id: str = "",
        around_msg_id: str = "",
        light_mode: bool = False,
    ) -> bytes:
        self.ensure_commit_announcements()
        meta = self.session_metadata()
        entries, has_older = self._entry_window(
            limit_override=limit_override,
            before_msg_id=before_msg_id,
            around_msg_id=around_msg_id,
        )
        if light_mode:
            entries = [self._light_entry(entry) for entry in entries]
        return json.dumps(
            {
                **meta,
                "filter": self.filter_agent or "all",
                "follow": self.follow_mode,
                "targets": self.active_agents(),
                "has_older": has_older,
                "light_mode": bool(light_mode),
                "entries": entries,
            },
            ensure_ascii=True,
        ).encode("utf-8")

    def caffeinate_status(self) -> dict:
        if self._caffeinate_proc is not None and self._caffeinate_proc.poll() is None:
            return {"active": True}
        self._caffeinate_proc = None
        try:
            result = subprocess.run(["pgrep", "-x", "caffeinate"], capture_output=True)
            if result.returncode == 0:
                return {"active": True}
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            pass
        return {"active": False}

    def caffeinate_toggle(self) -> dict:
        if self.caffeinate_status()["active"]:
            if self._caffeinate_proc is not None:
                self._caffeinate_proc.terminate()
                self._caffeinate_proc = None
            else:
                subprocess.run(["killall", "caffeinate"], capture_output=True, check=False)
            return {"active": False}
        self.ensure_caffeinate_active()
        return {"active": True}

    def ensure_caffeinate_active(self) -> None:
        if self.caffeinate_status()["active"]:
            return
        self._caffeinate_proc = subprocess.Popen(self._caffeinate_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def save_logs(self, *, reason: str = "autosave"):
        """Run multiagent save to capture panes to workspace/central logs (overwrites)."""
        reason = (reason or "autosave").strip()[:64] or "autosave"
        if not self.session_is_active:
            return 409, {"ok": False, "error": "session inactive", "reason": reason}
        bin_dir = Path(self.agent_send_path).parent.resolve()
        multiagent = bin_dir / "multiagent"
        if not multiagent.is_file():
            return 500, {"ok": False, "error": "multiagent not found", "reason": reason}
        env = os.environ.copy()
        env["MULTIAGENT_SESSION"] = self.session_name
        env["MULTIAGENT_WORKSPACE"] = self.workspace
        env["MULTIAGENT_BIN_DIR"] = str(bin_dir)
        if self.tmux_socket:
            env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
        if self.log_dir:
            env["MULTIAGENT_LOG_DIR"] = self.log_dir
        try:
            proc = subprocess.run(
                [str(multiagent), "save", "--session", self.session_name],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
                cwd=self.workspace or None,
                check=False,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return 500, {"ok": False, "error": str(exc), "reason": reason}
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            return 500, {"ok": False, "error": err, "reason": reason}
        return 200, {"ok": True, "reason": reason}

    def auto_mode_status(self) -> dict:
        try:
            result = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name, "MULTIAGENT_AUTO_MODE"],
                capture_output=True,
                text=True,
                check=False,
            )
            active = result.stdout.strip() == "MULTIAGENT_AUTO_MODE=1"
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            active = False
        approval_file = f"/tmp/multiagent_auto_approved_{self.session_name}"
        try:
            last_approval = os.path.getmtime(approval_file)
            last_approval_agent = Path(approval_file).read_text().strip().lower()
        except OSError:
            last_approval = 0
            last_approval_agent = ""
        return {"active": active, "last_approval": last_approval, "last_approval_agent": last_approval_agent}

    def active_agents(self) -> list[str]:
        """Return the list of agent instance names from MULTIAGENT_AGENTS."""
        try:
            r = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name, "MULTIAGENT_AGENTS"],
                capture_output=True, text=True, timeout=2, check=False,
            )
            line = r.stdout.strip()
            if r.returncode == 0 and "=" in line:
                return [a for a in line.split("=", 1)[1].split(",") if a]
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            pass
        pane_agents = self._agents_from_pane_env()
        if pane_agents:
            return pane_agents
        return list(self.targets) if self.targets else []

    def _agents_from_pane_env(self) -> list[str]:
        """Recover instance names from MULTIAGENT_PANE_* while MULTIAGENT_AGENTS is still settling."""
        try:
            r = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return []
        if r.returncode != 0:
            return []
        return agents_from_tmux_env_output(r.stdout)

    def resolve_target_agents(self, target: str) -> list[str]:
        return resolve_target_agent_names(target, self.active_agents())

    def pane_id_for_agent(self, agent_name: str) -> str:
        pane_var = f"MULTIAGENT_PANE_{agent_name.upper().replace('-', '_')}"
        res = subprocess.run(
            [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip().split("=", 1)[-1] if "=" in res.stdout else ""

    def agent_launch_cmd(self, agent_name: str) -> str:
        bin_dir = Path(self.agent_send_path).parent
        agent_exec_path = Path(self.resolve_agent_executable(agent_name))
        path_prefix = ":".join(
            [
                shlex.quote(str(bin_dir)),
                shlex.quote(str(agent_exec_path.parent)),
            ]
        )
        env_parts = [
            f"PATH={path_prefix}:$PATH",
            f"MULTIAGENT_SESSION={shlex.quote(self.session_name)}",
            f"MULTIAGENT_BIN_DIR={shlex.quote(str(bin_dir))}",
            f"MULTIAGENT_WORKSPACE={shlex.quote(self.workspace)}",
            f"MULTIAGENT_TMUX_SOCKET={shlex.quote(self.tmux_socket)}",
            f"MULTIAGENT_AGENT_NAME={shlex.quote(agent_name)}",
        ]
        env_exports = "export " + " ".join(env_parts)
        agent_exec = shlex.quote(str(agent_exec_path))
        base = agent_name.split("-")[0] if "-" in agent_name else agent_name
        adef = AGENTS.get(base)
        parts = [env_exports]
        if adef and adef.launch_env:
            parts.append(f"export {adef.launch_env}")
        launch_extra = adef.launch_extra if adef else ""
        launch_flags = adef.launch_flags if adef else ""
        extra = f" {launch_extra}" if launch_extra else ""
        flags = f" {launch_flags}" if launch_flags else ""
        parts.append(f"exec{extra} {agent_exec}{flags}")
        return "; ".join(parts)

    def agent_resume_cmd(self, agent_name: str) -> str:
        bin_dir = Path(self.agent_send_path).parent
        agent_exec_path = Path(self.resolve_agent_executable(agent_name))
        path_prefix = ":".join(
            [
                shlex.quote(str(bin_dir)),
                shlex.quote(str(agent_exec_path.parent)),
            ]
        )
        env_parts = [
            f"PATH={path_prefix}:$PATH",
            f"MULTIAGENT_SESSION={shlex.quote(self.session_name)}",
            f"MULTIAGENT_BIN_DIR={shlex.quote(str(bin_dir))}",
            f"MULTIAGENT_WORKSPACE={shlex.quote(self.workspace)}",
            f"MULTIAGENT_TMUX_SOCKET={shlex.quote(self.tmux_socket)}",
            f"MULTIAGENT_AGENT_NAME={shlex.quote(agent_name)}",
        ]
        env_exports = "export " + " ".join(env_parts)
        agent_exec = shlex.quote(str(agent_exec_path))
        base = agent_name.split("-")[0] if "-" in agent_name else agent_name
        adef = AGENTS.get(base)
        if not adef or not adef.resume_flag:
            return self.agent_launch_cmd(agent_name)
        parts = [env_exports]
        if adef.launch_env:
            parts.append(f"export {adef.launch_env}")
        launch_extra = adef.launch_extra if adef.launch_extra else ""
        resume_extra = adef.resume_extra_flags if adef.resume_extra_flags else ""
        extra = f" {launch_extra}" if launch_extra else ""
        flags = f" {adef.resume_flag}"
        if resume_extra:
            flags += f" {resume_extra}"
        parts.append(f"exec{extra} {agent_exec}{flags}")
        return "; ".join(parts)

    @staticmethod
    def resolve_agent_executable(agent_name: str) -> str:
        base = agent_name.split("-")[0] if "-" in agent_name else agent_name
        adef = AGENTS.get(base)
        exe_name = adef.exe if adef else agent_name
        found = shutil.which(exe_name)
        if found:
            return found
        if base == "cursor":
            found = shutil.which("cursor-agent")
            if found:
                return found
        home = Path.home()
        # Explicit fallback paths from registry
        if adef:
            for p in adef.fallback_paths:
                candidate = Path(p).expanduser()
                if candidate.is_file():
                    return str(candidate)
        # NVM fallback for npm-installed agents
        if adef and adef.fallback_nvm:
            nvm_bin = Path(os.environ.get("NVM_BIN", "")).expanduser()
            nvm_candidates: list[Path] = []
            if nvm_bin.is_dir():
                nvm_candidates.append(nvm_bin / exe_name)
            nvm_candidates.extend(
                sorted(
                    (home / ".nvm" / "versions" / "node").glob(f"*/bin/{exe_name}"),
                    reverse=True,
                )
            )
            for candidate in nvm_candidates:
                if candidate.is_file():
                    return str(candidate)
        return exe_name

    def restart_agent_pane(self, agent_name: str) -> tuple[bool, str]:
        pane_id = self.pane_id_for_agent(agent_name)
        if not pane_id:
            return False, f"pane not found for {agent_name}"
        shell = os.environ.get("SHELL") or "/bin/zsh"
        respawn_res = subprocess.run(
            [
                *self.tmux_prefix,
                "respawn-pane",
                "-k",
                "-t",
                pane_id,
                "-c",
                self.workspace,
                shell,
                "-lc",
                self.agent_launch_cmd(agent_name),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if respawn_res.returncode != 0:
            detail = (respawn_res.stderr or respawn_res.stdout or "").strip() or f"failed to restart {agent_name}"
            return False, detail
        subprocess.run([*self.tmux_prefix, "select-pane", "-t", pane_id, "-T", agent_name], capture_output=True, check=False)
        return True, pane_id

    def resume_agent_pane(self, agent_name: str) -> tuple[bool, str]:
        pane_id = self.pane_id_for_agent(agent_name)
        if not pane_id:
            return False, f"pane not found for {agent_name}"
        shell = os.environ.get("SHELL") or "/bin/zsh"
        respawn_res = subprocess.run(
            [
                *self.tmux_prefix,
                "respawn-pane",
                "-k",
                "-t",
                pane_id,
                "-c",
                self.workspace,
                shell,
                "-lc",
                self.agent_resume_cmd(agent_name),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if respawn_res.returncode != 0:
            detail = (respawn_res.stderr or respawn_res.stdout or "").strip() or f"failed to resume {agent_name}"
            return False, detail
        subprocess.run([*self.tmux_prefix, "select-pane", "-t", pane_id, "-T", agent_name], capture_output=True, check=False)
        return True, pane_id

    def send_message(
        self,
        target: str,
        message: str,
        reply_to: str = "",
        silent: bool = False,
        raw: bool = False,
        provider_direct: str = "",
        provider_model: str = "",
    ) -> tuple[int, dict]:
        target = (target or "").strip()
        message = (message or "").strip()
        reply_to = (reply_to or "").strip()
        provider_direct = (provider_direct or "").strip().lower()
        provider_model = (provider_model or "").strip()
        if not message:
            return 400, {"ok": False, "error": "message is required"}
        if provider_direct:
            return self.start_direct_provider_run(provider_direct, message, reply_to, provider_model=provider_model)
        if target:
            target = ",".join(self.resolve_target_agents(target))
        env = os.environ.copy()
        env["MULTIAGENT_SESSION"] = self.session_name
        env["MULTIAGENT_WORKSPACE"] = self.workspace
        env["MULTIAGENT_LOG_DIR"] = self.log_dir
        env["MULTIAGENT_BIN_DIR"] = str(Path(self.agent_send_path).parent)
        env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
        env.pop("TMUX", None)
        env.pop("TMUX_PANE", None)
        env["MULTIAGENT_AGENT_NAME"] = "user"
        bin_dir = Path(self.agent_send_path).parent
        pane_direct = self._parse_pane_direct_command(message)
        if message in {"brief", "save", "interrupt", "ctrlc", "enter", "restart", "resume"} or pane_direct:
            if message in {"interrupt", "ctrlc", "enter", "restart", "resume"} or pane_direct:
                if not target:
                    return 400, {"ok": False, "error": "target is required"}
                try:
                    for agent in [item.strip() for item in target.split(",") if item.strip()]:
                        if message == "restart":
                            ok, detail = self.restart_agent_pane(agent)
                            if not ok:
                                return 400, {"ok": False, "error": detail}
                            continue
                        if message == "resume":
                            ok, detail = self.resume_agent_pane(agent)
                            if not ok:
                                return 400, {"ok": False, "error": detail}
                            continue
                        pane_id = self.pane_id_for_agent(agent)
                        if not pane_id:
                            return 400, {"ok": False, "error": f"pane not found for {agent}"}
                        if pane_direct:
                            if pane_direct["name"] == "model":
                                subprocess.run(
                                    [*self.tmux_prefix, "send-keys", "-t", pane_id, "/", "m", "o", "d", "e", "l"],
                                    capture_output=True,
                                    check=False,
                                )
                                time.sleep(0.15)
                                subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, "Enter"], capture_output=True, check=False)
                            else:
                                tmux_key = {"up": "Up", "down": "Down"}[pane_direct["name"]]
                                for _ in range(pane_direct["repeat"]):
                                    subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, tmux_key], capture_output=True, check=False)
                            continue
                        tmux_key = {"interrupt": "Escape", "ctrlc": "C-c", "enter": "Enter"}[message]
                        subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, tmux_key], capture_output=True, check=False)
                except Exception as exc:
                    logging.error(f"Unexpected error: {exc}", exc_info=True)
                    return 500, {"ok": False, "error": str(exc)}
                return 200, {"ok": True, "mode": pane_direct["name"] if pane_direct else message}
            command = [str(bin_dir / "multiagent"), message, "--session", self.session_name]
            if message == "brief" and target:
                command.extend(["--agent", target])
            try:
                if message == "brief":
                    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                    return 200, {"ok": True, "mode": message}
                result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                return 500, {"ok": False, "error": str(exc)}
            if result.returncode != 0:
                return 400, {"ok": False, "error": (result.stderr or result.stdout or f"{message} failed").strip()}
            return 200, {"ok": True, "mode": message}
        if not target:
            return 400, {"ok": False, "error": "target is required"}
        if silent or raw:
            try:
                targets = [item.strip() for item in target.split(",") if item.strip()]
                if not targets:
                    return 400, {"ok": False, "error": "target is required"}
                for idx, agent in enumerate(targets):
                    pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
                    res = subprocess.run(
                        [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    pane_id = res.stdout.strip().split("=", 1)[-1] if "=" in res.stdout else ""
                    if not pane_id:
                        return 400, {"ok": False, "error": f"pane not found for {agent}"}
                    buf_name = f"direct_{agent}_{os.getpid()}_{idx}"
                    subprocess.run(
                        [*self.tmux_prefix, "load-buffer", "-b", buf_name, "-"],
                        input=message + "\n",
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    subprocess.run([*self.tmux_prefix, "paste-buffer", "-b", buf_name, "-d", "-t", pane_id], capture_output=True, check=False)
                    time.sleep(0.3)
                    subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"], capture_output=True, check=False)
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                return 500, {"ok": False, "error": str(exc)}
            return 200, {"ok": True, "raw": bool(raw)}
        try:
            cmd = [self.agent_send_path]
            if reply_to:
                cmd.extend(["--reply", reply_to])
            cmd.append(target)
            result = subprocess.run(cmd, input=message, capture_output=True, text=True, env=env, check=False)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return 500, {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return 400, {"ok": False, "error": (result.stderr or result.stdout or "agent-send failed").strip()}
        return 200, {"ok": True}

    @staticmethod
    def _parse_pane_direct_command(message: str) -> dict | None:
        normalized = (message or "").strip().lower()
        if normalized == "model":
            return {"name": "model", "repeat": 1}
        match = re.fullmatch(r"(up|down)(?:\s+(\d+))?", normalized)
        if not match:
            return None
        repeat = max(1, min(int(match.group(2) or "1"), 100))
        return {"name": match.group(1), "repeat": repeat}

    def agent_statuses(self) -> dict[str, str]:
        result = {}
        for agent in self.active_agents():
            pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
            try:
                r = subprocess.run(
                    [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                line = r.stdout.strip()
                if r.returncode != 0 or "=" not in line:
                    result[agent] = "offline"
                    self._pane_runtime_matches.pop(agent, None)
                    self._pane_runtime_state.pop(agent, None)
                    continue
                pane_id = line.split("=", 1)[1]
                dead = subprocess.run(
                    [*self.tmux_prefix, "display-message", "-p", "-t", pane_id, "#{pane_dead}"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                ).stdout.strip()
                if dead == "1":
                    result[agent] = "dead"
                    self._pane_snapshots.pop(pane_id, None)
                    self._pane_last_change.pop(pane_id, None)
                    self._pane_runtime_matches.pop(agent, None)
                    self._pane_runtime_state.pop(agent, None)
                    self._pane_native_log_paths.pop(pane_id, None)
                    continue

                base_name = _agent_base_name(agent)
                runtime_events = None

                if base_name in ("codex", "claude", "gemini", "copilot"):
                    native_log_path = self._pane_native_log_paths.get(pane_id)
                    if not native_log_path or not os.path.exists(native_log_path):
                        pane_pid = subprocess.run(
                            [*self.tmux_prefix, "display-message", "-p", "-t", pane_id, "#{pane_pid}"],
                            capture_output=True,
                            text=True,
                            timeout=2,
                            check=False,
                        ).stdout.strip()
                        if pane_pid:
                            if base_name == "codex":
                                native_log_path = _resolve_native_log_file(pane_pid, r"rollout-.*\.jsonl$", base_name=base_name)
                            elif base_name == "claude":
                                native_log_path = _resolve_native_log_file(pane_pid, r"1p_failed_events.*\.json$", base_name=base_name)
                            elif base_name == "copilot":
                                native_log_path = _resolve_native_log_file(pane_pid, r"events\.jsonl$", base_name=base_name)
                            
                            if native_log_path:
                                self._pane_native_log_paths[pane_id] = native_log_path
                    
                    if native_log_path and os.path.exists(native_log_path):
                        if base_name == "codex":
                            runtime_events = _parse_native_codex_log(native_log_path, limit=12)
                        elif base_name == "claude":
                            runtime_events = _parse_native_claude_log(native_log_path, limit=12)
                        elif base_name == "copilot":
                            runtime_events = _parse_native_copilot_log(native_log_path, limit=12)
                    elif base_name == "gemini":
                        runtime_events = _parse_native_gemini_log(self.session_name, self.repo_root, agent, limit=12)

                content = subprocess.run(
                    [*self.tmux_prefix, "capture-pane", "-p", "-S", "-80", "-t", pane_id],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                ).stdout
                
                if runtime_events is None:
                    # No native event log available: frontend shows the "thinking..." pulse.
                    runtime_events = []


                prev_runtime_events = self._pane_runtime_matches.get(agent, [])
                new_runtime_events = _pane_runtime_new_events(prev_runtime_events, runtime_events)
                self._pane_runtime_matches[agent] = runtime_events
                now = time.monotonic()
                prev = self._pane_snapshots.get(pane_id)
                self._pane_snapshots[pane_id] = content
                if prev is not None and content != prev:
                    self._pane_last_change[pane_id] = now
                    result[agent] = "running"
                else:
                    last_change = self._pane_last_change.get(pane_id, 0.0)
                    result[agent] = "running" if (now - last_change) < self.running_grace_seconds else "idle"
                if result[agent] == "running":
                    state = dict(self._pane_runtime_state.get(agent) or {})
                    current_event = state.get("current_event") if isinstance(state.get("current_event"), dict) else None
                    current_source_id = str((current_event or {}).get("source_id") or "").strip()
                    if runtime_events:
                        # Use only the latest event's text so the frontend shows the current activity
                        latest_event = runtime_events[-1]
                        latest_text = str(latest_event.get("text") or "").strip()
                        source_id = str(latest_event.get("source_id") or "").strip()
                        if not source_id or source_id != current_source_id:
                            self._pane_runtime_event_seq += 1
                            current_event = {
                                "id": f"{agent}:{self._pane_runtime_event_seq}",
                                "text": latest_text,
                                "source_id": source_id,
                            }
                        else:
                            # Update text even if the latest event ID is the same
                            if current_event:
                                current_event["text"] = latest_text
                    if current_event and str(current_event.get("text") or "").strip():
                        self._pane_runtime_state[agent] = {"current_event": current_event}
                    else:
                        # Keep last known state even when no current event (for idle agents)
                        pass
                else:
                    # Keep last known state for idle agents so the frontend still shows it
                    pass
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                result[agent] = "offline"
        try:
            update_shared_thinking_totals_from_statuses(
                self.repo_root,
                self.session_name,
                self.workspace,
                result,
            )
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            pass
        return result

    def agent_runtime_state(self) -> dict[str, dict]:
        result = {}
        for agent, payload in self._pane_runtime_state.items():
            raw_event = (payload or {}).get("current_event")
            if not isinstance(raw_event, dict):
                continue
            event_id = str(raw_event.get("id") or "").strip()
            text = str(raw_event.get("text") or "").rstrip()
            if not event_id or not text:
                continue
            result[agent] = {"current_event": {"id": event_id, "text": text}}
        return result

    def trace_content(self, agent: str, *, tail_lines: int | None = None) -> str:
        """Return tmux pane text. tail_lines: last N rows only (fast); None = full scrollback (heavy)."""
        pane_var = f"MULTIAGENT_PANE_{(agent or '').upper().replace('-', '_')}"
        content_str = ""
        try:
            r = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            line = r.stdout.strip()
            if r.returncode == 0 and "=" in line:
                pane_id = line.split("=", 1)[1]
                if tail_lines is not None:
                    n = max(1, min(int(tail_lines), 10_000))
                    start = f"-{n}"
                    cap_timeout = 3
                else:
                    # Large scrollback (tmux retains up to history-limit lines; see set -g history-limit).
                    start = "-500000"
                    cap_timeout = 8
                raw = subprocess.run(
                    [
                        *self.tmux_prefix,
                        "capture-pane",
                        "-p",
                        "-e",
                        "-S",
                        start,
                        "-t",
                        pane_id,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=cap_timeout,
                    check=False,
                ).stdout
                content_str = "\n".join(l.rstrip() for l in raw.splitlines())
            else:
                content_str = "Offline"
        except Exception as e:
            logging.error(f"Unexpected error: {e}", exc_info=True)
            content_str = f"Error: {e}"
        return content_str
