from __future__ import annotations


def on_pane_restart(runtime, agent: str) -> None:
    runtime._opencode_cursors.pop(agent, None)


def on_pane_add(runtime, agent: str) -> None:
    pass
