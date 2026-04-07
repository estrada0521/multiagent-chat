from __future__ import annotations

import subprocess
import time

from .chat_sync_cursor_core import _agent_base_name


def pane_prompt_ready(self, pane_id: str, agent_name: str) -> bool:
    base = _agent_base_name(agent_name)
    if base not in {"claude", "codex", "gemini", "qwen", "cursor"}:
        return True
    try:
        res = subprocess.run(
            [*self.tmux_prefix, "capture-pane", "-p", "-t", pane_id, "-S", "-40"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode != 0:
            return False
    except Exception:
        return False
    lines = [
        normalized
        for normalized in (
            (line or "").replace("\u00a0", " ").strip()
            for line in (res.stdout or "").splitlines()
        )
        if normalized
    ]
    tail = lines[-20:]
    if base == "claude":
        return any(line == "❯" for line in tail)
    if base == "codex":
        return any(line.startswith("›") for line in tail)
    if base in {"gemini", "qwen"}:
        return any("Type your message or @path/to/file" in line for line in tail)
    if base == "cursor":
        return any("/ commands" in line and "@ files" in line for line in tail)
    return True


def pane_has_escape_cancel_prompt(self, pane_id: str, agent_name: str) -> bool:
    if _agent_base_name(agent_name) != "claude":
        return False
    try:
        res = subprocess.run(
            [*self.tmux_prefix, "capture-pane", "-p", "-t", pane_id, "-S", "-40"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode != 0:
            return False
    except Exception:
        return False
    text = (res.stdout or "").replace("\u00a0", " ")
    return "Esc to cancel" in text and "What do you want to do?" in text


def pane_has_claude_trust_prompt(self, pane_id: str, agent_name: str) -> bool:
    if _agent_base_name(agent_name) != "claude":
        return False
    try:
        res = subprocess.run(
            [*self.tmux_prefix, "capture-pane", "-p", "-t", pane_id, "-S", "-60"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode != 0:
            return False
    except Exception:
        return False
    text = (res.stdout or "").replace("\u00a0", " ")
    return (
        "Quick safety check" in text
        and "Yes, I trust this folder" in text
        and "Enter to confirm" in text
    )


def pane_has_gemini_trust_prompt(self, pane_id: str, agent_name: str) -> bool:
    if _agent_base_name(agent_name) != "gemini":
        return False
    try:
        res = subprocess.run(
            [*self.tmux_prefix, "capture-pane", "-p", "-t", pane_id, "-S", "-80"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode != 0:
            return False
    except Exception:
        return False
    text = (res.stdout or "").replace("\u00a0", " ")
    return "Do you trust the files in this folder?" in text and "Trust folder" in text


def pane_has_cursor_trust_prompt(self, pane_id: str, agent_name: str) -> bool:
    if _agent_base_name(agent_name) != "cursor":
        return False
    try:
        res = subprocess.run(
            [*self.tmux_prefix, "capture-pane", "-p", "-t", pane_id, "-S", "-80"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode != 0:
            return False
    except Exception:
        return False
    text = (res.stdout or "").replace("\u00a0", " ")
    return "Workspace Trust Required" in text and "Trust this workspace" in text


def wait_for_agent_prompt(self, pane_id: str, agent_name: str, *, send_prompt_wait_seconds: float) -> bool:
    base = _agent_base_name(agent_name)
    if base not in {"claude", "codex", "gemini", "qwen", "cursor"}:
        return True
    deadline = time.time() + float(send_prompt_wait_seconds)
    while time.time() < deadline:
        if self._pane_prompt_ready(pane_id, agent_name):
            return True
        if base == "claude" and self._pane_has_claude_trust_prompt(pane_id, agent_name):
            subprocess.run(
                [*self.tmux_prefix, "send-keys", "-t", pane_id, "Enter"],
                capture_output=True,
                check=False,
            )
            time.sleep(0.3)
            continue
        if base == "claude" and self._pane_has_escape_cancel_prompt(pane_id, agent_name):
            subprocess.run(
                [*self.tmux_prefix, "send-keys", "-t", pane_id, "Escape"],
                capture_output=True,
                check=False,
            )
            time.sleep(0.2)
            continue
        if base == "gemini" and self._pane_has_gemini_trust_prompt(pane_id, agent_name):
            subprocess.run(
                [*self.tmux_prefix, "send-keys", "-t", pane_id, "Enter"],
                capture_output=True,
                check=False,
            )
            time.sleep(0.3)
            continue
        if base == "cursor" and self._pane_has_cursor_trust_prompt(pane_id, agent_name):
            subprocess.run(
                [*self.tmux_prefix, "send-keys", "-t", pane_id, "a"],
                capture_output=True,
                check=False,
            )
            time.sleep(0.3)
            continue
        time.sleep(0.2)
    return False


def wait_for_send_slot(self, agent_name: str, *, claude_send_cooldown_seconds: float) -> None:
    if _agent_base_name(agent_name) != "claude":
        return
    last = float(self._agent_last_send_ts.get(agent_name) or 0.0)
    wait = float(claude_send_cooldown_seconds) - (time.time() - last)
    if wait > 0:
        time.sleep(wait)


def mark_agent_sent(self, agent_name: str) -> None:
    if _agent_base_name(agent_name) == "claude":
        self._agent_last_send_ts[agent_name] = time.time()
