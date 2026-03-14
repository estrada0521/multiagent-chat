from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
import uuid
from datetime import datetime as dt_datetime
from pathlib import Path

from .hub_core import HUB_SETTINGS_DEFAULTS


class ChatRuntime:
    def __init__(
        self,
        *,
        index_path: Path | str,
        limit: int,
        filter_agent: str,
        session_name: str,
        follow_mode: bool,
        port: int,
        agent_send_path: Path | str,
        workspace: str,
        log_dir: str,
        targets: list[str],
        tmux_socket: str,
        hub_port: int,
        repo_root: Path | str,
        session_is_active: bool,
    ):
        self.index_path = Path(index_path)
        self.commit_state_path = self.index_path.parent / ".agent-index-commit-state.json"
        self.limit = int(limit)
        self.filter_agent = (filter_agent or "").strip().lower()
        self.session_name = session_name
        self.follow_mode = bool(follow_mode)
        self.port = int(port)
        self.agent_send_path = str(agent_send_path)
        self.workspace = workspace
        self.log_dir = log_dir
        self.targets = list(targets or [])
        self.tmux_socket = tmux_socket
        self.hub_port = int(hub_port)
        self.repo_root = Path(repo_root).resolve()
        self.session_is_active = bool(session_is_active)
        self.server_instance = uuid.uuid4().hex
        self.chat_settings_path = self.repo_root / "logs" / ".hub-settings.json"
        self.thinking_stats_path = self.repo_root / "logs" / ".thinking-time.json"
        self.tmux_prefix = ["tmux"]
        if self.tmux_socket:
            self.tmux_prefix.extend(["-L", self.tmux_socket])
        self._caffeinate_proc = None
        self._pane_snapshots = {}
        self._pane_last_change = {}
        self.running_grace_seconds = 2.0

    def load_chat_settings(self):
        settings = dict(HUB_SETTINGS_DEFAULTS)
        if self.chat_settings_path.is_file():
            try:
                raw = json.loads(self.chat_settings_path.read_text(encoding="utf-8"))
            except Exception:
                raw = {}
            if isinstance(raw, dict):
                theme = str(raw.get("theme") or settings["theme"]).strip().lower()
                if theme in {"default"}:
                    settings["theme"] = theme
                agent_font_mode = str(raw.get("agent_font_mode") or settings["agent_font_mode"]).strip().lower()
                if agent_font_mode in {"serif", "gothic"}:
                    settings["agent_font_mode"] = agent_font_mode
                for key, default in (("mobile_message_limit", 50), ("desktop_message_limit", 500)):
                    try:
                        value = int(raw.get(key, settings[key]))
                    except Exception:
                        value = default
                    settings[key] = max(10, min(self.limit if self.limit > 0 else 500, value))
        return settings

    @staticmethod
    def chat_agent_font_mode_inline_style(font_mode):
        if str(font_mode).strip().lower() != "gothic":
            return ""
        return """
    .message.claude .md-body,
    .message.codex .md-body,
    .message.gemini .md-body,
    .message.copilot .md-body {
      font-family: "anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", sans-serif !important;
      font-size: 16px !important;
      line-height: 22px !important;
      font-style: normal !important;
      font-weight: 360 !important;
      letter-spacing: -0.01em !important;
      -webkit-font-smoothing: antialiased !important;
      -moz-osx-font-smoothing: grayscale !important;
      font-synthesis-weight: none !important;
      font-optical-sizing: auto !important;
      font-variation-settings: "wght" 360, "opsz" 16 !important;
    }
    .message.claude .md-body p,
    .message.claude .md-body li,
    .message.claude .md-body h1,
    .message.claude .md-body h2,
    .message.claude .md-body h3,
    .message.claude .md-body h4,
    .message.claude .md-body blockquote,
    .message.codex .md-body p,
    .message.codex .md-body li,
    .message.codex .md-body h1,
    .message.codex .md-body h2,
    .message.codex .md-body h3,
    .message.codex .md-body h4,
    .message.codex .md-body blockquote,
    .message.gemini .md-body p,
    .message.gemini .md-body li,
    .message.gemini .md-body h1,
    .message.gemini .md-body h2,
    .message.gemini .md-body h3,
    .message.gemini .md-body h4,
    .message.gemini .md-body blockquote,
    .message.copilot .md-body p,
    .message.copilot .md-body li,
    .message.copilot .md-body h1,
    .message.copilot .md-body h2,
    .message.copilot .md-body h3,
    .message.copilot .md-body h4,
    .message.copilot .md-body blockquote {
      font-family: inherit !important;
      font-weight: 360 !important;
      font-variation-settings: "wght" 360, "opsz" 16 !important;
    }
    .message.claude .md-body li,
    .message.codex .md-body li,
    .message.gemini .md-body li,
    .message.copilot .md-body li {
      line-height: 22px !important;
    }
    """

    def persist_thinking_totals(self, totals):
        agents = {}
        for agent in ("claude", "codex", "gemini", "copilot"):
            try:
                value = int(totals.get(agent, 0) or 0)
            except Exception:
                value = 0
            agents[agent] = max(0, value)
        payload = {}
        if self.thinking_stats_path.is_file():
            try:
                payload = json.loads(self.thinking_stats_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            payload = {}
        sessions = payload.get("sessions")
        if not isinstance(sessions, dict):
            sessions = {}
        sessions[self.session_name] = {
            "workspace": self.workspace,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "agents": agents,
        }
        payload["sessions"] = sessions
        self.thinking_stats_path.parent.mkdir(parents=True, exist_ok=True)
        self.thinking_stats_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_system_entry(self, message, **extra):
        entry = {
            "timestamp": dt_datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session": self.session_name,
            "sender": "system",
            "targets": [],
            "message": message,
            "msg_id": uuid.uuid4().hex[:12],
        }
        entry.update(extra)
        with self.index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def read_commit_state(self):
        if not self.commit_state_path.exists():
            return {}
        try:
            return json.loads(self.commit_state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def write_commit_state(self, commit):
        try:
            self.commit_state_path.write_text(
                json.dumps(
                    {
                        "last_commit_hash": commit["hash"],
                        "last_commit_short": commit["short"],
                        "last_commit_subject": commit["subject"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def current_git_commit(self):
        try:
            result = subprocess.run(
                ["git", "-C", self.workspace, "log", "-1", "--format=%H%x1f%h%x1f%s"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except Exception:
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

    def git_commits_since(self, base_hash):
        try:
            result = subprocess.run(
                ["git", "-C", self.workspace, "log", "--reverse", "--format=%H%x1f%h%x1f%s", f"{base_hash}..HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except Exception:
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

    def ensure_commit_announcements(self):
        current = self.current_git_commit()
        if not current:
            return
        state = self.read_commit_state()
        last_hash = state.get("last_commit_hash", "")
        if not last_hash:
            self.write_commit_state(current)
            return
        if last_hash == current["hash"]:
            return
        commits = self.git_commits_since(last_hash)
        if commits is None:
            commits = [current]
        if not commits:
            self.write_commit_state(current)
            return
        for commit in commits:
            self.append_system_entry(
                f"Commit: {commit['short']} {commit['subject']}",
                kind="git-commit",
                commit_hash=commit["hash"],
                commit_short=commit["short"],
            )
        self.write_commit_state(commits[-1])

    def matches(self, entry):
        if not self.filter_agent:
            return True
        if entry.get("sender", "").lower() == self.filter_agent:
            return True
        return any(t.lower() == self.filter_agent for t in entry.get("targets", []))

    def read_entries(self, limit_override=None):
        if not self.index_path.exists():
            return []
        entries = []
        with self.index_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if self.matches(entry):
                    entries.append(entry)
        l = limit_override if limit_override is not None else self.limit
        if l and l > 0:
            return entries[-l:]
        return entries

    def payload(self, limit_override=None):
        self.ensure_commit_announcements()
        return json.dumps(
            {
                "server_instance": self.server_instance,
                "session": self.session_name,
                "filter": self.filter_agent or "all",
                "follow": self.follow_mode,
                "active": self.session_is_active,
                "source": str(self.index_path),
                "targets": self.targets,
                "entries": self.read_entries(limit_override=limit_override),
            },
            ensure_ascii=True,
        ).encode("utf-8")

    def caffeinate_status(self):
        if self._caffeinate_proc is not None and self._caffeinate_proc.poll() is None:
            return {"active": True}
        self._caffeinate_proc = None
        try:
            result = subprocess.run(["pgrep", "-x", "caffeinate"], capture_output=True)
            if result.returncode == 0:
                return {"active": True}
        except Exception:
            pass
        return {"active": False}

    def caffeinate_toggle(self):
        if self.caffeinate_status()["active"]:
            if self._caffeinate_proc is not None:
                self._caffeinate_proc.terminate()
                self._caffeinate_proc = None
            else:
                subprocess.run(["killall", "caffeinate"], capture_output=True, check=False)
            return {"active": False}
        self._caffeinate_proc = subprocess.Popen(["caffeinate", "-s"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"active": True}

    def auto_mode_status(self):
        try:
            result = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name, "MULTIAGENT_AUTO_MODE"],
                capture_output=True,
                text=True,
                check=False,
            )
            active = result.stdout.strip() == "MULTIAGENT_AUTO_MODE=1"
        except Exception:
            active = False
        approval_file = f"/tmp/multiagent_auto_approved_{self.session_name}"
        try:
            last_approval = os.path.getmtime(approval_file)
            last_approval_agent = Path(approval_file).read_text().strip().lower()
        except OSError:
            last_approval = 0
            last_approval_agent = ""
        return {"active": active, "last_approval": last_approval, "last_approval_agent": last_approval_agent}

    def pane_id_for_agent(self, agent_name):
        pane_var = f"MULTIAGENT_PANE_{agent_name.upper()}"
        res = subprocess.run(
            [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip().split("=", 1)[-1] if "=" in res.stdout else ""

    def agent_launch_cmd(self, agent_name):
        bin_dir = Path(self.agent_send_path).parent
        env_parts = [
            f"PATH={shlex.quote(str(bin_dir))}:$PATH",
            f"MULTIAGENT_SESSION={shlex.quote(self.session_name)}",
            f"MULTIAGENT_BIN_DIR={shlex.quote(str(bin_dir))}",
            f"MULTIAGENT_WORKSPACE={shlex.quote(self.workspace)}",
            f"MULTIAGENT_TMUX_SOCKET={shlex.quote(self.tmux_socket)}",
            f"MULTIAGENT_AGENT_NAME={shlex.quote(agent_name)}",
        ]
        env_exports = "export " + " ".join(env_parts)
        if agent_name == "claude":
            return f"{env_exports}; exec env -u CLAUDECODE claude"
        if agent_name == "copilot":
            return f"{env_exports}; export COPILOT_ALLOW_ALL=1; exec copilot --allow-all-tools"
        return f"{env_exports}; exec {shlex.quote(agent_name)}"

    def agent_resume_cmd(self, agent_name):
        bin_dir = Path(self.agent_send_path).parent
        env_parts = [
            f"PATH={shlex.quote(str(bin_dir))}:$PATH",
            f"MULTIAGENT_SESSION={shlex.quote(self.session_name)}",
            f"MULTIAGENT_BIN_DIR={shlex.quote(str(bin_dir))}",
            f"MULTIAGENT_WORKSPACE={shlex.quote(self.workspace)}",
            f"MULTIAGENT_TMUX_SOCKET={shlex.quote(self.tmux_socket)}",
            f"MULTIAGENT_AGENT_NAME={shlex.quote(agent_name)}",
        ]
        env_exports = "export " + " ".join(env_parts)
        if agent_name == "claude":
            return f"{env_exports}; exec env -u CLAUDECODE claude --continue"
        if agent_name == "codex":
            return f"{env_exports}; exec codex resume --last"
        if agent_name == "gemini":
            return f"{env_exports}; exec gemini --resume latest"
        if agent_name == "copilot":
            return f"{env_exports}; export COPILOT_ALLOW_ALL=1; exec copilot --continue --allow-all-tools"
        return self.agent_launch_cmd(agent_name)

    def restart_agent_pane(self, agent_name):
        pane_id = self.pane_id_for_agent(agent_name)
        if not pane_id:
            return False, f"pane not found for {agent_name}"
        respawn_res = subprocess.run(
            [*self.tmux_prefix, "respawn-pane", "-k", "-t", pane_id, "-c", self.workspace, self.agent_launch_cmd(agent_name)],
            capture_output=True,
            text=True,
            check=False,
        )
        if respawn_res.returncode != 0:
            detail = (respawn_res.stderr or respawn_res.stdout or "").strip() or f"failed to restart {agent_name}"
            return False, detail
        subprocess.run([*self.tmux_prefix, "select-pane", "-t", pane_id, "-T", agent_name], capture_output=True, check=False)
        return True, pane_id

    def resume_agent_pane(self, agent_name):
        pane_id = self.pane_id_for_agent(agent_name)
        if not pane_id:
            return False, f"pane not found for {agent_name}"
        respawn_res = subprocess.run(
            [*self.tmux_prefix, "respawn-pane", "-k", "-t", pane_id, "-c", self.workspace, self.agent_resume_cmd(agent_name)],
            capture_output=True,
            text=True,
            check=False,
        )
        if respawn_res.returncode != 0:
            detail = (respawn_res.stderr or respawn_res.stdout or "").strip() or f"failed to resume {agent_name}"
            return False, detail
        subprocess.run([*self.tmux_prefix, "select-pane", "-t", pane_id, "-T", agent_name], capture_output=True, check=False)
        return True, pane_id

    def send_message(self, target, message, reply_to="", silent=False, raw=False):
        target = (target or "").strip()
        message = (message or "").strip()
        reply_to = (reply_to or "").strip()
        if not message:
            return 400, {"ok": False, "error": "message is required"}
        env = os.environ.copy()
        env["MULTIAGENT_SESSION"] = self.session_name
        env["MULTIAGENT_WORKSPACE"] = self.workspace
        env["MULTIAGENT_LOG_DIR"] = self.log_dir
        env["MULTIAGENT_BIN_DIR"] = str(Path(self.agent_send_path).parent)
        env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
        env.pop("TMUX", None)
        env.pop("TMUX_PANE", None)
        env["MULTIAGENT_AGENT_NAME"] = "user"
        bin_dir = Path(self.agent_send_path).parent
        if message in {"brief", "kill", "save", "interrupt", "ctrlc", "enter", "restart", "resume"}:
            if message in {"interrupt", "ctrlc", "enter", "restart", "resume"}:
                if not target:
                    return 400, {"ok": False, "error": "target is required"}
                try:
                    for agent in [item.strip() for item in target.split(",") if item.strip()]:
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
                        tmux_key = {"interrupt": "Escape", "ctrlc": "C-c", "enter": "Enter"}[message]
                        subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, tmux_key], capture_output=True, check=False)
                except Exception as exc:
                    return 500, {"ok": False, "error": str(exc)}
                return 200, {"ok": True, "mode": message}
            command = [str(bin_dir / "multiagent"), message, "--session", self.session_name]
            if message == "brief" and target:
                command.extend(["--agent", target])
            try:
                if message == "brief":
                    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                    return 200, {"ok": True, "mode": message}
                result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
            except Exception as exc:
                return 500, {"ok": False, "error": str(exc)}
            if result.returncode != 0:
                return 400, {"ok": False, "error": (result.stderr or result.stdout or f"{message} failed").strip()}
            return 200, {"ok": True, "mode": message}
        if not target:
            return 400, {"ok": False, "error": "target is required"}
        if silent or raw:
            try:
                targets = [item.strip() for item in target.split(",") if item.strip()]
                if not targets:
                    return 400, {"ok": False, "error": "target is required"}
                for idx, agent in enumerate(targets):
                    pane_var = f"MULTIAGENT_PANE_{agent.upper()}"
                    res = subprocess.run(
                        [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    pane_id = res.stdout.strip().split("=", 1)[-1] if "=" in res.stdout else ""
                    if not pane_id:
                        return 400, {"ok": False, "error": f"pane not found for {agent}"}
                    buf_name = f"direct_{agent}_{os.getpid()}_{idx}"
                    subprocess.run(
                        [*self.tmux_prefix, "load-buffer", "-b", buf_name, "-"],
                        input=message + "\n",
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    subprocess.run([*self.tmux_prefix, "paste-buffer", "-b", buf_name, "-d", "-t", pane_id], capture_output=True, check=False)
                    time.sleep(0.3)
                    subprocess.run([*self.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"], capture_output=True, check=False)
            except Exception as exc:
                return 500, {"ok": False, "error": str(exc)}
            return 200, {"ok": True, "raw": bool(raw)}
        try:
            cmd = [self.agent_send_path]
            if reply_to:
                cmd.extend(["--reply", reply_to])
            cmd.extend(["--stdin", target])
            result = subprocess.run(cmd, input=message, capture_output=True, text=True, env=env, check=False)
        except Exception as exc:
            return 500, {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return 400, {"ok": False, "error": (result.stderr or result.stdout or "agent-send failed").strip()}
        return 200, {"ok": True}

    def agent_statuses(self):
        result = {}
        for agent in ["claude", "codex", "gemini", "copilot"]:
            pane_var = f"MULTIAGENT_PANE_{agent.upper()}"
            try:
                r = subprocess.run(
                    [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                line = r.stdout.strip()
                if r.returncode != 0 or "=" not in line:
                    result[agent] = "offline"
                    continue
                pane_id = line.split("=", 1)[1]
                dead = subprocess.run(
                    [*self.tmux_prefix, "display-message", "-p", "-t", pane_id, "#{pane_dead}"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                ).stdout.strip()
                if dead == "1":
                    result[agent] = "dead"
                    self._pane_snapshots.pop(pane_id, None)
                    self._pane_last_change.pop(pane_id, None)
                    continue
                content = subprocess.run(
                    [*self.tmux_prefix, "capture-pane", "-p", "-S", "-20", "-t", pane_id],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                ).stdout
                now = time.monotonic()
                prev = self._pane_snapshots.get(pane_id)
                self._pane_snapshots[pane_id] = content
                if prev is not None and content != prev:
                    self._pane_last_change[pane_id] = now
                    result[agent] = "running"
                else:
                    last_change = self._pane_last_change.get(pane_id, 0.0)
                    result[agent] = "running" if (now - last_change) < self.running_grace_seconds else "idle"
            except Exception:
                result[agent] = "offline"
        return result

    def trace_content(self, agent):
        pane_var = f"MULTIAGENT_PANE_{(agent or '').upper()}"
        content_str = ""
        try:
            r = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            line = r.stdout.strip()
            if r.returncode == 0 and "=" in line:
                pane_id = line.split("=", 1)[1]
                raw = subprocess.run(
                    [*self.tmux_prefix, "capture-pane", "-p", "-e", "-t", pane_id],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                ).stdout
                content_str = "\n".join(l.rstrip() for l in raw.splitlines())
            else:
                content_str = "Offline"
        except Exception as e:
            content_str = f"Error: {e}"
        return content_str
