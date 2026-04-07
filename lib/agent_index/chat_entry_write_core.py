from __future__ import annotations


def load_thinking_totals(runtime, *, load_shared_session_thinking_totals_fn) -> dict[str, int]:
    return load_shared_session_thinking_totals_fn(runtime.repo_root, runtime.session_name, runtime.workspace)


def append_system_entry(
    runtime,
    message: str,
    *,
    agent: str = "",
    extra: dict | None = None,
    datetime_class,
    uuid_module,
    append_jsonl_entry_fn,
) -> dict:
    entry = {
        "timestamp": datetime_class.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session": runtime.session_name,
        "sender": "system",
        "targets": [],
        "message": message,
        "msg_id": uuid_module.uuid4().hex[:12],
    }
    if agent:
        entry["agent"] = agent
    if extra:
        entry.update(extra)
    append_jsonl_entry_fn(runtime.index_path, entry)
    return entry
