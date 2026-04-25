#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import time
from http.client import RemoteDisconnected
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote as url_quote, urlencode, urlparse
from urllib.request import Request, urlopen

repo_root = Path(sys.argv[1]).resolve()
script_path = Path(sys.argv[2]).resolve()
hub_port = int(sys.argv[3])
edge_port = int(sys.argv[4])
tmux_socket = sys.argv[5] if len(sys.argv) > 5 else ""

cert_file = (os.environ.get("MULTIAGENT_CERT_FILE", "") or "").strip()
key_file = (os.environ.get("MULTIAGENT_KEY_FILE", "") or "").strip()
if not cert_file or not key_file:
    default_cert = repo_root / "certs" / "cert.pem"
    default_key = repo_root / "certs" / "key.pem"
    if default_cert.is_file() and default_key.is_file():
        os.environ.setdefault("MULTIAGENT_CERT_FILE", str(default_cert))
        os.environ.setdefault("MULTIAGENT_KEY_FILE", str(default_key))

sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "src"))
from multiagent_chat.files.runtime import FileRuntime
from multiagent_chat.hub.runtime import HubRuntime
from multiagent_chat.chat.runtime import ChatRuntime
from multiagent_chat.runtime.state import load_hub_settings

hub = HubRuntime(repo_root, script_path, tmux_socket, hub_port=hub_port)
ensure_chat_server = hub.ensure_chat_server
revive_archived_session = hub.revive_archived_session

