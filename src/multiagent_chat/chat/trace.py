from __future__ import annotations

import logging

from backend_core.tmux.pane import capture_pane_text
from .runtime_format import _deduplicate_consecutive_thought_blocks
from native_log_sync.agents._shared.path_state import _agent_base_name


def trace_content(self, agent: str, *, tail_lines: int | None = None) -> str:
    content_str = ""
    try:
        pane_id = self.pane_id_for_agent(agent)
        if pane_id:
            if tail_lines is not None:
                n = max(1, min(int(tail_lines), 10_000))
                start = f"-{n}"
                cap_timeout = 3
            else:
                start = "-500000"
                cap_timeout = 8
            raw = capture_pane_text(
                self,
                pane_id,
                start=start,
                include_escape=True,
                timeout_seconds=cap_timeout,
            )
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
