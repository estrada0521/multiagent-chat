from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


DEFAULT_MODEL = "gemini-2.5-flash"
NORMALIZED_EVENT_SCHEMA = "multiagent.normalized_event.v1"


@dataclass(frozen=True)
class GeminiRequest:
    model: str = DEFAULT_MODEL
    system: str = ""
    temperature: float | None = None
    max_output_tokens: int | None = None
    api_key_env: str = ""
    session: str = ""
    run_id: str = ""
    adapter: str = "gemini-direct"
    provider: str = "gemini"
    vendor: str = "google"
    include_raw_payload: bool = False


@dataclass
class GeminiRunSummary:
    ok: bool
    run_id: str
    model: str
    chunk_count: int = 0
    output_text: str = ""
    finish_reason: str = ""
    usage: dict | None = None
    error: str = ""
    http_status: int | None = None


def resolve_api_key(preferred_env: str) -> str:
    names: list[str] = []
    if preferred_env:
        names.append(preferred_env)
    names.extend(["GEMINI_API_KEY", "GOOGLE_API_KEY"])
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    raise RuntimeError("Gemini API key not found. Set GEMINI_API_KEY or GOOGLE_API_KEY first.")


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


def build_request_body(prompt: str, request: GeminiRequest) -> dict:
    body: dict = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ]
    }
    if request.system:
        body["system_instruction"] = {
            "parts": [{"text": request.system}],
        }
    generation_config: dict = {}
    if request.temperature is not None:
        generation_config["temperature"] = request.temperature
    if request.max_output_tokens is not None:
        generation_config["maxOutputTokens"] = request.max_output_tokens
    if generation_config:
        body["generationConfig"] = generation_config
    return body


def extract_text_chunks(payload: dict) -> list[str]:
    out: list[str] = []
    for candidate in payload.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if isinstance(text, str) and text:
                out.append(text)
    return out


def first_finish_reason(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    return str(candidates[0].get("finishReason") or "")


def event_jsonl_line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False)


def run_gemini_event_stream(
    prompt: str,
    request: GeminiRequest,
    *,
    on_event: Callable[[dict], None] | None = None,
    on_raw_line: Callable[[str], None] | None = None,
) -> GeminiRunSummary:
    model = request.model.strip() or DEFAULT_MODEL
    run_id = request.run_id.strip() or uuid.uuid4().hex[:12]
    summary = GeminiRunSummary(ok=False, run_id=run_id, model=model, usage={})
    body = build_request_body(prompt, GeminiRequest(
        model=model,
        system=request.system,
        temperature=request.temperature,
        max_output_tokens=request.max_output_tokens,
        api_key_env=request.api_key_env,
        session=request.session,
        run_id=run_id,
        adapter=request.adapter,
        provider=request.provider,
        vendor=request.vendor,
        include_raw_payload=request.include_raw_payload,
    ))
    query = urllib.parse.urlencode({"alt": "sse"})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?{query}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    ssl_context = ssl.create_default_context()
    try:
        import certifi  # type: ignore

        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass

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
        api_key = resolve_api_key(request.api_key_env)
        req.add_header("x-goog-api-key", api_key)
        with urllib.request.urlopen(req, timeout=180, context=ssl_context) as resp:
            chunk_index = 0
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if on_raw_line is not None:
                    on_raw_line(line)
                if not line.startswith("data:"):
                    continue
                raw_json = line[5:].strip()
                if not raw_json:
                    continue
                payload = json.loads(raw_json)
                text = "".join(extract_text_chunks(payload))
                if text:
                    pieces.append(text)
                finish_reason = first_finish_reason(payload)
                if finish_reason:
                    summary.finish_reason = finish_reason
                usage = payload.get("usageMetadata") or {}
                if usage:
                    summary.usage = usage
                emit(
                    "response.output_text.delta",
                    chunk_index=chunk_index,
                    text_delta=text,
                    finish_reason=finish_reason or None,
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
    except RuntimeError as exc:
        summary.error = str(exc)
        emit(
            "response.error",
            error_type="configuration_error",
            error=summary.error,
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
