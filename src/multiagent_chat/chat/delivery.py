from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime as dt_datetime
from pathlib import Path

from native_log_sync.agents._shared.path_state import _agent_base_name
from ..agents.ensure_clis import agent_launch_readiness
from ..multiagent.instances import expected_instance_names
from .monitor import apply_saved_monitor_setting
from backend_core.tmux.pane import send_enter


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
                pane_id = self.pane_id_for_agent(agent)
                if not pane_id:
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
        pane_id = self.pane_id_for_agent(agent)
        if pane_id:
            send_enter(self, pane_id, subprocess_module=subprocess)
    time.sleep(0.3)
    _mark_pending_session_launched(self, delivery_targets)
    apply_saved_monitor_setting(
        self,
        subprocess_module=subprocess,
        os_module=os,
        path_class=Path,
        logging_module=logging,
    )
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


