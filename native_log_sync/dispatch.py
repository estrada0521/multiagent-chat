from __future__ import annotations

from native_log_sync.agents.claude.read_updates import sync_claude_native_log
from native_log_sync.agents.codex.read_updates import sync_codex_native_log
from native_log_sync.agents.copilot.read_updates import sync_copilot_native_log
from native_log_sync.agents.cursor.read_updates import sync_cursor_native_log
from native_log_sync.agents.gemini.read_updates import sync_gemini_native_log
from native_log_sync.agents.opencode.read_updates import sync_opencode_native_log
from native_log_sync.agents.qwen.read_updates import sync_qwen_native_log
from native_log_sync.io.sync_timing import FIRST_SEEN_GRACE_SECONDS, SYNC_BIND_BACKFILL_WINDOW_SECONDS


def sync_agent(runtime, agent: str, path: str | None = None) -> None:
    base = str(agent or "").split("-", 1)[0].lower()
    if base == "claude":
        sync_claude_native_log(
            runtime, agent, path,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
            sync_bind_backfill_window_seconds=SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )
    elif base == "codex":
        sync_codex_native_log(
            runtime, agent, path,
            sync_bind_backfill_window_seconds=SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )
    elif base == "cursor":
        sync_cursor_native_log(
            runtime, agent, path,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
        )
    elif base == "copilot":
        sync_copilot_native_log(runtime, agent, path)
    elif base == "qwen":
        sync_qwen_native_log(
            runtime, agent, path,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
            sync_bind_backfill_window_seconds=SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )
    elif base == "gemini":
        sync_gemini_native_log(
            runtime, agent, path,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
            sync_bind_backfill_window_seconds=SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )
    elif base == "opencode":
        sync_opencode_native_log(
            runtime, agent,
            sync_bind_backfill_window_seconds=SYNC_BIND_BACKFILL_WINDOW_SECONDS,
        )
