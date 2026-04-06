from __future__ import annotations


def _parse_tmux_environment_output(output: str) -> dict[str, str]:
    env_map: dict[str, str] = {}
    for raw in (output or "").splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_map[key] = value
    return env_map


def _clean_tmux_env_value(value: str) -> str:
    cleaned = (value or "").strip()
    if cleaned == "-":
        return ""
    return cleaned


def session_context_from_env_output(tmux_env_output: str) -> dict[str, str]:
    env_map = _parse_tmux_environment_output(tmux_env_output)
    return {
        "workspace": _clean_tmux_env_value(env_map.get("MULTIAGENT_WORKSPACE", "")),
        "bin_dir": _clean_tmux_env_value(env_map.get("MULTIAGENT_BIN_DIR", "")),
        "tmux_socket": _clean_tmux_env_value(env_map.get("MULTIAGENT_TMUX_SOCKET", "")),
        "log_dir": _clean_tmux_env_value(env_map.get("MULTIAGENT_LOG_DIR", "")),
    }
