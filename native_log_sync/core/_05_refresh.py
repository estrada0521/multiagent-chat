from __future__ import annotations

from native_log_sync.core._01_bindings import NativeLogBinding, PaneBindingRequest, binding_for_path
from native_log_sync.sync_timing import FIRST_SEEN_GRACE_SECONDS


def _resolve_cursor_binding(runtime, request: PaneBindingRequest) -> NativeLogBinding | None:
    from native_log_sync.cursor.log_location import resolve_cursor_transcript_open_in_pane

    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=resolve_cursor_transcript_open_in_pane(runtime, request.agent),
        source="cursor-pane",
    )


def _resolve_claude_binding(runtime, request: PaneBindingRequest) -> NativeLogBinding | None:
    from native_log_sync.claude.log_location import resolve_claude_session_jsonl_path

    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=resolve_claude_session_jsonl_path(
            runtime,
            request.agent,
            None,
            None,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
        ),
        source="claude-session",
    )


def _resolve_codex_binding(runtime, request: PaneBindingRequest) -> NativeLogBinding | None:
    from native_log_sync.codex.log_location import resolve_codex_rollout_jsonl_path

    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=resolve_codex_rollout_jsonl_path(runtime, request.agent, None),
        source="codex-rollout",
    )


def _resolve_gemini_binding(runtime, request: PaneBindingRequest) -> NativeLogBinding | None:
    from native_log_sync.gemini.log_location import resolve_gemini_native_log

    workspace_text = str(runtime.workspace or "").strip()
    if not workspace_text:
        return None
    path = resolve_gemini_native_log(
        agent=request.agent,
        workspace_aliases=runtime._workspace_aliases(workspace_text),
        native_log_path=None,
        gemini_cursors=runtime._gemini_cursors,
        should_stick_to_existing_cursor=runtime._should_stick_to_existing_cursor(request.agent),
        first_seen_ts=runtime._first_seen_for_agent(request.agent),
        first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
        global_claimed_paths=set(runtime._collect_global_native_log_claims().keys()),
    )
    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=path or "",
        source="gemini-chat",
    )


def _resolve_qwen_binding(runtime, request: PaneBindingRequest) -> NativeLogBinding | None:
    from native_log_sync.qwen.log_location import resolve_qwen_chat_jsonl_path

    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=resolve_qwen_chat_jsonl_path(
            runtime,
            request.agent,
            None,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
        ),
        source="qwen-chat",
    )


def _resolve_copilot_binding(runtime, request: PaneBindingRequest) -> NativeLogBinding | None:
    from native_log_sync.copilot.log_location import resolve_path

    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=resolve_path(runtime, request.agent, request.pane_id, request.pane_pid),
        source="copilot-events",
    )


_BINDING_RESOLVERS = {
    "claude": _resolve_claude_binding,
    "codex": _resolve_codex_binding,
    "copilot": _resolve_copilot_binding,
    "cursor": _resolve_cursor_binding,
    "gemini": _resolve_gemini_binding,
    "qwen": _resolve_qwen_binding,
}


def refresh_native_log_bindings(
    runtime,
    pane_requests: list[PaneBindingRequest],
    *,
    reason: str = "",
) -> list[NativeLogBinding]:
    del reason
    bindings: list[NativeLogBinding] = []
    next_by_agent: dict[str, NativeLogBinding] = {}
    next_watch_roots: dict[str, list[str]] = {}

    for request in pane_requests:
        runtime._pane_native_log_paths.pop(request.pane_id, None)
        resolver = _BINDING_RESOLVERS.get(request.agent.split("-", 1)[0])
        if resolver is None:
            continue
        binding = resolver(runtime, request)
        if binding is None:
            continue
        bindings.append(binding)
        next_by_agent[binding.agent] = binding
        for root in binding.watch_roots:
            next_watch_roots.setdefault(root, []).append(binding.agent)

    runtime._native_log_bindings_by_agent = next_by_agent
    runtime._native_log_watch_roots = next_watch_roots
    runtime._native_log_watch_generation += 1
    runtime._native_log_watch_reconfigure.set()
    return bindings
