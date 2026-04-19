from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote as url_quote


def _read_json_body(handler):
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8") or "{}"), None
    except json.JSONDecodeError:
        return None, "invalid json"


def post_start_session(
    handler,
    *,
    all_agent_names,
    new_session_max_per_agent: int,
    script_path,
    wait_for_session_instances_fn,
    ensure_chat_server_fn,
    active_session_records_query_fn,
    agent_launch_readiness_fn,
) -> None:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw)
    except Exception:
        handler._send_json(400, {"ok": False, "error": "invalid JSON"})
        return
    workspace = (data.get("workspace") or "").strip()
    session_name = (data.get("session_name") or "").strip()
    agents = [a for a in (data.get("agents") or []) if a in all_agent_names]
    if not workspace or not Path(workspace).is_dir():
        handler._send_json(400, {"ok": False, "error": f"Invalid workspace: {workspace or '(empty)'}"})
        return
    if not agents:
        handler._send_json(400, {"ok": False, "error": "Select at least one agent."})
        return
    agent_counts = {}
    for agent in agents:
        agent_counts[agent] = agent_counts.get(agent, 0) + 1
    if any(count > new_session_max_per_agent for count in agent_counts.values()):
        handler._send_json(400, {"ok": False, "error": f"Each agent is limited to {new_session_max_per_agent} instances."})
        return
    if not session_name:
        session_name = Path(workspace).name
    session_name = re.sub(r"[^a-zA-Z0-9_.\-]", "-", session_name)[:64]
    launch_agents = agents
    preflight = []
    seen_bases = set()
    for agent in launch_agents:
        base = str(agent or "").split("-", 1)[0]
        if not base or base in seen_bases:
            continue
        seen_bases.add(base)
        readiness = agent_launch_readiness_fn(Path(workspace), base)
        if readiness.get("status") != "ok":
            preflight.append(readiness)
    if preflight:
        first = preflight[0]
        handler._send_json(
            400,
            {
                "ok": False,
                "error": first.get("error") or "Selected agent is not ready to launch.",
                "reason": first.get("status") or "preflight_failed",
                "agent": first.get("agent") or "",
                "problems": preflight,
            },
        )
        return
    agents_str = ",".join(launch_agents)
    multiagent_bin = str(script_path.parent / "multiagent")
    launch_env = os.environ.copy()
    launch_env["MULTIAGENT_SKIP_USER_CHAT"] = "1"
    try:
        subprocess.Popen(
            [multiagent_bin, "--detach", "--session", session_name, "--workspace", workspace, "--agents", agents_str],
            cwd=workspace,
            env=launch_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    if not wait_for_session_instances_fn(session_name, launch_agents):
        handler._send_json(500, {"ok": False, "error": "session panes did not become ready"})
        return
    ok, _chat_port, detail = ensure_chat_server_fn(session_name)
    if ok:
        query = active_session_records_query_fn()
        handler._send_json(
            200,
            {
                "ok": True,
                "session": session_name,
                "chat_url": f"/session/{url_quote(session_name, safe='')}/?follow=1",
                "session_record": query.records.get(session_name, {}),
            },
        )
    else:
        handler._send_json(500, {"ok": False, "error": detail})
