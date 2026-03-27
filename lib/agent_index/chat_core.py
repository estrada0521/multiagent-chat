from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
import uuid
from datetime import datetime as dt_datetime
from pathlib import Path
import shutil
from urllib.parse import quote

from .agent_registry import AGENTS, ALL_AGENT_NAMES, generate_agent_message_selectors
from .instance_core import agents_from_tmux_env_output
from .instance_core import resolve_target_agents as resolve_target_agent_names
from .state_core import load_hub_settings as load_shared_hub_settings
from .state_core import load_session_thinking_totals as load_shared_session_thinking_totals

def _bh_agent_detail_selectors(prefix: str = "") -> str:
    """Generate .message.{agent} .md-body {p,li,h1..h4,blockquote} selectors."""
    subs = ["p", "li", "h1", "h2", "h3", "h4", "blockquote"]
    parts = []
    for name in ALL_AGENT_NAMES:
        for sub in subs:
            parts.append(f'    {prefix}.message.{name} .md-body {sub}')
    return ",\n".join(parts)
from .state_core import update_thinking_totals_from_statuses as update_shared_thinking_totals_from_statuses


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
        self.tmux_prefix = ["tmux"]
        if self.tmux_socket:
            if "/" in self.tmux_socket:
                self.tmux_prefix.extend(["-S", self.tmux_socket])
            else:
                self.tmux_prefix.extend(["-L", self.tmux_socket])
        self._caffeinate_proc = None
        self._pane_snapshots = {}
        self._pane_last_change = {}
        self.running_grace_seconds = 2.0
        self._caffeinate_args = ["caffeinate", "-s"]
        try:
            settings = self.load_chat_settings()
        except Exception:
            settings = {}
        if bool(settings.get("chat_awake", False)):
            self.ensure_caffeinate_active()

    def load_chat_settings(self):
        cap = self.limit if self.limit > 0 else 500
        return load_shared_hub_settings(self.repo_root, message_limit_cap=cap)

    @staticmethod
    def _font_family_stack(selection: str, role: str) -> str:
        value = str(selection or "").strip()
        sans_stack = '"anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Meiryo", sans-serif'
        serif_stack = '"anthropicSerif", "anthropicSerif Fallback", "Anthropic Serif", "Hiragino Mincho ProN", "Yu Mincho", "YuMincho", "Noto Serif JP", Georgia, "Times New Roman", Times, serif'
        default_stack = sans_stack if role == "user" else serif_stack
        if value == "preset-gothic":
            return sans_stack
        if value == "preset-mincho":
            return serif_stack
        if value.startswith("system:"):
            family = value.split(":", 1)[1].strip()
            if family:
                return f'"{family}", {default_stack}'
        return default_stack

    @classmethod
    def chat_font_settings_inline_style(cls, settings):
        user_family = cls._font_family_stack(settings.get("user_message_font", "preset-gothic"), "user")
        agent_family = cls._font_family_stack(settings.get("agent_message_font", "preset-mincho"), "agent")
        theme = str(settings.get("theme", "black-hole") or "black-hole").strip().lower()
        try:
            message_text_size = max(11, min(18, int(settings.get("message_text_size", 13))))
        except Exception:
            message_text_size = 13
        try:
            user_opacity = max(0.2, min(1.0, float(settings.get("user_message_opacity_blackhole", 1.0))))
        except Exception:
            user_opacity = 1.0
        try:
            agent_opacity = max(0.2, min(1.0, float(settings.get("agent_message_opacity_blackhole", 1.0))))
        except Exception:
            agent_opacity = 1.0
        if theme == "black-hole":
            user_color = f"rgba(252, 252, 252, {user_opacity:.2f})"
            agent_color = f"rgba(252, 252, 252, {agent_opacity:.2f})"
        else:
            # Light themes should inherit dark foreground tones.
            user_color = f"rgba(26, 30, 36, {user_opacity:.2f})"
            agent_color = f"rgba(26, 30, 36, {agent_opacity:.2f})"
        return f"""
    :root {{
      --message-text-size: {message_text_size}px;
      --message-text-line-height: {message_text_size + 9}px;
      --user-message-blackhole-color: {user_color};
      --agent-message-blackhole-color: {agent_color};
    }}
    .message.user .md-body {{
      font-family: {user_family} !important;
    }}
{generate_agent_message_selectors(" .md-body")} {{
      font-family: {agent_family} !important;
    }}
    .message.user .md-body {{
      color: var(--user-message-blackhole-color) !important;
    }}
    .message.user .md-body p,
    .message.user .md-body li,
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4,
    .message.user .md-body blockquote {{
      color: var(--user-message-blackhole-color) !important;
    }}
{generate_agent_message_selectors(" .md-body")} {{
      color: var(--agent-message-blackhole-color) !important;
    }}
{_bh_agent_detail_selectors(prefix="")} {{
      color: var(--agent-message-blackhole-color) !important;
    }}
    """

    def load_thinking_totals(self):
        return load_shared_session_thinking_totals(self.repo_root, self.session_name, self.workspace)

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

    def session_metadata(self):
        session_slug = quote(self.session_name, safe="")
        return {
            "server_instance": self.server_instance,
            "session": self.session_name,
            "active": self.session_is_active,
            "source": str(self.index_path),
            "workspace": self.workspace,
            "log_dir": self.log_dir,
            "port": self.port,
            "hub_port": self.hub_port,
            "session_path": f"/session/{session_slug}/",
            "follow_path": f"/session/{session_slug}/?follow=1",
        }

    def payload(self, limit_override=None):
        self.ensure_commit_announcements()
        meta = self.session_metadata()
        return json.dumps(
            {
                **meta,
                "filter": self.filter_agent or "all",
                "follow": self.follow_mode,
                "targets": self.active_agents(),
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
        self.ensure_caffeinate_active()
        return {"active": True}

    def ensure_caffeinate_active(self):
        if self.caffeinate_status()["active"]:
            return
        self._caffeinate_proc = subprocess.Popen(self._caffeinate_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def save_logs(self, *, reason: str = "autosave"):
        """Run multiagent save to capture panes to workspace/central logs (overwrites)."""
        reason = (reason or "autosave").strip()[:64] or "autosave"
        if not self.session_is_active:
            return 409, {"ok": False, "error": "session inactive", "reason": reason}
        bin_dir = Path(self.agent_send_path).parent.resolve()
        multiagent = bin_dir / "multiagent"
        if not multiagent.is_file():
            return 500, {"ok": False, "error": "multiagent not found", "reason": reason}
        env = os.environ.copy()
        env["MULTIAGENT_SESSION"] = self.session_name
        env["MULTIAGENT_WORKSPACE"] = self.workspace
        env["MULTIAGENT_BIN_DIR"] = str(bin_dir)
        if self.tmux_socket:
            env["MULTIAGENT_TMUX_SOCKET"] = self.tmux_socket
        if self.log_dir:
            env["MULTIAGENT_LOG_DIR"] = self.log_dir
        try:
            proc = subprocess.run(
                [str(multiagent), "save", "--session", self.session_name],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
                cwd=self.workspace or None,
                check=False,
            )
        except Exception as exc:
            return 500, {"ok": False, "error": str(exc), "reason": reason}
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            return 500, {"ok": False, "error": err, "reason": reason}
        return 200, {"ok": True, "reason": reason}

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

    def active_agents(self):
        """Return the list of agent instance names from MULTIAGENT_AGENTS."""
        try:
            r = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name, "MULTIAGENT_AGENTS"],
                capture_output=True, text=True, timeout=2, check=False,
            )
            line = r.stdout.strip()
            if r.returncode == 0 and "=" in line:
                return [a for a in line.split("=", 1)[1].split(",") if a]
        except Exception:
            pass
        pane_agents = self._agents_from_pane_env()
        if pane_agents:
            return pane_agents
        return list(self.targets) if self.targets else []

    def _agents_from_pane_env(self):
        """Recover instance names from MULTIAGENT_PANE_* while MULTIAGENT_AGENTS is still settling."""
        try:
            r = subprocess.run(
                [*self.tmux_prefix, "show-environment", "-t", self.session_name],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except Exception:
            return []
        if r.returncode != 0:
            return []
        return agents_from_tmux_env_output(r.stdout)

    def resolve_target_agents(self, target: str) -> list[str]:
        return resolve_target_agent_names(target, self.active_agents())

    def pane_id_for_agent(self, agent_name):
        pane_var = f"MULTIAGENT_PANE_{agent_name.upper().replace('-', '_')}"
        res = subprocess.run(
            [*self.tmux_prefix, "show-environment", "-t", self.session_name, pane_var],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip().split("=", 1)[-1] if "=" in res.stdout else ""

    def agent_launch_cmd(self, agent_name):
        bin_dir = Path(self.agent_send_path).parent
        agent_exec_path = Path(self.resolve_agent_executable(agent_name))
        path_prefix = ":".join(
            [
                shlex.quote(str(bin_dir)),
                shlex.quote(str(agent_exec_path.parent)),
            ]
        )
        env_parts = [
            f"PATH={path_prefix}:$PATH",
            f"MULTIAGENT_SESSION={shlex.quote(self.session_name)}",
            f"MULTIAGENT_BIN_DIR={shlex.quote(str(bin_dir))}",
            f"MULTIAGENT_WORKSPACE={shlex.quote(self.workspace)}",
            f"MULTIAGENT_TMUX_SOCKET={shlex.quote(self.tmux_socket)}",
            f"MULTIAGENT_AGENT_NAME={shlex.quote(agent_name)}",
        ]
        env_exports = "export " + " ".join(env_parts)
        agent_exec = shlex.quote(str(agent_exec_path))
        base = agent_name.split("-")[0] if "-" in agent_name else agent_name
        adef = AGENTS.get(base)
        parts = [env_exports]
        if adef and adef.launch_env:
            parts.append(f"export {adef.launch_env}")
        launch_extra = adef.launch_extra if adef else ""
        launch_flags = adef.launch_flags if adef else ""
        extra = f" {launch_extra}" if launch_extra else ""
        flags = f" {launch_flags}" if launch_flags else ""
        parts.append(f"exec{extra} {agent_exec}{flags}")
        return "; ".join(parts)

    def agent_resume_cmd(self, agent_name):
        bin_dir = Path(self.agent_send_path).parent
        agent_exec_path = Path(self.resolve_agent_executable(agent_name))
        path_prefix = ":".join(
            [
                shlex.quote(str(bin_dir)),
                shlex.quote(str(agent_exec_path.parent)),
            ]
        )
        env_parts = [
            f"PATH={path_prefix}:$PATH",
            f"MULTIAGENT_SESSION={shlex.quote(self.session_name)}",
            f"MULTIAGENT_BIN_DIR={shlex.quote(str(bin_dir))}",
            f"MULTIAGENT_WORKSPACE={shlex.quote(self.workspace)}",
            f"MULTIAGENT_TMUX_SOCKET={shlex.quote(self.tmux_socket)}",
            f"MULTIAGENT_AGENT_NAME={shlex.quote(agent_name)}",
        ]
        env_exports = "export " + " ".join(env_parts)
        agent_exec = shlex.quote(str(agent_exec_path))
        base = agent_name.split("-")[0] if "-" in agent_name else agent_name
        adef = AGENTS.get(base)
        if not adef or not adef.resume_flag:
            return self.agent_launch_cmd(agent_name)
        parts = [env_exports]
        if adef.launch_env:
            parts.append(f"export {adef.launch_env}")
        launch_extra = adef.launch_extra if adef.launch_extra else ""
        resume_extra = adef.resume_extra_flags if adef.resume_extra_flags else ""
        extra = f" {launch_extra}" if launch_extra else ""
        flags = f" {adef.resume_flag}"
        if resume_extra:
            flags += f" {resume_extra}"
        parts.append(f"exec{extra} {agent_exec}{flags}")
        return "; ".join(parts)

    @staticmethod
    def resolve_agent_executable(agent_name: str) -> str:
        base = agent_name.split("-")[0] if "-" in agent_name else agent_name
        adef = AGENTS.get(base)
        exe_name = adef.exe if adef else agent_name
        found = shutil.which(exe_name)
        if found:
            return found
        if base == "cursor":
            found = shutil.which("cursor-agent")
            if found:
                return found
        home = Path.home()
        # Explicit fallback paths from registry
        if adef:
            for p in adef.fallback_paths:
                candidate = Path(p).expanduser()
                if candidate.is_file():
                    return str(candidate)
        # NVM fallback for npm-installed agents
        if adef and adef.fallback_nvm:
            nvm_bin = Path(os.environ.get("NVM_BIN", "")).expanduser()
            nvm_candidates: list[Path] = []
            if nvm_bin.is_dir():
                nvm_candidates.append(nvm_bin / exe_name)
            nvm_candidates.extend(
                sorted(
                    (home / ".nvm" / "versions" / "node").glob(f"*/bin/{exe_name}"),
                    reverse=True,
                )
            )
            for candidate in nvm_candidates:
                if candidate.is_file():
                    return str(candidate)
        return exe_name

    def restart_agent_pane(self, agent_name):
        pane_id = self.pane_id_for_agent(agent_name)
        if not pane_id:
            return False, f"pane not found for {agent_name}"
        shell = os.environ.get("SHELL") or "/bin/zsh"
        respawn_res = subprocess.run(
            [
                *self.tmux_prefix,
                "respawn-pane",
                "-k",
                "-t",
                pane_id,
                "-c",
                self.workspace,
                shell,
                "-lc",
                self.agent_launch_cmd(agent_name),
            ],
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
        shell = os.environ.get("SHELL") or "/bin/zsh"
        respawn_res = subprocess.run(
            [
                *self.tmux_prefix,
                "respawn-pane",
                "-k",
                "-t",
                pane_id,
                "-c",
                self.workspace,
                shell,
                "-lc",
                self.agent_resume_cmd(agent_name),
            ],
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
        if target:
            target = ",".join(self.resolve_target_agents(target))
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
        pane_direct = self._parse_pane_direct_command(message)
        if message in {"brief", "save", "interrupt", "ctrlc", "enter", "restart", "resume"} or pane_direct:
            if message in {"interrupt", "ctrlc", "enter", "restart", "resume"} or pane_direct:
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
                    return 500, {"ok": False, "error": str(exc)}
                return 200, {"ok": True, "mode": pane_direct["name"] if pane_direct else message}
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
            cmd.append(target)
            result = subprocess.run(cmd, input=message, capture_output=True, text=True, env=env, check=False)
        except Exception as exc:
            return 500, {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return 400, {"ok": False, "error": (result.stderr or result.stdout or "agent-send failed").strip()}
        return 200, {"ok": True}

    @staticmethod
    def _parse_pane_direct_command(message: str):
        normalized = (message or "").strip().lower()
        if normalized == "model":
            return {"name": "model", "repeat": 1}
        match = re.fullmatch(r"(up|down)(?:\s+(\d+))?", normalized)
        if not match:
            return None
        repeat = max(1, min(int(match.group(2) or "1"), 100))
        return {"name": match.group(1), "repeat": repeat}

    def agent_statuses(self):
        result = {}
        for agent in self.active_agents():
            pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
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
        try:
            update_shared_thinking_totals_from_statuses(
                self.repo_root,
                self.session_name,
                self.workspace,
                result,
            )
        except Exception:
            pass
        return result

    def trace_content(self, agent: str, *, tail_lines: int | None = None) -> str:
        """Return tmux pane text. tail_lines: last N rows only (fast); None = full scrollback (heavy)."""
        pane_var = f"MULTIAGENT_PANE_{(agent or '').upper().replace('-', '_')}"
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
                if tail_lines is not None:
                    n = max(1, min(int(tail_lines), 10_000))
                    start = f"-{n}"
                    cap_timeout = 3
                else:
                    # Large scrollback (tmux retains up to history-limit lines; see set -g history-limit).
                    start = "-500000"
                    cap_timeout = 8
                raw = subprocess.run(
                    [
                        *self.tmux_prefix,
                        "capture-pane",
                        "-p",
                        "-e",
                        "-S",
                        start,
                        "-t",
                        pane_id,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=cap_timeout,
                    check=False,
                ).stdout
                content_str = "\n".join(l.rstrip() for l in raw.splitlines())
            else:
                content_str = "Offline"
        except Exception as e:
            content_str = f"Error: {e}"
        return content_str
