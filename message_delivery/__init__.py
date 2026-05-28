from __future__ import annotations

import logging
import os
import subprocess
import time
import uuid
from datetime import datetime as dt_datetime

from native_log_sync.agents._shared.path_state import _agent_base_name
from backend_core.access.files import append_jsonl_entry
from message_delivery.interaction import pane_delivery_payload
from message_delivery.paste_timing import delivery_paste_delay_seconds


def _send_keys_literal(runtime, pane_id: str, text: str, *, subprocess_module=subprocess) -> bool:
    pane = str(pane_id or "").strip()
    if not pane:
        return False
    result = subprocess_module.run(
        [*runtime.tmux_prefix, "send-keys", "-t", pane, "-l", "--", str(text)],
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0


def _send_enter(runtime, pane_id: str, *, subprocess_module=subprocess) -> bool:
    pane = str(pane_id or "").strip()
    if not pane:
        return False
    result = subprocess_module.run(
        [*runtime.tmux_prefix, "send-keys", "-t", pane, "", "Enter"],
        capture_output=True, check=False,
    )
    return result.returncode == 0


def _session_attached_count(runtime, *, subprocess_module=subprocess) -> int | None:
    session_name = str(getattr(runtime, "session_name", "") or "").strip()
    if not session_name:
        return None
    result = subprocess_module.run(
        [*runtime.tmux_prefix, "display-message", "-p", "-t", session_name, "#{session_attached}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    raw = str(result.stdout or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def wait_for_send_slot(self, agent_name: str, *, claude_send_cooldown_seconds: float) -> None:
    if _agent_base_name(agent_name) != "claude":
        return
    last = float(self._agent_last_send_ts.get(agent_name) or 0.0)
    wait = float(claude_send_cooldown_seconds) - (time.time() - last)
    if wait > 0:
        time.sleep(wait)


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
    if target:
        target = ",".join(self.resolve_target_agents(target))
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
    attached_count = _session_attached_count(self, subprocess_module=subprocess)
    if silent or raw:
        try:
            for agent in delivery_targets:
                pane_id = self.pane_id_for_agent(agent)
                if not pane_id:
                    return 400, {"ok": False, "error": f"pane not found for {agent}"}
                self._wait_for_send_slot(agent)
                if not _send_keys_literal(self, pane_id, message, subprocess_module=subprocess):
                    return 400, {"ok": False, "error": f"Failed to deliver to: {agent}"}
                time.sleep(
                    delivery_paste_delay_seconds(
                        message,
                        env=os.environ,
                        session_attached_count=attached_count,
                    )
                )
                if not _send_enter(self, pane_id, subprocess_module=subprocess):
                    return 400, {"ok": False, "error": f"Failed to deliver to: {agent}"}
                self._mark_agent_sent(agent)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return 500, {"ok": False, "error": str(exc)}
        return 200, {"ok": True, "raw": bool(raw)}
    payload = message
    successful_targets: list[str] = []
    failed_targets: list[str] = []
    try:
        for agent in delivery_targets:
            pane_id = self.pane_id_for_agent(agent)
            if not pane_id:
                failed_targets.append(agent)
                continue
            self._wait_for_send_slot(agent)
            agent_payload = pane_delivery_payload(agent, payload)
            if not _send_keys_literal(self, pane_id, agent_payload, subprocess_module=subprocess):
                failed_targets.append(agent)
                continue
            time.sleep(
                delivery_paste_delay_seconds(
                    agent_payload,
                    env=os.environ,
                    session_attached_count=attached_count,
                )
            )
            if not _send_enter(self, pane_id, subprocess_module=subprocess):
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


def _update_running_env(runtime, agent: str, running: bool) -> None:
    upper = agent.upper().replace("-", "_")
    var = f"MULTIAGENT_RUNNING_{upper}"
    try:
        if running:
            subprocess.run(
                [*runtime.tmux_prefix, "set-environment", "-t", runtime.session_name, var, "1"],
                capture_output=True, check=False, timeout=1,
            )
        else:
            subprocess.run(
                [*runtime.tmux_prefix, "set-environment", "-u", "-t", runtime.session_name, var],
                capture_output=True, check=False, timeout=1,
            )
    except Exception:
        pass


def mark_agent_sent(self, agent_name: str) -> None:
    base = _agent_base_name(agent_name)
    if base in {"claude", "cursor", "codex", "copilot", "gemini"}:
        self._agent_last_send_ts[agent_name] = time.time()
        self._mark_running(agent_name)
