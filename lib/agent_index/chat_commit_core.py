from __future__ import annotations

import fcntl
import json
import logging
import os
import subprocess
from collections import deque
from pathlib import Path


def read_commit_state_locked(runtime, handle, *, json_module=json, logging_module=logging) -> dict:
    handle.seek(0)
    raw = handle.read().strip()
    if not raw:
        return {}
    try:
        return json_module.loads(raw)
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
        return {}


def commit_state_payload(commit: dict) -> dict:
    return {
        "last_commit_hash": commit["hash"],
        "last_commit_short": commit["short"],
        "last_commit_subject": commit["subject"],
    }


def write_commit_state_locked(runtime, handle, commit: dict, *, json_module=json) -> None:
    handle.seek(0)
    handle.truncate()
    handle.write(json_module.dumps(commit_state_payload(commit), ensure_ascii=False))
    handle.flush()


def has_logged_commit_entry(
    runtime,
    commit_hash: str,
    *,
    recent_limit: int = 256,
    deque_class=deque,
    json_module=json,
    logging_module=logging,
) -> bool:
    commit_hash = (commit_hash or "").strip()
    if not commit_hash or not runtime.index_path.exists():
        return False
    try:
        recent_lines: deque[str] = deque_class(maxlen=max(32, int(recent_limit)))
        with runtime.index_path.open("r", encoding="utf-8") as f:
            for line in f:
                recent_lines.append(line)
        for line in reversed(recent_lines):
            try:
                entry = json_module.loads(line)
            except Exception:
                continue
            if entry.get("kind") != "git-commit":
                continue
            if (entry.get("commit_hash") or "").strip() == commit_hash:
                return True
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
    return False


def start_direct_provider_run(
    runtime,
    provider: str,
    prompt: str,
    reply_to: str = "",
    provider_model: str = "",
    *,
    path_class=Path,
    os_module=os,
    subprocess_module=subprocess,
    logging_module=logging,
) -> tuple[int, dict]:
    provider_name = (provider or "").strip().lower()
    prompt = (prompt or "").strip()
    reply_to = (reply_to or "").strip()
    provider_model = (provider_model or "").strip()
    if not runtime.session_is_active:
        return 409, {"ok": False, "error": "archived session is read-only"}
    supported_providers = {"gemini", "ollama"}
    if provider_name not in supported_providers:
        return 400, {"ok": False, "error": f"unsupported direct provider: {provider_name}"}
    if not prompt:
        return 400, {"ok": False, "error": "message is required"}
    bin_dir = path_class(runtime.agent_send_path).parent
    runner_map = {
        "gemini": "multiagent-gemini-direct-run",
        "ollama": "multiagent-ollama-direct-run",
    }
    runner = bin_dir / runner_map[provider_name]
    if not runner.is_file():
        return 500, {"ok": False, "error": f"{runner_map[provider_name]} not found"}
    env = os_module.environ.copy()
    env.pop("MULTIAGENT_AGENT_NAME", None)
    env["MULTIAGENT_SESSION"] = runtime.session_name
    env["MULTIAGENT_WORKSPACE"] = runtime.workspace
    env["MULTIAGENT_LOG_DIR"] = runtime.log_dir
    env["MULTIAGENT_BIN_DIR"] = str(bin_dir)
    env["MULTIAGENT_TMUX_SOCKET"] = runtime.tmux_socket
    env.pop("TMUX", None)
    env.pop("TMUX_PANE", None)
    command = [
        str(runner),
        "--session",
        runtime.session_name,
        "--workspace",
        runtime.workspace,
        "--sender",
        provider_name,
        "--target",
        "user",
        "--prompt-sender",
        "user",
        "--prompt-target",
        provider_name,
    ]
    if runtime.log_dir:
        command.extend(["--log-dir", runtime.log_dir])
    if reply_to:
        command.extend(["--reply-to", reply_to])
    if provider_model:
        command.extend(["--model", provider_model])
    try:
        proc = subprocess_module.Popen(
            command,
            cwd=runtime.workspace or None,
            env=env,
            stdin=subprocess_module.PIPE,
            stdout=subprocess_module.DEVNULL,
            stderr=subprocess_module.DEVNULL,
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
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
        return 500, {"ok": False, "error": str(exc)}
    return 200, {"ok": True, "mode": "provider-direct", "provider": provider_name}


def read_commit_state(
    runtime,
    *,
    fcntl_module=fcntl,
    logging_module=logging,
) -> dict:
    if not runtime.commit_state_path.exists():
        return {}
    try:
        with runtime.commit_state_path.open("a+", encoding="utf-8") as handle:
            fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_SH)
            try:
                return runtime._read_commit_state_locked(handle)
            finally:
                fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_UN)
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
        return {}


