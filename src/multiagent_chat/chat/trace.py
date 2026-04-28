from __future__ import annotations

import logging
import subprocess

from .runtime_format import _deduplicate_consecutive_thought_blocks
from native_log_sync.core._08_cursor_state import _agent_base_name


def trace_content(self, agent: str, *, tail_lines: int | None = None) -> str:
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

            base_name = _agent_base_name(agent)
            if base_name == "gemini":
                content_str = _deduplicate_consecutive_thought_blocks(content_str)
        else:
            content_str = "Offline"
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        content_str = f"Error: {e}"
    return content_str
