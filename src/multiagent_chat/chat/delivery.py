from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import uuid
from datetime import datetime as dt_datetime
from pathlib import Path

from ..agents.interaction import pane_delivery_payload, pane_prompt_ready_from_text
from native_log_sync.agents._shared.path_state import _agent_base_name
from ..agents.ensure_clis import agent_launch_readiness
from ..multiagent.instances import expected_instance_names
from ..jsonl_append import append_jsonl_entry


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
    return pane_prompt_ready_from_text(agent_name, res.stdout or "")


def wait_for_agent_prompt(self, pane_id: str, agent_name: str, *, send_prompt_wait_seconds: float) -> bool:
    base = _agent_base_name(agent_name)
    if base not in {"claude", "cursor", "codex", "copilot", "gemini", "qwen"}:
        return True
    if base != "qwen":
        return True

    deadline = time.time() + float(send_prompt_wait_seconds)
    while time.time() < deadline:
        if self._pane_prompt_ready(pane_id, agent_name):
            return True
        time.sleep(0.08)
    return False


def wait_for_send_slot(self, agent_name: str, *, claude_send_cooldown_seconds: float) -> None:
    if _agent_base_name(agent_name) != "claude":
        return
    last = float(self._agent_last_send_ts.get(agent_name) or 0.0)
    wait = float(claude_send_cooldown_seconds) - (time.time() - last)
    if wait > 0:
        time.sleep(wait)


def mark_agent_sent(self, agent_name: str) -> None:
    if _agent_base_name(agent_name) in {"claude", "cursor", "codex", "copilot", "gemini"}:
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


