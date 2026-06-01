from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from message_delivery.interaction import normalize_sender_payload, pane_delivery_payload
from backend_core.agents.names import agent_base_name
from backend_core.agents.registry import ALL_AGENT_NAMES, number_alias_map
from backend_core.access.files import append_jsonl_entry
import hashlib as _hashlib

from message_delivery.paste_timing import delivery_paste_delay_seconds

def default_tmux_socket_name(repo_root) -> str:
    return "agent-window"


def _safe_session_name(s: str) -> str:
    return (s or "default").replace("/", "_")


def session_topology_lock_path(tmux_socket: str, session_name: str) -> Path:
    safe = _safe_session_name(session_name)
    sock = tmux_socket or "default"
    if sock.startswith("/"):
        digest = _hashlib.sha1(f"{sock}|{safe}".encode()).hexdigest()[:20]
    else:
        digest = _hashlib.sha1(f"{sock}|{safe}".encode()).hexdigest()[:20]
    run_dir = Path(os.environ.get("AGENT_WINDOW_RUN_DIR") or (Path.home() / ".agent-window" / "run"))
    return run_dir / "topology-locks" / f"{digest}.lock"


from backend_core.access.settings import session_log_path


class AgentSendError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeliveryTarget:
    agent_name: str
    pane_id: str


def tmux_socket_from_env(repo_root: Path | str, env: dict[str, str]) -> str:
    explicit = (env.get("MULTIAGENT_TMUX_SOCKET") or "").strip()
    if explicit:
        return explicit
    tmux_env = (env.get("TMUX") or "").strip()
    if tmux_env:
        socket_path = tmux_env.split(",", 1)[0]
        if re.match(r"^/(private/)?tmp/tmux-[^/]+/.+$", socket_path):
            return Path(socket_path).name
        return socket_path
    return default_tmux_socket_name(repo_root)

class TmuxClient:
    def __init__(self, tmux_socket_name: str, env: dict[str, str]):
        self.tmux_socket_name = tmux_socket_name
        self.env = env

    def _prefix(self) -> list[str]:
        if "/" in self.tmux_socket_name:
            return ["tmux", "-S", self.tmux_socket_name]
        return ["tmux", "-L", self.tmux_socket_name]

    def run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*self._prefix(), *args],
            capture_output=True,
            text=True,
            check=False,
            env=self.env,
        )


