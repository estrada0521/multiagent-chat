"""Pre-trust a workspace directory for each known CLI agent.

Called from bin/multiagent's start_agent() before sending the launch command
to the tmux pane. Each function is idempotent (no-ops when already trusted).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _trust_claude(workspace: str) -> None:
    """~/.claude.json: projects[path].hasTrustDialogAccepted = true"""
    config_path = Path.home() / ".claude.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except Exception:
        data = {}
    projects = data.setdefault("projects", {})
    if not projects.get(workspace, {}).get("hasTrustDialogAccepted"):
        projects.setdefault(workspace, {})["hasTrustDialogAccepted"] = True
        config_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _trust_gemini(workspace: str) -> None:
    """~/.gemini/trustedFolders.json: path -> TRUST_FOLDER"""
    config_path = Path.home() / ".gemini" / "trustedFolders.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except Exception:
        data = {}
    key = workspace.lower()  # Gemini stores lowercase paths
    if key not in data:
        data[key] = "TRUST_FOLDER"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _trust_copilot(workspace: str) -> None:
    """~/.copilot/config.json: trustedFolders[] append"""
    config_path = Path.home() / ".copilot" / "config.json"
    try:
        raw = config_path.read_text(encoding="utf-8") if config_path.exists() else "{}"
        # Strip leading comment lines
        json_part = re.sub(r"^//.*$", "", raw, flags=re.MULTILINE)
        data = json.loads(json_part)
    except Exception:
        data = {}
    folders: list = data.setdefault("trustedFolders", [])
    if workspace not in folders:
        folders.append(workspace)
        comment_lines = [l for l in raw.splitlines() if l.strip().startswith("//")]
        header = "\n".join(comment_lines) + "\n" if comment_lines else ""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(header + json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _trust_codex(workspace: str) -> None:
    """~/.codex/config.toml: [projects."path"] trust_level = "trusted" """
    config_path = Path.home() / ".codex" / "config.toml"
    content = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    section = f'[projects."{workspace}"]'
    if section not in content:
        content = content.rstrip("\n") + f'\n\n{section}\ntrust_level = "trusted"\n'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(content, encoding="utf-8")


def _trust_cursor(workspace: str) -> None:
    """~/.cursor/projects/{encoded}/.workspace-trusted JSON marker"""
    encoded = workspace.lstrip("/").replace("/", "-")
    project_dir = Path.home() / ".cursor" / "projects" / encoded
    project_dir.mkdir(parents=True, exist_ok=True)
    marker = project_dir / ".workspace-trusted"
    if not marker.exists():
        marker.write_text(
            json.dumps({
                "trustedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "workspacePath": workspace,
            }, indent=2) + "\n",
            encoding="utf-8",
        )


_TRUST_FN = {
    "claude": _trust_claude,
    "gemini": _trust_gemini,
    "copilot": _trust_copilot,
    "codex": _trust_codex,
    "cursor": _trust_cursor,
}


def trust_workspace(agent_base_name: str, workspace: str) -> None:
    fn = _TRUST_FN.get(agent_base_name)
    if fn:
        try:
            fn(workspace)
        except Exception as exc:
            print(f"workspace_trust: {agent_base_name}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    # Usage: python -m multiagent_lib.workspace_trust <agent_base_name> <workspace>
    if len(sys.argv) >= 3:
        trust_workspace(sys.argv[1], sys.argv[2])