def _wait_for_session_instances(self, base_agents: list[str], timeout_seconds: float = 12.0) -> bool:
    expected_instances = expected_instance_names(base_agents)
    deadline = time.time() + max(0.5, float(timeout_seconds))
    while time.time() < deadline:
        has_session = subprocess.run(
            [*self.tmux_prefix, "has-session", "-t", f"={self.session_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if has_session.returncode == 0:
            ready = True
            for agent in expected_instances:
                pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
                pane_res = subprocess.run(
                    [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                pane_line = pane_res.stdout.strip()
                if pane_res.returncode != 0 or "=" not in pane_line:
                    ready = False
                    break
            if ready:
                return True
        time.sleep(0.08)
    return False


def _mark_pending_session_launched(self, launched_agents: list[str]) -> None:
    session_dir = self.index_path.parent
    meta_path = session_dir / ".meta"
    updated_at = dt_datetime.now().strftime("%Y-%m-%d %H:%M")
    meta = {}
    if meta_path.is_file():
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                meta = raw
        except Exception:
            meta = {}
    if "created_at" not in meta or not str(meta.get("created_at") or "").strip():
        meta["created_at"] = updated_at
    meta["updated_at"] = updated_at
    meta["session"] = self.session_name
    meta["workspace"] = self.workspace
    meta["agents"] = list(launched_agents or [])
    try:
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass
    self.targets = list(launched_agents or [])
    self.mark_session_activated()


def pending_launch_preflight(workspace: str, delivery_targets: list[str]) -> tuple[bool, dict]:
    if not delivery_targets:
        return False, {"ok": False, "error": "target is required"}
    readiness_failures = []
    seen_bases = set()
    for agent in delivery_targets:
        base = _agent_base_name(agent)
        if not base or base in seen_bases:
            continue
        seen_bases.add(base)
        readiness = agent_launch_readiness(Path(workspace), base)
        if readiness.get("status") != "ok":
            readiness_failures.append(readiness)
    if not readiness_failures:
        return True, {"ok": True}
    first = readiness_failures[0]
    return False, {
        "ok": False,
        "error": first.get("error") or "Selected agent is not ready to launch.",
        "reason": first.get("status") or "preflight_failed",
        "agent": first.get("agent") or "",
        "problems": readiness_failures,
    }


def _launch_pending_session(self, delivery_targets: list[str]) -> tuple[bool, dict]:
    ready, payload = pending_launch_preflight(self.workspace, delivery_targets)
    if not ready:
        return False, payload
    env = os.environ.copy()
    env["MULTIAGENT_SESSION"] = self.session_name
    env["MULTIAGENT_WORKSPACE"] = self.workspace
    env["MULTIAGENT_LOG_DIR"] = self.log_dir
    env["MULTIAGENT_INDEX_PATH"] = str(self.index_path)
    env["MULTIAGENT_BIN_DIR"] = str(Path(self.agent_send_path).parent)
    env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
    env["MULTIAGENT_SKIP_USER_CHAT"] = "1"
    env.pop("TMUX", None)
    env.pop("TMUX_PANE", None)
    env["MULTIAGENT_AGENT_NAME"] = "user"
    bin_dir = Path(self.agent_send_path).parent
    multiagent_bin = bin_dir / "multiagent"
    try:
        subprocess.Popen(
            [
                str(multiagent_bin),
                "--detach",
                "--session",
                self.session_name,
                "--workspace",
                self.workspace,
                "--agents",
                ",".join(delivery_targets),
            ],
            cwd=self.workspace or None,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logging.error("Unexpected error: %s", exc, exc_info=True)
        return False, {"ok": False, "error": str(exc)}
    if not _wait_for_session_instances(self, delivery_targets):
        return False, {"ok": False, "error": "session panes did not become ready"}
    time.sleep(0.5)
    for agent in delivery_targets:
        pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
        pane_res = subprocess.run(
            [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
            capture_output=True, text=True, check=False,
        )
        pane_id = pane_res.stdout.strip().split("=", 1)[-1] if "=" in pane_res.stdout else ""
        if pane_id:
            subprocess.run(
                [*self.tmux_prefix, "send-keys", "-t", pane_id, "Enter"],
                capture_output=True, check=False,
            )
    time.sleep(0.3)
    _mark_pending_session_launched(self, delivery_targets)
    return True, {"ok": True, "activated": True, "targets": list(delivery_targets)}


def launch_pending_session(self, requested_targets: list[str] | tuple[str, ...] | str) -> tuple[int, dict]:
    if not self.launch_pending():
        return 400, {"ok": False, "error": "session is already active"}
    if isinstance(requested_targets, str):
        raw_targets = [item.strip() for item in requested_targets.split(",") if item.strip()]
    else:
        raw_targets = [str(item).strip() for item in (requested_targets or []) if str(item).strip()]
    if not raw_targets:
        return 400, {"ok": False, "error": "agent required"}
    delivery_targets: list[str] = []
    seen_targets: set[str] = set()
    for raw_target in raw_targets:
        if raw_target in {"user", "others"}:
            return 400, {"ok": False, "error": "select an initial agent"}
        for resolved in self.resolve_target_agents(raw_target):
            if resolved in {"user", "others"} or resolved in seen_targets:
                continue
            seen_targets.add(resolved)
            delivery_targets.append(resolved)
    if len(delivery_targets) != 1:
        return 400, {"ok": False, "error": "select exactly one initial agent"}
    activated, payload = _launch_pending_session(self, delivery_targets)
    if not activated:
        return 400, payload
    return 200, {
        **payload,
        "selected_agent": delivery_targets[0],
        "targets": self.active_agents(),
    }


def send_message(
    self,
    target: str,
    message: str,
    reply_to: str = "",
    silent: bool = False,
    raw: bool = False,
    append_entry: bool = True,
) -> tuple[int, dict]:
    target = (target or "").strip()
    message = (message or "").strip()
    reply_to = (reply_to or "").strip()
    if not message:
        return 400, {"ok": False, "error": "message is required"}
    if self.launch_pending():
        return 400, {"ok": False, "error": "Start the session first by selecting an initial agent."}
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
                        time.sleep(0.08)
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
    if not target:
        target = "user"
    targets = [item.strip() for item in target.split(",") if item.strip()]
    if not targets:
        return 400, {"ok": False, "error": "target is required"}
    if targets == ["user"]:
        if append_entry:
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
                time.sleep(0.08)
                enter_res = subprocess.run(
                    [*self.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"],
                    capture_output=True,
                    check=False,
                )
                if enter_res.returncode != 0:
                    return 400, {"ok": False, "error": f"Failed to deliver to: {agent}"}
                self._mark_agent_sent(agent)
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
            agent_payload = pane_delivery_payload(agent, payload)
            type_res = subprocess.run(
                [*self.tmux_prefix, "send-keys", "-t", pane_id, "-l", agent_payload],
                text=True,
                capture_output=True,
                check=False,
            )
            if type_res.returncode != 0:
                failed_targets.append(agent)
                continue
            time.sleep(0.08)
            enter_res = subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"], capture_output=True, check=False)
            if enter_res.returncode != 0:
                failed_targets.append(agent)
                continue
            self._mark_agent_sent(agent)
            successful_targets.append(agent)
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return 500, {"ok": False, "error": str(exc)}
    if not successful_targets:
        if failed_targets:
            return 400, {"ok": False, "error": f"Failed to deliver to: {failed_targets[0]}"}
        return 400, {"ok": False, "error": "No target panes resolved."}
    if append_entry:
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
