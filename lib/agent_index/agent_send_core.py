from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agent_interaction_core import normalize_sender_payload, pane_delivery_payload, pane_prompt_ready_from_text
from .agent_name_core import agent_base_name
from .agent_registry import ALL_AGENT_NAMES, number_alias_map
from .jsonl_append import append_jsonl_entry
from .session_path_core import default_tmux_socket_name, multiagent_panes_state_path

_SEND_PROMPT_WAIT_SECONDS = 6.0


class AgentSendError(RuntimeError):
    """Expected runtime error for user-facing CLI messages."""


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


def _state_file_value(path: Path, key: str) -> str:
    if not path.is_file():
        return ""
    needle = f"{key}="
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.rstrip("\n")
                if line.startswith(needle):
                    return line[len(needle) :]
    except Exception:
        return ""
    return ""


def _symlink_target_abs(path: Path) -> str:
    target = os.readlink(path)
    if os.path.isabs(target):
        return os.path.abspath(target)
    return os.path.abspath(path.parent / target)


def ensure_session_index_mirror(canonical_path: Path, mirror_base: Path, session_name: str) -> None:
    if not session_name:
        return

    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_abs = os.path.abspath(canonical_path)

    if canonical_path.is_symlink():
        try:
            if _symlink_target_abs(canonical_path) == canonical_abs:
                canonical_path.unlink()
        except Exception:
            try:
                canonical_path.unlink()
            except Exception:
                pass

    if not canonical_path.exists():
        backups = sorted(
            canonical_path.parent.glob(".agent-index.jsonl.backup.*"),
            key=lambda p: p.stat().st_mtime,
        )
        if backups:
            shutil.copy2(backups[-1], canonical_path)
        else:
            bak = canonical_path.parent / ".agent-index.jsonl.bak"
            if bak.exists():
                shutil.copy2(bak, canonical_path)
            else:
                canonical_path.touch()

    mirror_path = mirror_base / session_name / ".agent-index.jsonl"
    mirror_abs = os.path.abspath(mirror_path)
    if mirror_abs == canonical_abs:
        return
    try:
        if canonical_path.parent.resolve() == mirror_base.resolve():
            return
    except Exception:
        pass

    mirror_path.parent.mkdir(parents=True, exist_ok=True)

    if mirror_path.exists() and not mirror_path.is_symlink():
        canonical_seen_ids: set[str] = set()
        canonical_seen_raw: set[str] = set()
        with canonical_path.open("a+", encoding="utf-8") as canonical:
            fcntl.flock(canonical.fileno(), fcntl.LOCK_EX)
            try:
                canonical.seek(0)
                for raw in canonical.read().splitlines():
                    line = raw.strip()
                    if not line:
                        continue
                    canonical_seen_raw.add(line)
                    try:
                        msg_id = str((json.loads(line) or {}).get("msg_id") or "").strip()
                    except Exception:
                        msg_id = ""
                    if msg_id:
                        canonical_seen_ids.add(msg_id)

                merged: list[str] = []
                for raw in mirror_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except Exception:
                        if line in canonical_seen_raw:
                            continue
                        canonical_seen_raw.add(line)
                        merged.append(line)
                        continue

                    msg_id = str((item or {}).get("msg_id") or "").strip()
                    if msg_id:
                        if msg_id in canonical_seen_ids:
                            continue
                        canonical_seen_ids.add(msg_id)
                    elif line in canonical_seen_raw:
                        continue

                    canonical_seen_raw.add(line)
                    merged.append(line)

                if merged:
                    canonical.seek(0, os.SEEK_END)
                    for line in merged:
                        canonical.write(line + "\n")
                    canonical.flush()
            finally:
                fcntl.flock(canonical.fileno(), fcntl.LOCK_UN)

        backup = mirror_path.with_name(f"{mirror_path.name}.backup.{int(os.path.getmtime(mirror_path))}")
        try:
            shutil.move(str(mirror_path), str(backup))
        except Exception:
            try:
                mirror_path.unlink()
            except Exception:
                pass
    elif mirror_path.is_symlink():
        try:
            current = _symlink_target_abs(mirror_path)
            if current == canonical_abs:
                return
            mirror_path.unlink()
        except Exception:
            try:
                mirror_path.unlink()
            except Exception:
                pass

    if not mirror_path.exists():
        try:
            mirror_path.symlink_to(canonical_path)
        except Exception:
            # Best effort: canonical log is still valid even if mirror cannot be created.
            pass


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

    def session_log_dir_value(self, session_name: str) -> str:
        return self.tmux_env(session_name, "MULTIAGENT_LOG_DIR")

    def session_index_path_value(self, session_name: str) -> str:
        return self.tmux_env(session_name, "MULTIAGENT_INDEX_PATH")

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

        hinted_session_name = self.env.get("MULTIAGENT_SESSION") or "default"
        state_file = multiagent_panes_state_path(self.tmux_socket_name, hinted_session_name)
        hint_session = _state_file_value(state_file, "MULTIAGENT_SESSION")
        if hint_session:
            result = self.tmux.run(["has-session", "-t", hint_session])
            if result.returncode == 0:
                return hint_session

        raise AgentSendError("No active multiagent session found for this workspace.")

    def resolve_pane(self, session_name: str, key: str) -> str:
        value = self.tmux_env(session_name, key)
        if value:
            return value
        state_file = multiagent_panes_state_path(self.tmux_socket_name, session_name)
        state_session = _state_file_value(state_file, "MULTIAGENT_SESSION")
        if state_session == session_name:
            return _state_file_value(state_file, key)
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
        index_path_raw = (self.env.get("MULTIAGENT_INDEX_PATH") or "").strip()
        if not index_path_raw and session_name:
            index_path_raw = self.session_index_path_value(session_name).strip()
        if not index_path_raw and session_name:
            index_path_raw = str(self.repo_root / "logs" / session_name / ".agent-index.jsonl")

        if index_path_raw:
            index_path = Path(index_path_raw)
            index_path.parent.mkdir(parents=True, exist_ok=True)

            mirror_base = (self.env.get("MULTIAGENT_LOG_DIR") or "").strip()
            if not mirror_base and session_name:
                mirror_base = self.session_log_dir_value(session_name).strip()
            if not mirror_base:
                workspace = (self.env.get("MULTIAGENT_WORKSPACE") or self.session_workspace_value(session_name)).strip()
                if workspace:
                    mirror_base = str(Path(workspace) / "logs")
            if mirror_base:
                ensure_session_index_mirror(index_path, Path(mirror_base), session_name)
            if not index_path.exists():
                index_path.touch()
            return index_path

        default_path = self.repo_root / "logs" / "default" / ".agent-index.jsonl"
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

    def _pane_prompt_ready(self, pane_id: str, agent_name: str) -> bool:
        base = self._agent_base_name(agent_name)
        if base not in {"claude", "codex", "gemini", "qwen", "cursor"}:
            return True
        result = self.tmux.run(["capture-pane", "-p", "-t", pane_id, "-S", "-40"])
        if result.returncode != 0:
            return False
        return pane_prompt_ready_from_text(agent_name, result.stdout or "")

    def _pane_has_escape_cancel_prompt(self, pane_id: str, agent_name: str) -> bool:
        if self._agent_base_name(agent_name) != "claude":
            return False
        result = self.tmux.run(["capture-pane", "-p", "-t", pane_id, "-S", "-40"])
        if result.returncode != 0:
            return False
        text = (result.stdout or "").replace("\u00a0", " ")
        return "Esc to cancel" in text and "What do you want to do?" in text

    def _pane_has_claude_trust_prompt(self, pane_id: str, agent_name: str) -> bool:
        if self._agent_base_name(agent_name) != "claude":
            return False
        result = self.tmux.run(["capture-pane", "-p", "-t", pane_id, "-S", "-60"])
        if result.returncode != 0:
            return False
        text = (result.stdout or "").replace("\u00a0", " ")
        return (
            "Quick safety check" in text
            and "Yes, I trust this folder" in text
            and "Enter to confirm" in text
        )

    def _pane_has_gemini_trust_prompt(self, pane_id: str, agent_name: str) -> bool:
        if self._agent_base_name(agent_name) != "gemini":
            return False
        result = self.tmux.run(["capture-pane", "-p", "-t", pane_id, "-S", "-80"])
        if result.returncode != 0:
            return False
        text = (result.stdout or "").replace("\u00a0", " ")
        return "Do you trust the files in this folder?" in text and "Trust folder" in text

    def _pane_has_cursor_trust_prompt(self, pane_id: str, agent_name: str) -> bool:
        if self._agent_base_name(agent_name) != "cursor":
            return False
        result = self.tmux.run(["capture-pane", "-p", "-t", pane_id, "-S", "-80"])
        if result.returncode != 0:
            return False
        text = (result.stdout or "").replace("\u00a0", " ")
        return "Workspace Trust Required" in text and "Trust this workspace" in text

    def _wait_for_pane_prompt(self, pane_id: str, agent_name: str) -> bool:
        base = self._agent_base_name(agent_name)
        if base not in {"claude", "codex", "gemini", "qwen", "cursor"}:
            return True
        deadline = time.time() + _SEND_PROMPT_WAIT_SECONDS
        while time.time() < deadline:
            if self._pane_prompt_ready(pane_id, agent_name):
                return True
            if base == "claude" and self._pane_has_claude_trust_prompt(pane_id, agent_name):
                self.tmux.run(["send-keys", "-t", pane_id, "Enter"])
                time.sleep(0.3)
                continue
            if base == "claude" and self._pane_has_escape_cancel_prompt(pane_id, agent_name):
                self.tmux.run(["send-keys", "-t", pane_id, "Escape"])
                time.sleep(0.2)
                continue
            if base == "gemini" and self._pane_has_gemini_trust_prompt(pane_id, agent_name):
                self.tmux.run(["send-keys", "-t", pane_id, "Enter"])
                time.sleep(0.3)
                continue
            if base == "cursor" and self._pane_has_cursor_trust_prompt(pane_id, agent_name):
                self.tmux.run(["send-keys", "-t", pane_id, "a"])
                time.sleep(0.3)
                continue
            time.sleep(0.2)
        return False

    def send_to_pane(self, pane_id: str, payload: str, agent_name: str = "") -> bool:
        if not pane_id:
            return False
        if not self._wait_for_pane_prompt(pane_id, agent_name):
            return False
        if self.tmux.run(["send-keys", "-t", pane_id, "-l", payload]).returncode != 0:
            return False
        delay_raw = (self.env.get("AGENT_SEND_PASTE_DELAY") or "").strip()
        try:
            delay = float(delay_raw) if delay_raw else 0.3
        except ValueError:
            delay = 0.3
        time.sleep(max(0.0, delay))
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
        for target in delivery_targets:
            if self.send_to_pane(
                target.pane_id,
                pane_delivery_payload(target.agent_name, delivery_payload),
                target.agent_name,
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
