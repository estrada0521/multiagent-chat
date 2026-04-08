from __future__ import annotations

import logging
import os
import re
import subprocess
import time
import uuid
from datetime import datetime as dt_datetime
from pathlib import Path

from .chat_sync_cursor_core import _agent_base_name
from .jsonl_append import append_jsonl_entry


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


def parse_pane_direct_command(message: str) -> dict | None:
    normalized = (message or "").strip().lower()
    if normalized == "model":
        return {"name": "model", "repeat": 1}
    match = re.fullmatch(r"(up|down)(?:\s+(\d+))?", normalized)
    if not match:
        return None
    repeat = max(1, min(int(match.group(2) or "1"), 100))
    return {"name": match.group(1), "repeat": repeat}


def send_message(
    self,
    target: str,
    message: str,
    reply_to: str = "",
    silent: bool = False,
    raw: bool = False,
) -> tuple[int, dict]:
    target = (target or "").strip()
    message = (message or "").strip()
    reply_to = (reply_to or "").strip()
    if not message:
        return 400, {"ok": False, "error": "message is required"}
    if target:
        target = ",".join(self.resolve_target_agents(target))
    env = os.environ.copy()
    env["MULTIAGENT_SESSION"] = self.session_name
    env["MULTIAGENT_WORKSPACE"] = self.workspace
    env["MULTIAGENT_LOG_DIR"] = self.log_dir
    env["MULTIAGENT_INDEX_PATH"] = str(self.index_path)
    env["MULTIAGENT_BIN_DIR"] = str(Path(self.agent_send_path).parent)
    env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
    env.pop("TMUX", None)
    env.pop("TMUX_PANE", None)
    env["MULTIAGENT_AGENT_NAME"] = "user"
    bin_dir = Path(self.agent_send_path).parent
    pane_direct = parse_pane_direct_command(message)
    if message in {"save", "interrupt", "ctrlc", "enter", "restart", "resume"} or pane_direct:
        if message in {"interrupt", "ctrlc", "enter", "restart", "resume"} or pane_direct:
            if not target:
                return 400, {"ok": False, "error": "target is required"}
            control_targets = [item.strip() for item in target.split(",") if item.strip()]
            try:
                for agent in control_targets:
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
            if message in {"restart", "resume"} and control_targets:
                action = "Restarted" if message == "restart" else "Resumed"
                self.append_system_entry(
                    f"{action}: {', '.join(control_targets)}",
                    kind="agent-control",
                    command=message,
                    targets=control_targets,
                )
            return 200, {"ok": True, "mode": pane_direct["name"] if pane_direct else message}
        command = [str(bin_dir / "multiagent"), message, "--session", self.session_name]
        try:
            result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return 500, {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return 400, {"ok": False, "error": (result.stderr or result.stdout or f"{message} failed").strip()}
        return 200, {"ok": True, "mode": message}
    if not target:
        target = "user"
    targets = [item.strip() for item in target.split(",") if item.strip()]
    if not targets:
        return 400, {"ok": False, "error": "target is required"}
    if targets == ["user"]:
        entry = {
            "timestamp": dt_datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session": self.session_name,
            "sender": "user",
            "targets": ["user"],
            "message": message,
            "msg_id": uuid.uuid4().hex[:12],
        }
        if reply_to:
            entry["reply_to"] = reply_to
            reply_preview = self._reply_preview_for(reply_to)
            if reply_preview:
                entry["reply_preview"] = reply_preview
        append_jsonl_entry(self.index_path, entry)
        return 200, {"ok": True, "mode": "memo"}
    if "user" in targets:
        return 400, {"ok": False, "error": 'target "user" cannot be combined with other targets'}
    delivery_targets: list[str] = []
    seen_targets: set[str] = set()
    for agent in targets:
        if agent == "others":
            for expanded in self.active_agents():
                if expanded not in seen_targets:
                    seen_targets.add(expanded)
                    delivery_targets.append(expanded)
            continue
        if agent not in seen_targets:
            seen_targets.add(agent)
            delivery_targets.append(agent)
    if not delivery_targets:
        return 400, {"ok": False, "error": "target is required"}
    base_target_counts: dict[str, int] = {}
    for agent in delivery_targets:
        base = _agent_base_name(agent)
        base_target_counts[base] = base_target_counts.get(base, 0) + 1
    if silent or raw:
        try:
            for agent in delivery_targets:
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
                self._wait_for_send_slot(agent)
                if not self._wait_for_agent_prompt(pane_id, agent):
                    return 400, {"ok": False, "error": f"pane not ready for {agent}"}
                typed_res = subprocess.run(
                    [*self.tmux_prefix, "send-keys", "-t", pane_id, "-l", message],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if typed_res.returncode != 0:
                    return 400, {"ok": False, "error": f"Failed to deliver to: {agent}"}
                time.sleep(0.3)
                enter_res = subprocess.run(
                    [*self.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"],
                    capture_output=True,
                    check=False,
                )
                if enter_res.returncode != 0:
                    return 400, {"ok": False, "error": f"Failed to deliver to: {agent}"}
                self._mark_agent_sent(agent)
                if base_target_counts.get(_agent_base_name(agent), 0) == 1:
                    self._handoff_shared_sync_claim(agent)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return 500, {"ok": False, "error": str(exc)}
        return 200, {"ok": True, "raw": bool(raw)}
    payload = f"[From: User]\n{message}"
    successful_targets: list[str] = []
    failed_targets: list[str] = []
    try:
        for agent in delivery_targets:
            pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
            pane_res = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                capture_output=True,
                text=True,
                check=False,
            )
            pane_id = pane_res.stdout.strip().split("=", 1)[-1] if "=" in pane_res.stdout else ""
            if not pane_id:
                failed_targets.append(agent)
                continue
            self._wait_for_send_slot(agent)
            if not self._wait_for_agent_prompt(pane_id, agent):
                failed_targets.append(agent)
                continue
            type_res = subprocess.run(
                [*self.tmux_prefix, "send-keys", "-t", pane_id, "-l", payload],
                text=True,
                capture_output=True,
                check=False,
            )
            if type_res.returncode != 0:
                failed_targets.append(agent)
                continue
            time.sleep(0.3)
            enter_res = subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"], capture_output=True, check=False)
            if enter_res.returncode != 0:
                failed_targets.append(agent)
                continue
            self._mark_agent_sent(agent)
            if base_target_counts.get(_agent_base_name(agent), 0) == 1:
                self._handoff_shared_sync_claim(agent)
            successful_targets.append(agent)
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return 500, {"ok": False, "error": str(exc)}
    if not successful_targets:
        if failed_targets:
            return 400, {"ok": False, "error": f"Failed to deliver to: {failed_targets[0]}"}
        return 400, {"ok": False, "error": "No target panes resolved."}
    entry = {
        "timestamp": dt_datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session": self.session_name,
        "sender": "user",
        "targets": successful_targets,
        "message": payload,
        "msg_id": uuid.uuid4().hex[:12],
    }
    if reply_to:
        entry["reply_to"] = reply_to
        reply_preview = self._reply_preview_for(reply_to)
        if reply_preview:
            entry["reply_preview"] = reply_preview
    append_jsonl_entry(self.index_path, entry)
    if failed_targets:
        return 400, {"ok": False, "error": f"Failed to deliver to: {', '.join(failed_targets)}"}
    return 200, {"ok": True}
