from __future__ import annotations

import subprocess


def capture_pane_text(
    runtime,
    pane_id: str,
    *,
    start: str,
    include_escape: bool = False,
    timeout_seconds: int = 2,
    subprocess_module=subprocess,
) -> str:
    pane = str(pane_id or "").strip()
    if not pane:
        return ""
    cmd = [*runtime.tmux_prefix, "capture-pane", "-p"]
    if include_escape:
        cmd.append("-e")
    cmd.extend(["-S", str(start), "-t", pane])
    result = subprocess_module.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout or ""