def write_commit_state(
    runtime,
    commit: dict,
    *,
    fcntl_module=fcntl,
    logging_module=logging,
) -> None:
    try:
        runtime.commit_state_path.parent.mkdir(parents=True, exist_ok=True)
        with runtime.commit_state_path.open("a+", encoding="utf-8") as handle:
            fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_EX)
            try:
                runtime._write_commit_state_locked(handle, commit)
            finally:
                fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_UN)
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
        pass


def record_git_commit_locked(runtime, handle, commit: dict, *, agent: str = "") -> bool:
    if runtime.has_logged_commit_entry(commit["hash"]):
        runtime._write_commit_state_locked(handle, commit)
        return False
    runtime.append_system_entry(
        f"Commit: {commit['short']} {commit['subject']}",
        kind="git-commit",
        commit_hash=commit["hash"],
        commit_short=commit["short"],
        agent=agent,
    )
    runtime._write_commit_state_locked(handle, commit)
    return True


def record_git_commit(
    runtime,
    *,
    commit_hash: str,
    commit_short: str,
    subject: str,
    agent: str = "",
    fcntl_module=fcntl,
    logging_module=logging,
) -> bool:
    commit = {
        "hash": (commit_hash or "").strip(),
        "short": (commit_short or "").strip(),
        "subject": str(subject or "").strip(),
    }
    if not commit["hash"] or not commit["short"] or not commit["subject"]:
        return False
    try:
        runtime.commit_state_path.parent.mkdir(parents=True, exist_ok=True)
        with runtime.commit_state_path.open("a+", encoding="utf-8") as handle:
            fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_EX)
            try:
                return runtime._record_git_commit_locked(handle, commit, agent=agent)
            finally:
                fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_UN)
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
        return False


def current_git_commit(
    runtime,
    *,
    subprocess_module=subprocess,
    logging_module=logging,
) -> dict | None:
    try:
        result = subprocess_module.run(
            ["git", "-C", runtime.workspace, "log", "-1", "--format=%H%x1f%h%x1f%s"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
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


def git_commits_since(
    runtime,
    base_hash: str,
    *,
    subprocess_module=subprocess,
    logging_module=logging,
) -> list[dict] | None:
    try:
        result = subprocess_module.run(
            ["git", "-C", runtime.workspace, "log", "--reverse", "--format=%H%x1f%h%x1f%s", f"{base_hash}..HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
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


def ensure_commit_announcements(
    runtime,
    *,
    fcntl_module=fcntl,
    logging_module=logging,
) -> None:
    current = runtime.current_git_commit()
    if not current:
        return
    try:
        runtime.commit_state_path.parent.mkdir(parents=True, exist_ok=True)
        with runtime.commit_state_path.open("a+", encoding="utf-8") as handle:
            fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_EX)
            try:
                state = runtime._read_commit_state_locked(handle)
                last_hash = (state.get("last_commit_hash") or "").strip()
                if not last_hash:
                    runtime._record_git_commit_locked(handle, current)
                    return
                if last_hash == current["hash"]:
                    return
                commits = runtime.git_commits_since(last_hash)
                if commits is None:
                    runtime._record_git_commit_locked(handle, current)
                    return
                if not commits:
                    runtime._record_git_commit_locked(handle, current)
                    return
                for commit in commits:
                    runtime._record_git_commit_locked(handle, commit)
            finally:
                fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_UN)
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
