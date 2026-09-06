#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote as url_quote, urlparse

repo_root = Path(sys.argv[1]).resolve()
hub_port = int(sys.argv[2])
edge_port = int(sys.argv[3])
tmux_socket = sys.argv[4] if len(sys.argv) > 4 else ""

sys.path.insert(0, str(repo_root))
from backend_core.net import http_proxy
from workspace_sync.files.runtime import FileRuntime
from hub_backend.runtime import HubRuntime
from hub_backend.chat_supervisor import ensure_chat_server
from hub_backend.session_api import resolve_session_chat_target
from appearance.typography import CODE_FONT, MESSAGE_FONT

hub = HubRuntime(repo_root, tmux_socket, hub_port=hub_port)

SESSION_GET_RETRY_WINDOW = 3.0
SESSION_GET_RETRY_DELAY = 0.1
SESSION_POST_RETRY_WINDOW = 0.5
UPSTREAM_TIMEOUT = 30.0
TRANSIENT_UPSTREAM_ERRORS = http_proxy.TRANSIENT_UPSTREAM_ERRORS
STREAM_CHUNK_SIZE = 64 * 1024


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _safe_write(self, body: bytes):
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return False
        return True

    def _send_json(self, status: int, payload: str):
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._safe_write(body)

    def _send_bad_gateway(self, exc):
        body = f"Bad Gateway: {exc}".encode("utf-8")
        self.send_response(502)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._safe_write(body)

    def _send_service_unavailable(self, detail: str):
        body = f"Service Unavailable: {detail}\n\nThe system is temporarily unstable (tmux timeout). Please try again in a few seconds.".encode("utf-8")
        self.send_response(503)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._safe_write(body)


    def _read_request_body(self, method: str) -> bytes | None:
        body = None
        if method == "POST":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            body = self.rfile.read(length)
        return body

    def _forward_headers(self, *, forwarded_prefix: str = "", host_override: str = "") -> dict[str, str]:
        external_host = host_override or self.headers.get("Host", "")
        extra = None
        if forwarded_prefix:
            extra = {
                "X-Forwarded-Public-Host": external_host,
                "X-Forwarded-Public-Proto": "https",
            }
        return http_proxy.forward_headers(
            self.headers, host=external_host, forwarded_prefix=forwarded_prefix, extra=extra,
        )

    def _open_upstream(self, method: str, upstream: str, *, body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = UPSTREAM_TIMEOUT):
        return http_proxy.open_upstream(method, upstream, body=body, headers=headers, timeout=timeout)

    def _request_upstream(self, method: str, upstream: str, *, body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = UPSTREAM_TIMEOUT) -> dict:
        return http_proxy.read_upstream(method, upstream, body=body, headers=headers, timeout=timeout)

    def _relay_upstream(self, response: dict, *, extra_headers: dict[str, str] | None = None):
        http_proxy.relay_buffered(self, response, extra_headers=extra_headers)

    def _relay_upstream_stream(self, status: int, resp_headers, resp):
        http_proxy.relay_stream(self, status, resp_headers, resp, chunk_size=STREAM_CHUNK_SIZE)

    def _proxy(self, method: str, upstream: str, *, forwarded_prefix: str = ""):
        body = self._read_request_body(method)
        headers = self._forward_headers(forwarded_prefix=forwarded_prefix)
        try:
            status, resp_headers, resp = self._open_upstream(method, upstream, body=body, headers=headers)
        except TRANSIENT_UPSTREAM_ERRORS as exc:
            self._send_bad_gateway(exc)
            return
        self._relay_upstream_stream(status, resp_headers, resp)

    def _resolve_session(self, session_name: str) -> dict | None:
        """Resolve a session (active, or archived as a read-only viewer) without
        reviving it. Reviving is exclusively a /revive-session action, proxied
        straight through to the local hub."""
        self.__tmux_unhealthy_detail = ""
        resolved = resolve_session_chat_target(hub, session_name)
        if resolved["status"] == "unhealthy":
            self.__tmux_unhealthy_detail = resolved.get("detail", "")
            return None
        if resolved["status"] != "ok":
            return None
        return resolved

    def _session_file_runtime(self, session_name: str, workspace: str = "") -> FileRuntime | None:
        if not workspace:
            resolved = self._resolve_session(session_name)
            workspace = str((resolved or {}).get("workspace") or "").strip()
        if not workspace:
            return None
        return FileRuntime(workspace=workspace)

    def _handle_session_file_request(self, session_name: str, suffix: str, parsed, *, workspace: str = "") -> bool:
        if suffix not in {"/file-raw", "/file-view"}:
            return False
        runtime = self._session_file_runtime(session_name, workspace)
        if runtime is None:
            self.send_response(404)
            self.end_headers()
            return True
        qs = parse_qs(parsed.query)
        rel = qs.get("path", [""])[0]
        if suffix == "/file-raw":
            try:
                metadata = runtime.raw_response_metadata(rel, self.headers.get("Range", ""))
            except PermissionError:
                self.send_error(403)
                return True
            except FileNotFoundError:
                self.send_error(404)
                return True
            if int(metadata.get("status", 500)) == 416:
                self.send_response(416)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes */{int(metadata.get('size', 0) or 0)}")
                self.end_headers()
                return True
            self.send_response(int(metadata.get("status", 200)))
            self.send_header("Content-Type", str(metadata.get("content_type") or "application/octet-stream"))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Accept-Ranges", "bytes")
            content_range = str(metadata.get("content_range") or "")
            if content_range:
                self.send_header("Content-Range", content_range)
            self.send_header("Content-Length", str(int(metadata.get("length", 0) or 0)))
            self.end_headers()
            runtime.stream_raw_response(metadata, self._safe_write)
            return True
        embed = qs.get("embed", [""])[0] == "1"
        try:
            page = runtime.file_view(
                rel,
                embed=embed,
                base_path=f"/session/{url_quote(session_name)}",
                agent_font_family=MESSAGE_FONT,
                agent_code_font=CODE_FONT,
            )
        except PermissionError:
            self.send_error(403)
            return True
        except FileNotFoundError:
            self.send_error(404)
            return True
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._safe_write(body)
        return True

    def _proxy_hub(self, method: str):
        parsed = urlparse(self.path)
        upstream = f"{hub.hub_scheme}://127.0.0.1:{hub_port}{parsed.path}"
        if parsed.query:
            upstream += f"?{parsed.query}"
        self._proxy(method, upstream)

    def _proxy_session(self, method: str):
        parsed = urlparse(self.path)
        parts = parsed.path.split("/", 3)
        if len(parts) < 3 or not parts[2]:
            self.send_response(404)
            self.end_headers()
            return
        session_name = parts[2]
        suffix = "/" if len(parts) < 4 or not parts[3] else f"/{parts[3]}"
        resolved = self._resolve_session(session_name)
        if resolved is None:
            if getattr(self, "_Handler__tmux_unhealthy_detail", ""):
                self._send_service_unavailable(self._Handler__tmux_unhealthy_detail)
                return
            self.send_response(404)
            self.end_headers()
            return
        workspace = str(resolved.get("workspace") or "").strip()
        session_is_active = bool(resolved.get("session_is_active", True))
        if method == "GET" and self._handle_session_file_request(session_name, suffix, parsed, workspace=workspace):
            return
        body = self._read_request_body(method)
        forwarded_prefix = f"/session/{session_name}"
        headers = self._forward_headers(forwarded_prefix=forwarded_prefix)
        deadline = time.time() + SESSION_GET_RETRY_WINDOW if method == "GET" else time.time()
        post_deadline = time.time() + SESSION_POST_RETRY_WINDOW if method == "POST" and suffix == "/new-chat" else time.time()
        while True:
            ok, chat_port, detail = ensure_chat_server(
                hub,
                expected_active=session_is_active,
                workspace=workspace,
            )
            if not ok:
                body_bytes = f"Failed to start chat for {session_name}: {detail}".encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body_bytes)))
                self.end_headers()
                self._safe_write(body_bytes)
                return
            upstream_suffix = suffix + (f"?{parsed.query}" if parsed.query else "")
            last_exc = None
            response = None
            status = 0
            resp_headers = None
            resp = None
            upstream = f"{hub.hub_scheme}://127.0.0.1:{chat_port}{upstream_suffix}"
            try:
                if method == "POST" and suffix == "/new-chat":
                    response = self._request_upstream(method, upstream, body=body, headers=headers)
                else:
                    status, resp_headers, resp = self._open_upstream(method, upstream, body=body, headers=headers)
                last_exc = None
            except TRANSIENT_UPSTREAM_ERRORS as exc:
                last_exc = exc
            if last_exc is not None:
                if method == "GET" and time.time() < deadline:
                    time.sleep(SESSION_GET_RETRY_DELAY)
                    continue
                if method == "POST" and suffix == "/new-chat" and time.time() < post_deadline:
                    time.sleep(SESSION_GET_RETRY_DELAY)
                    continue
                self._send_bad_gateway(last_exc)
                return
            if method == "POST" and suffix == "/new-chat":
                self._relay_upstream(response)
                return
            if method == "GET" and status in {502, 503, 504} and time.time() < deadline:
                try:
                    resp.close()
                except Exception:
                    pass
                time.sleep(SESSION_GET_RETRY_DELAY)
                continue
            self._relay_upstream_stream(status, resp_headers, resp)
            return

    def _handle_open_session(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        session_name = (qs.get("session", [""])[0] or "").strip()
        fmt = qs.get("format", [""])[0]
        resolved = self._resolve_session(session_name) if session_name else None
        if not session_name or resolved is None:
            if getattr(self, "_Handler__tmux_unhealthy_detail", ""):
                payload = json.dumps({"ok": False, "error": f"tmux unresponsive: {self._Handler__tmux_unhealthy_detail}"})
                self._send_json(503, payload)
                return
            payload = '{"ok": false, "error": "Session not found"}'
            self._send_json(404, payload)
            return
        location = f"/session/{url_quote(session_name, safe='')}/?follow=1"
        if fmt == "json":
            self._send_json(200, f'{{"ok": true, "chat_url": "{location}"}}')
        else:
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/session/"):
            self._proxy_session("GET")
            return
        if parsed.path == "/open-session":
            self._handle_open_session()
            return
        self._proxy_hub("GET")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/session/"):
            self._proxy_session("POST")
            return
        self._proxy_hub("POST")


ThreadingHTTPServer.allow_reuse_address = True
server = ThreadingHTTPServer(("127.0.0.1", edge_port), Handler)
logging.info("http://127.0.0.1:%s", edge_port)
server.serve_forever()
