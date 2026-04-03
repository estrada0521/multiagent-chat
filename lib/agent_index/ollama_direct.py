from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_BASE_URL = "http://localhost:11434"
NORMALIZED_EVENT_SCHEMA = "multiagent.normalized_event.v1"


@dataclass(frozen=True)
class OllamaRequest:
    model: str = DEFAULT_MODEL
    system: str = ""
    temperature: float | None = None
    max_output_tokens: int | None = None
    base_url: str = DEFAULT_BASE_URL
    keep_alive: str = "0"
    session: str = ""
    run_id: str = ""
    adapter: str = "ollama-direct"
    provider: str = "ollama"
    vendor: str = "local"
    include_raw_payload: bool = False


@dataclass
class OllamaRunSummary:
    ok: bool
    run_id: str
    model: str
    chunk_count: int = 0
    output_text: str = ""
    finish_reason: str = ""
    usage: dict | None = None
    error: str = ""
    http_status: int | None = None


def read_prompt_text(prompt_parts: list[str] | tuple[str, ...] | None) -> str:
    if prompt_parts:
        text = " ".join(str(part) for part in prompt_parts).strip()
        if text:
            return text
    try:
        import sys

        if not sys.stdin.isatty():
            text = sys.stdin.read()
            if text.strip():
                return text.strip()
    except Exception:
        pass
    raise RuntimeError("Prompt required. Pass text as arguments or via stdin.")


def build_request_body(prompt: str, request: OllamaRequest) -> dict:
    body: dict = {
        "model": request.model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": True,
        "keep_alive": request.keep_alive,
    }
    if request.system:
        body["messages"].insert(0, {
            "role": "system",
            "content": request.system,
        })
    options: dict = {}
    if request.temperature is not None:
        options["temperature"] = request.temperature
    if request.max_output_tokens is not None:
        options["num_predict"] = request.max_output_tokens
    if options:
        body["options"] = options
    return body


def event_jsonl_line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False)


def run_ollama_event_stream(
    prompt: str,
    request: OllamaRequest,
    *,
    on_event: Callable[[dict], None] | None = None,
    on_raw_line: Callable[[str], None] | None = None,
) -> OllamaRunSummary:
    model = request.model.strip() or DEFAULT_MODEL
    run_id = request.run_id.strip() or uuid.uuid4().hex[:12]
    summary = OllamaRunSummary(ok=False, run_id=run_id, model=model, usage={})
    body = build_request_body(prompt, request)
    url = f"{request.base_url.rstrip('/')}/api/chat"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    seq = 0
    pieces: list[str] = []

    def emit(event_name: str, **extra) -> None:
        nonlocal seq
        event = {
            "type": "multiagent.normalized_event",
            "schema": NORMALIZED_EVENT_SCHEMA,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event": event_name,
            "seq": seq,
            "run_id": run_id,
            "provider": request.provider,
            "vendor": request.vendor,
            "adapter": request.adapter,
            "model": model,
        }
        if request.session:
            event["session"] = request.session
        for key, value in extra.items():
            if value is None:
                continue
            if isinstance(value, str) and not value:
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            event[key] = value
        seq += 1
        if on_event is not None:
            on_event(event)

    emit(
        "response.started",
        prompt_chars=len(prompt),
        has_system_instruction=bool(request.system),
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            chunk_index = 0
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if on_raw_line is not None:
                    on_raw_line(line)
                if not line.strip():
                    continue
                payload = json.loads(line)
                message = payload.get("message") or {}
                text = message.get("content") or ""
                done = payload.get("done", False)
                if text:
                    pieces.append(text)
                usage = {}
                if done:
                    summary.finish_reason = payload.get("done_reason") or "stop"
                    prompt_tokens = payload.get("prompt_eval_count")
                    eval_tokens = payload.get("eval_count")
                    if prompt_tokens is not None or eval_tokens is not None:
                        usage = {
                            "promptTokenCount": prompt_tokens,
                            "candidatesTokenCount": eval_tokens,
                            "totalTokenCount": (prompt_tokens or 0) + (eval_tokens or 0),
                        }
                        summary.usage = usage
                emit(
                    "response.output_text.delta",
                    chunk_index=chunk_index,
                    text_delta=text,
                    finish_reason=(summary.finish_reason if done else None),
                    usage=usage or None,
                    provider_payload=payload if request.include_raw_payload else None,
                )
                chunk_index += 1
            summary.ok = True
            summary.chunk_count = chunk_index
            summary.output_text = "".join(pieces)
            emit(
                "response.completed",
                chunk_count=chunk_index,
                output_text=summary.output_text,
                finish_reason=summary.finish_reason or None,
                usage=summary.usage or None,
            )
            return summary
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = ""
        summary.error = detail or f"HTTP {exc.code}: {exc.reason}"
        summary.http_status = int(exc.code)
        emit(
            "response.error",
            error_type="http_error",
            error=summary.error,
            http_status=summary.http_status,
        )
        return summary
    except urllib.error.URLError as exc:
        summary.error = f"Network error: {exc}"
        emit(
            "response.error",
            error_type="network_error",
            error=summary.error,
        )
        return summary
    except Exception as exc:
        summary.error = str(exc) or exc.__class__.__name__
        emit(
            "response.error",
            error_type="runtime_error",
            error=summary.error,
        )
        return summary
