from __future__ import annotations

import os
import subprocess


def _pane_id_for_agent(runtime, agent: str) -> str:
    pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
    result = subprocess.run(
        [*runtime.tmux_prefix, "show-environment", "-t", runtime.session_name, pane_var],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )
    line = result.stdout.strip()
    if result.returncode != 0 or "=" not in line:
        return ""
    return line.split("=", 1)[1].strip()


def _pane_field(runtime, pane_id: str, field: str) -> str:
    if not pane_id:
        return ""
    return subprocess.run(
        [*runtime.tmux_prefix, "display-message", "-p", "-t", pane_id, field],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    ).stdout.strip()


def _cached_native_log_path(runtime, pane_id: str, pane_pid: str) -> str:
    cached_entry = runtime._pane_native_log_paths.get(pane_id)
    cached_pid = ""
    cached_path = ""
    if isinstance(cached_entry, tuple) and len(cached_entry) == 2:
        cached_pid = str(cached_entry[0] or "")
        cached_path = str(cached_entry[1] or "")
    elif isinstance(cached_entry, str):
        cached_path = cached_entry
    if cached_path and os.path.exists(cached_path) and (
        not cached_pid or cached_pid == pane_pid
    ):
        return cached_path
    if cached_path and cached_pid and cached_pid != pane_pid:
        runtime._pane_native_log_paths.pop(pane_id, None)
    return ""


def sync_agent_assistant_messages(runtime, agent: str) -> None:
    base_name = (agent or "").lower().split("-")[0]
    if base_name in ("claude", "gemini", "cursor", "qwen"):
        sync_method = getattr(runtime, f"_sync_{base_name}_assistant_messages", None)
        if not sync_method:
            return
        native_log_path = ""
        pane_workspace = ""
        pane_id = _pane_id_for_agent(runtime, agent)
        if pane_id:
            if base_name == "claude":
                pane_workspace = _pane_field(runtime, pane_id, "#{pane_current_path}")
            pane_pid = _pane_field(runtime, pane_id, "#{pane_pid}")
            if pane_pid:
                native_log_path = _cached_native_log_path(runtime, pane_id, pane_pid)
                if not native_log_path:
                    from agent_index.chat_runtime_parse_core import _resolve_native_log_file

                    patterns = {
                        "claude": r"\.jsonl$",
                        "cursor": r"\.jsonl$",
                        "qwen": r"\.jsonl$",
                        "gemini": r"session-.*\.json$",
                    }
                    native_log_path = _resolve_native_log_file(
                        pane_pid,
                        patterns[base_name],
                        base_name=base_name,
                    ) or ""
                    if native_log_path:
                        runtime._pane_native_log_paths[pane_id] = (pane_pid, native_log_path)

        if native_log_path and os.path.exists(native_log_path):
            if base_name == "claude":
                sync_method(agent, native_log_path, workspace_hint=pane_workspace)
            else:
                sync_method(agent, native_log_path)
        else:
            if base_name == "claude":
                sync_method(agent, workspace_hint=pane_workspace)
            else:
                sync_method(agent)
        return

    if base_name in ("codex", "copilot"):
        pane_id = _pane_id_for_agent(runtime, agent)
        if not pane_id:
            return
        pane_pid = _pane_field(runtime, pane_id, "#{pane_pid}")
        if not pane_pid:
            return

        native_log_path = _cached_native_log_path(runtime, pane_id, pane_pid)
        if not native_log_path:
            from agent_index.chat_runtime_parse_core import _resolve_native_log_file

            if base_name == "codex":
                native_log_path = _resolve_native_log_file(
                    pane_pid,
                    r"rollout-.*\.jsonl$",
                    base_name=base_name,
                ) or ""
            else:
                native_log_path = _resolve_native_log_file(
                    pane_pid,
                    r"events\.jsonl$",
                    base_name=base_name,
                ) or ""
            if native_log_path:
                runtime._pane_native_log_paths[pane_id] = (pane_pid, native_log_path)

        sync_method = getattr(runtime, f"_sync_{base_name}_assistant_messages", None)
        if not sync_method:
            return
        if native_log_path and os.path.exists(native_log_path):
            sync_method(agent, native_log_path)
        elif base_name == "codex":
            sync_method(agent)
        return

    if base_name == "opencode":
        sync_method = getattr(runtime, f"_sync_{base_name}_assistant_messages", None)
        if sync_method:
            sync_method(agent)