class AgentSendRuntime:
    def __init__(
        self,
        *,
        repo_root: Path | str,
        script_dir: Path | str,
        env: dict[str, str] | None = None,
        cwd: Path | str | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.script_dir = Path(script_dir).resolve()
        self.env = dict(os.environ if env is None else env)
        self.cwd = Path(cwd or os.getcwd()).resolve()
        self.tmux_socket_name = tmux_socket_from_env(self.repo_root, self.env)
        self.tmux = TmuxClient(self.tmux_socket_name, self.env)
        self.all_agents = list(ALL_AGENT_NAMES)
        self.number_aliases = number_alias_map()

    def list_sessions(self) -> list[str]:
        result = self.tmux.run(["list-sessions", "-F", "#S"])
        if result.returncode != 0:
            return []
        return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]

    def tmux_env(self, session_name: str, key: str) -> str:
        result = self.tmux.run(["show-environment", "-t", session_name, key])
        line = (result.stdout or "").strip()
        if result.returncode == 0 and "=" in line:
            return line.split("=", 1)[1]
        return ""

    def session_workspace_value(self, session_name: str) -> str:
        return self.tmux_env(session_name, "MULTIAGENT_WORKSPACE")

    def session_bin_dir_value(self, session_name: str) -> str:
        return self.tmux_env(session_name, "MULTIAGENT_BIN_DIR")

    def matching_repo_sessions(self) -> list[str]:
        matched: list[str] = []
        for session in self.list_sessions():
            bin_dir = self.session_bin_dir_value(session).strip()
            if not bin_dir:
                continue
            try:
                resolved = str(Path(bin_dir).resolve())
            except Exception:
                resolved = bin_dir
            if resolved == str(self.script_dir):
                matched.append(session)
        return matched

    def resolve_session_name(self, explicit_session: str = "") -> str:
        if explicit_session:
            return explicit_session

        if self.env.get("TMUX"):
            result = self.tmux.run(["display-message", "-p", "#{session_name}"])
            session_name = (result.stdout or "").strip()
            if session_name:
                return session_name

        matched_workspace_sessions = [
            session for session in self.list_sessions() if self.session_workspace_value(session) == str(self.cwd)
        ]
        if len(matched_workspace_sessions) == 1:
            return matched_workspace_sessions[0]
        if len(matched_workspace_sessions) > 1:
            raise AgentSendError("Multiple sessions exist for this workspace; run from inside tmux or set MULTIAGENT_SESSION.")

        matched_repo_sessions = self.matching_repo_sessions()
        if len(matched_repo_sessions) == 1:
            return matched_repo_sessions[0]
        if len(matched_repo_sessions) > 1:
            raise AgentSendError("Multiple active multiagent sessions exist; set MULTIAGENT_SESSION or pass --session.")

        raise AgentSendError("No active multiagent session found for this workspace.")

    def resolve_pane(self, session_name: str, key: str) -> str:
        value = self.tmux_env(session_name, key)
        if value:
            return value
        return ""

    def resolve_agent_name(self, token: str) -> str | None:
        lower = (token or "").strip().lower()
        if not lower:
            return None
        if lower.isdigit():
            alias = self.number_aliases.get(int(lower))
            if alias:
                return alias
        base = agent_base_name(lower)
        if base in self.all_agents:
            return lower
        return None

    def resolve_self_agent(self, session_name: str) -> str | None:
        current_pane = (self.env.get("TMUX_PANE") or "").strip()
        if not current_pane:
            return None

        agents_str = self.tmux_env(session_name, "MULTIAGENT_AGENTS")
        if agents_str:
            for instance in [x.strip() for x in agents_str.split(",") if x.strip()]:
                upper = instance.upper().replace("-", "_")
                pane = self.resolve_pane(session_name, f"MULTIAGENT_PANE_{upper}")
                if pane == current_pane:
                    return instance

        for agent in self.all_agents:
            pane = self.resolve_pane(session_name, f"MULTIAGENT_PANE_{agent.upper()}")
            if pane == current_pane:
                return agent
        return None

    def current_pane_role(self, session_name: str) -> str | None:
        current_pane = (self.env.get("TMUX_PANE") or "").strip()
        if not current_pane:
            return None

        user_panes = self.resolve_pane(session_name, "MULTIAGENT_PANES_USER")
        if user_panes:
            if current_pane in [x.strip() for x in user_panes.split(",") if x.strip()]:
                return "user"
        else:
            user_pane = self.resolve_pane(session_name, "MULTIAGENT_PANE_USER")
            if user_pane == current_pane:
                return "user"

        return self.resolve_self_agent(session_name)

    @staticmethod
    def normalize_payload(sender: str, payload: str) -> str:
        return normalize_sender_payload(sender, payload)

    def resolve_session_index_path(self, session_name: str) -> Path:
        target_session = session_name or "default"
        default_path = session_log_path(target_session)
        default_path.parent.mkdir(parents=True, exist_ok=True)
        if not default_path.exists():
            default_path.touch()
        return default_path

    def _build_delivery_targets(self, session_name: str, target_spec: str, sender_role: str | None) -> list[DeliveryTarget]:
        targets: list[DeliveryTarget] = []
        panes_by_target: dict[str, str] = {}

        def queue(agent_name: str, pane_id: str) -> None:
            if not agent_name or not pane_id:
                return
            panes_by_target[agent_name] = pane_id

        for raw_target in [item.strip() for item in (target_spec or "").split(",") if item.strip()]:
            resolved_name = self.resolve_agent_name(raw_target)
            if resolved_name and resolved_name != "user":
                base_name = agent_base_name(resolved_name)
                if re.search(r"-\d+$", resolved_name):
                    upper = resolved_name.upper().replace("-", "_")
                    pane = self.resolve_pane(session_name, f"MULTIAGENT_PANE_{upper}")
                    if not pane:
                        raise AgentSendError(f"Target pane not found: {resolved_name}")
                    queue(resolved_name, pane)
                    continue

                agents_str = self.tmux_env(session_name, "MULTIAGENT_AGENTS")
                found = False
                if agents_str:
                    for instance in [x.strip() for x in agents_str.split(",") if x.strip()]:
                        if instance == base_name or instance.startswith(f"{base_name}-"):
                            pane = self.resolve_pane(session_name, f"MULTIAGENT_PANE_{instance.upper().replace('-', '_')}")
                            if pane:
                                queue(instance, pane)
                                found = True
                if not found:
                    pane = self.resolve_pane(session_name, f"MULTIAGENT_PANE_{base_name.upper()}")
                    if pane:
                        queue(base_name, pane)
                        found = True
                if not found:
                    raise AgentSendError(f"Target pane not found: {raw_target}")
                continue

            lower_target = raw_target.lower()
            if lower_target == "user":
                raise AgentSendError(
                    'agent-send: target "user" has been removed.\n\n'
                    "Respond to humans in your normal assistant output (native event logs are indexed automatically).\n"
                    "Use agent-send only for agent-to-agent communication targets."
                )
            if lower_target == "others":
                if not sender_role:
                    raise AgentSendError("Cannot resolve current sender for target: others")
                agents_str = self.tmux_env(session_name, "MULTIAGENT_AGENTS")
                if agents_str:
                    for instance in [x.strip() for x in agents_str.split(",") if x.strip()]:
                        if sender_role != "user" and instance == sender_role:
                            continue
                        pane = self.resolve_pane(session_name, f"MULTIAGENT_PANE_{instance.upper().replace('-', '_')}")
                        if pane:
                            queue(instance, pane)
                else:
                    for agent in self.all_agents:
                        if sender_role != "user" and agent == sender_role:
                            continue
                        pane = self.resolve_pane(session_name, f"MULTIAGENT_PANE_{agent.upper()}")
                        if pane:
                            queue(agent, pane)
                continue

            raise AgentSendError(f"Unknown target: {raw_target}")

        for name, pane in panes_by_target.items():
            targets.append(DeliveryTarget(agent_name=name, pane_id=pane))
        return targets

    @staticmethod
    def _agent_base_name(agent_name: str) -> str:
        return agent_base_name(agent_name)

    def _session_attached_count(self, session_name: str) -> int | None:
        if not session_name:
            return None
        result = self.tmux.run(["display-message", "-p", "-t", session_name, "#{session_attached}"])
        if result.returncode != 0:
            return None
        raw = str(result.stdout or "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def send_to_pane(
        self,
        pane_id: str,
        payload: str,
        agent_name: str = "",
        *,
        session_name: str = "",
        session_attached_count: int | None = None,
    ) -> bool:
        if not pane_id:
            return False
        if self.tmux.run(["send-keys", "-t", pane_id, "-l", "--", payload]).returncode != 0:
            return False
        attached_count = session_attached_count
        if attached_count is None:
            attached_count = self._session_attached_count(session_name)
        time.sleep(
            delivery_paste_delay_seconds(
                payload,
                env=self.env,
                session_attached_count=attached_count,
            )
        )
        if self.tmux.run(["send-keys", "-t", pane_id, "", "Enter"]).returncode != 0:
            return False
        return True

    def _reply_preview_for(self, index_path: Path, reply_to: str) -> str:
        if not reply_to:
            return ""
        try:
            with index_path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if entry.get("msg_id") != reply_to:
                        continue
                    message = str(entry.get("message") or "")
                    if "[From:" in message:
                        idx = message.find("]")
                        if idx != -1:
                            message = message[idx + 1 :].strip()
                    preview = message[:80].replace("\n", " ")
                    return f"{entry.get('sender', 'unknown')}: {preview}"
        except Exception:
            return ""
        return ""

    def append_index_entry(
        self,
        *,
        session_name: str,
        sender: str,
        targets: list[str],
        payload: str,
        msg_id: str,
        reply_to: str = "",
    ) -> None:
        index_path = self.resolve_session_index_path(session_name)
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "session": session_name,
            "sender": sender,
            "targets": targets,
            "message": payload,
            "msg_id": msg_id,
        }
        if reply_to:
            entry["reply_to"] = reply_to
            preview = self._reply_preview_for(index_path, reply_to)
            if preview:
                entry["reply_preview"] = preview
        append_jsonl_entry(index_path, entry)

    def send_message(
        self,
        *,
        target_spec: str,
        payload: str,
        explicit_session: str = "",
        reply_to: str = "",
    ) -> bool:
        session_name = self.resolve_session_name(explicit_session)
        sender_role = self.current_pane_role(session_name) or self.env.get("MULTIAGENT_AGENT_NAME") or "user"
        delivery_payload = self.normalize_payload(sender_role, payload)
        delivery_targets = self._build_delivery_targets(session_name, target_spec, sender_role)
        if not delivery_targets:
            raise AgentSendError("No target panes resolved.")

        successful_targets: list[str] = []
        failed_any = False
        attached_count = self._session_attached_count(session_name)
        for target in delivery_targets:
            if self.send_to_pane(
                target.pane_id,
                pane_delivery_payload(target.agent_name, delivery_payload),
                target.agent_name,
                session_name=session_name,
                session_attached_count=attached_count,
            ):
                if target.agent_name not in successful_targets:
                    successful_targets.append(target.agent_name)
            else:
                failed_any = True
                print(f"Failed to deliver to: {target.agent_name}", file=sys.stderr)

        if not successful_targets:
            raise AgentSendError("Message delivery failed for all targets.")

        msg_id = uuid.uuid4().hex[:12]
        self.append_index_entry(
            session_name=session_name,
            sender=sender_role,
            targets=successful_targets,
            payload=delivery_payload,
            msg_id=msg_id,
            reply_to=reply_to,
        )
        return not failed_any