SESSION_GET_RETRY_WINDOW = 3.0
SESSION_GET_RETRY_DELAY = 0.15
SESSION_POST_RETRY_WINDOW = 0.6
SESSION_RESTART_WAIT_WINDOW = 2.5
SESSION_STATE_TIMEOUT = 1.2
UPSTREAM_TIMEOUT = 30.0
TRANSIENT_UPSTREAM_ERRORS = (URLError, OSError, TimeoutError, RemoteDisconnected)
STREAM_CHUNK_SIZE = 64 * 1024
PUBLIC_MESSAGE_LIMIT = 50


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
        headers = {}
        external_host = host_override or self.headers.get("Host", "")
        for key, value in self.headers.items():
            key_lc = key.lower()
            if key_lc in {"host", "content-length", "connection", "accept-encoding"}:
                continue
            headers[key] = value
        headers["Host"] = external_host
        headers["Accept-Encoding"] = "identity"
        if forwarded_prefix:
            headers["X-Forwarded-Prefix"] = forwarded_prefix
            headers["X-Forwarded-Public-Host"] = external_host
            headers["X-Forwarded-Public-Proto"] = "https"
        return headers

    def _open_upstream(self, method: str, upstream: str, *, body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = UPSTREAM_TIMEOUT):
        req = Request(upstream, data=body, method=method, headers=headers)
        ctx = ssl._create_unverified_context()
        try:
            resp = urlopen(req, context=ctx, timeout=timeout)
            return int(getattr(resp, "status", 200) or 200), resp.headers, resp
        except HTTPError as exc:
            return exc.code, exc.headers, exc

    def _request_upstream(self, method: str, upstream: str, *, body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = UPSTREAM_TIMEOUT) -> dict:
        status, resp_headers, resp = self._open_upstream(method, upstream, body=body, headers=headers, timeout=timeout)
        try:
            resp_body = resp.read()
        finally:
            try:
                resp.close()
            except Exception:
                pass
        return {"status": status, "headers": resp_headers, "body": resp_body}

    def _relay_upstream(self, response: dict, *, extra_headers: dict[str, str] | None = None):
        status = int(response.get("status", 502))
        resp_headers = response.get("headers") or {}
        resp_body = response.get("body") or b""
        self.send_response(status)
        for key, value in resp_headers.items():
            key_lc = key.lower()
            if key_lc in {"transfer-encoding", "connection", "content-length", "content-encoding"}:
                continue
            self.send_header(key, value)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self._safe_write(resp_body)

    def _relay_upstream_stream(self, status: int, resp_headers, resp):
        try:
            self.send_response(status)
            for key, value in resp_headers.items():
                if key.lower() in {"transfer-encoding", "connection"}:
                    continue
                self.send_header(key, value)
            self.end_headers()
            while True:
                chunk = resp.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                if not self._safe_write(chunk):
                    break
        finally:
            try:
                resp.close()
            except Exception:
                pass

    def _proxy(self, method: str, upstream: str, *, forwarded_prefix: str = ""):
        body = self._read_request_body(method)
        headers = self._forward_headers(forwarded_prefix=forwarded_prefix)
        try:
            status, resp_headers, resp = self._open_upstream(method, upstream, body=body, headers=headers)
        except TRANSIENT_UPSTREAM_ERRORS as exc:
            self._send_bad_gateway(exc)
            return
        self._relay_upstream_stream(status, resp_headers, resp)

    def _active_session_record(self, session_name: str, *, revive: bool = False) -> dict | None:
        self.__tmux_unhealthy_detail = ""
        query = hub.active_session_records_query()
        if query.state == "unhealthy":
            self.__tmux_unhealthy_detail = query.detail
            return None

        record = query.records.get(session_name)
        if record is not None or not revive:
            return record

        ok, _detail = revive_archived_session(session_name)
        if not ok:
            if "unresponsive" in (_detail or ""):
                self.__tmux_unhealthy_detail = _detail
            return None

        # Re-query after revive to ensure we have the latest and healthy state
        final_query = hub.active_session_records_query()
        if final_query.state == "unhealthy":
            self.__tmux_unhealthy_detail = final_query.detail
            return None
        return final_query.records.get(session_name)

    def _session_file_runtime(self, session_name: str, record: dict | None = None) -> FileRuntime | None:
        record = record or self._active_session_record(session_name)
        if record is None:
            return None
        workspace = (record.get("workspace") or "").strip() or str(repo_root)
        return FileRuntime(workspace=workspace)

    @staticmethod
    def _public_message_limit(query: str) -> int:
        qs = parse_qs(query, keep_blank_values=True)
        try:
            requested = int((qs.get("limit", [""])[0] or "").strip())
        except ValueError:
            requested = PUBLIC_MESSAGE_LIMIT
        if requested <= 0:
            requested = PUBLIC_MESSAGE_LIMIT
        return min(requested, PUBLIC_MESSAGE_LIMIT)

    @staticmethod
    def _with_query_limit(suffix: str, query: str, limit: int) -> str:
        qs = parse_qs(query, keep_blank_values=True)
        qs["limit"] = [str(limit)]
        qs["light"] = ["1"]
        next_query = urlencode(qs, doseq=True)
        return suffix + (f"?{next_query}" if next_query else "")

    def _relay_public_messages(self, response: dict, *, limit: int):
        status = int(response.get("status", 502))
        if status != 200:
            self._relay_upstream(response)
            return
        try:
            payload_body = json.loads((response.get("body") or b"{}").decode("utf-8", errors="replace"))
        except Exception:
            self._relay_upstream(response)
            return
        entries = payload_body.get("entries")
        if isinstance(entries, list) and limit > 0 and len(entries) > limit:
            payload_body["entries"] = entries[-limit:]
            payload_body["has_older"] = True
        body = json.dumps(payload_body, ensure_ascii=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self._safe_write(body)

    def _handle_session_file_request(self, session_name: str, suffix: str, parsed, *, record: dict | None = None) -> bool:
        if suffix not in {"/file-raw", "/file-view", "/file-openability"}:
            return False
        runtime = self._session_file_runtime(session_name, record)
        if runtime is None:
            self.send_response(404)
            self.end_headers()
            return True
        qs = parse_qs(parsed.query)
        rel = qs.get("path", [""])[0]
        try:
            full_path = runtime._resolve_path(rel)
        except PermissionError:
            self.send_error(403)
            return True
        except FileNotFoundError:
            self.send_error(404)
            return True
        if not os.path.exists(full_path):
            self.send_error(404)
            return True
        if suffix == "/file-openability":
            try:
                payload_body = {"editable": runtime.can_open_in_editor(rel)}
            except PermissionError:
                self.send_error(403)
                return True
            except FileNotFoundError:
                self.send_error(404)
                return True
            body = json.dumps(payload_body, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._safe_write(body)
            return True
        if suffix == "/file-raw":
            metadata = runtime.raw_response_metadata(rel, self.headers.get("Range", ""))
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
            settings = load_hub_settings(repo_root)
            agent_font_mode = str(settings.get("agent_font_mode", "serif") or "serif").strip().lower()
            agent_message_font = str(
                settings.get(
                    "agent_message_font",
                    "preset-gothic" if agent_font_mode == "gothic" else "preset-mincho",
                )
                or ("preset-gothic" if agent_font_mode == "gothic" else "preset-mincho")
            ).strip()
            page = runtime.file_view(
                rel,
                embed=embed,
                base_path=f"/session/{url_quote(session_name)}",
                agent_font_mode=agent_font_mode,
                agent_font_family=ChatRuntime._font_family_stack(agent_message_font, "agent"),
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

    def _read_chat_session_state(self, chat_port: int) -> dict | None:
        upstream = f"https://127.0.0.1:{chat_port}/session-state?ts={int(time.time() * 1000)}"
        headers = self._forward_headers(host_override=f"127.0.0.1:{chat_port}")
        try:
            response = self._request_upstream("GET", upstream, headers=headers, timeout=SESSION_STATE_TIMEOUT)
        except TRANSIENT_UPSTREAM_ERRORS:
            return None
        if int(response.get("status", 0)) != 200:
            return None
        try:
            return json.loads((response.get("body") or b"{}").decode("utf-8", errors="replace"))
        except Exception:
            return None

    def _wait_for_chat_restart(self, session_name: str, previous_instance: str = ""):
        deadline = time.time() + SESSION_RESTART_WAIT_WINDOW
        saw_disconnect = False
        while time.time() < deadline:
            ok, chat_port, _detail = ensure_chat_server(session_name)
            if ok:
                payload = self._read_chat_session_state(chat_port)
                instance = str((payload or {}).get("server_instance") or "")
                if not previous_instance or (instance and instance != previous_instance) or saw_disconnect:
                    return True
            else:
                payload = None
            if not payload:
                saw_disconnect = True
            time.sleep(SESSION_GET_RETRY_DELAY)
        return False

    def _proxy_hub(self, method: str):
        parsed = urlparse(self.path)
        upstream = f"https://127.0.0.1:{hub_port}{parsed.path}"
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
        record = self._active_session_record(session_name)
        if record is None:
            if getattr(self, "_Handler__tmux_unhealthy_detail", ""):
                self._send_service_unavailable(self._Handler__tmux_unhealthy_detail)
                return
            self.send_response(404)
            self.end_headers()
            return
        if method == "GET" and self._handle_session_file_request(session_name, suffix, parsed, record=record):
            return
        body = self._read_request_body(method)
        forwarded_prefix = f"/session/{session_name}"
        headers = self._forward_headers(forwarded_prefix=forwarded_prefix)
        previous_instance = ""
        deadline = time.time() + SESSION_GET_RETRY_WINDOW if method == "GET" else time.time()
        post_deadline = time.time() + SESSION_POST_RETRY_WINDOW if method == "POST" and suffix == "/new-chat" else time.time()
        public_message_limit = self._public_message_limit(parsed.query) if method == "GET" and suffix == "/messages" else 0
        while True:
            ok, chat_port, detail = ensure_chat_server(session_name)
            if not ok:
                body_bytes = f"Failed to start chat for {session_name}: {detail}".encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body_bytes)))
                self.end_headers()
                self._safe_write(body_bytes)
                return
            if method == "POST" and suffix == "/new-chat" and not previous_instance:
                payload = self._read_chat_session_state(chat_port)
                previous_instance = str((payload or {}).get("server_instance") or "")
            upstream_suffix = self._with_query_limit(suffix, parsed.query, public_message_limit) if public_message_limit else suffix
            if not public_message_limit and parsed.query:
                upstream_suffix += f"?{parsed.query}"
            upstream = f"https://127.0.0.1:{chat_port}{upstream_suffix}"
            try:
                if method == "POST" and suffix == "/new-chat":
                    response = self._request_upstream(method, upstream, body=body, headers=headers)
                elif public_message_limit:
                    response = self._request_upstream(method, upstream, body=body, headers=headers)
                else:
                    status, resp_headers, resp = self._open_upstream(method, upstream, body=body, headers=headers)
            except TRANSIENT_UPSTREAM_ERRORS as exc:
                if method == "GET" and time.time() < deadline:
                    time.sleep(SESSION_GET_RETRY_DELAY)
                    continue
                if method == "POST" and suffix == "/new-chat" and time.time() < post_deadline:
                    time.sleep(SESSION_GET_RETRY_DELAY)
                    continue
                self._send_bad_gateway(exc)
                return
            if method == "POST" and suffix == "/new-chat":
                ready = False
                if 200 <= int(response.get("status", 0)) < 300:
                    ready = self._wait_for_chat_restart(session_name, previous_instance)
                self._relay_upstream(
                    response,
                    extra_headers={"X-Multiagent-Chat-Ready": "1" if ready else "0"},
                )
                return
            if public_message_limit:
                if method == "GET" and int(response.get("status", 0)) in {502, 503, 504} and time.time() < deadline:
                    time.sleep(SESSION_GET_RETRY_DELAY)
                    continue
                self._relay_public_messages(response, limit=public_message_limit)
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
        if not session_name or self._active_session_record(session_name, revive=True) is None:
            if getattr(self, "_Handler__tmux_unhealthy_detail", ""):
                payload = json.dumps({"ok": False, "error": f"tmux unresponsive: {self._Handler__tmux_unhealthy_detail}"})
                self._send_json(503, payload)
                return
            payload = '{"ok": false, "error": "Session not found"}'
            self._send_json(404, payload)
            return
        ok, _chat_port, detail = ensure_chat_server(session_name)
        if not ok:
            payload = '{"ok": false, "error": "%s"}' % detail.replace('"', "'")
            self._send_json(500, payload)
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
