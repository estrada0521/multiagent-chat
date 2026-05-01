from __future__ import annotations

import logging
import subprocess
import time
import uuid
from datetime import datetime as dt_datetime

from native_log_sync.agents._shared.path_state import _agent_base_name
from backend_core.access.files import append_jsonl_entry
from backend_core.tmux.pane import capture_pane_text, send_enter, send_keys_literal
from multiagent_chat.agents.interaction import pane_delivery_payload, pane_prompt_ready_from_text


def pane_prompt_ready(self, pane_id: str, agent_name: str) -> bool:
    base = _agent_base_name(agent_name)
    if base not in {"claude", "codex", "gemini", "qwen", "cursor"}:
        return True
    try:
        pane_text = capture_pane_text(
            self,
            pane_id,
            start="-40",
            timeout_seconds=2,
            subprocess_module=subprocess,
        )
        if not pane_text:
            return False
    except Exception:
        return False
    return pane_prompt_ready_from_text(agent_name, pane_text)


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
    if silent or raw:
        try:
            for agent in delivery_targets:
                pane_id = self.pane_id_for_agent(agent)
                if not pane_id:
                    return 400, {"ok": False, "error": f"pane not found for {agent}"}
                self._wait_for_send_slot(agent)
                if not self._wait_for_agent_prompt(pane_id, agent):
                    return 400, {"ok": False, "error": f"pane not ready for {agent}"}
                if not send_keys_literal(self, pane_id, message, subprocess_module=subprocess):
                    return 400, {"ok": False, "error": f"Failed to deliver to: {agent}"}
                time.sleep(0.08)
                if not send_enter(self, pane_id, subprocess_module=subprocess):
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
            pane_id = self.pane_id_for_agent(agent)
            if not pane_id:
                failed_targets.append(agent)
                continue
            self._wait_for_send_slot(agent)
            if not self._wait_for_agent_prompt(pane_id, agent):
                failed_targets.append(agent)
                continue
            agent_payload = pane_delivery_payload(agent, payload)
            if not send_keys_literal(self, pane_id, agent_payload, subprocess_module=subprocess):
                failed_targets.append(agent)
                continue
            time.sleep(0.08)
            if not send_enter(self, pane_id, subprocess_module=subprocess):
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
