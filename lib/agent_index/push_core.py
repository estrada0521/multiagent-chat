from __future__ import annotations

import base64
import contextlib
import fcntl
import hashlib
import http.client
import json
import logging
import os
import re
import ssl
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlparse

from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .state_core import local_state_dir


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    text = str(raw or "").strip()
    if not text:
        return b""
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("ascii"))


def _sha1_hex(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _safe_session_slug(session_name: str, workspace: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", str(session_name or "").strip()).strip("-") or "session"
    workspace_hash = _sha1_hex(str(Path(workspace or "").expanduser().resolve()))[:12]
    return f"{base}-{workspace_hash}"


def _push_state_dir(repo_root: Path | str) -> Path:
    path = local_state_dir(repo_root) / "push"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_push_state_path(repo_root: Path | str, session_name: str, workspace: str) -> Path:
    return _push_state_dir(repo_root) / f"{_safe_session_slug(session_name, workspace)}.json"


def _session_push_lock_path(repo_root: Path | str, session_name: str, workspace: str) -> Path:
    return _push_state_dir(repo_root) / f"{_safe_session_slug(session_name, workspace)}.lock"


def _vapid_state_path(repo_root: Path | str) -> Path:
    return _push_state_dir(repo_root) / ".vapid-keypair.json"


def _hub_push_state_path(repo_root: Path | str) -> Path:
    return _push_state_dir(repo_root) / "hub.json"


def _hub_push_lock_path(repo_root: Path | str) -> Path:
    return _push_state_dir(repo_root) / "hub.lock"


@contextlib.contextmanager
def _locked_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield handle
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_json_dict(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return {}
    return data if isinstance(data, dict) else {}


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def _ec_public_key_bytes(public_key: ec.EllipticCurvePublicKey) -> bytes:
    numbers = public_key.public_numbers()
    return b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    h = hmac.HMAC(salt, hashes.SHA256())
    h.update(ikm)
    return h.finalize()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    h = hmac.HMAC(prk, hashes.SHA256())
    h.update(info + b"\x01")
    return h.finalize()[:length]


def ensure_vapid_keypair(repo_root: Path | str) -> dict[str, str]:
    path = _vapid_state_path(repo_root)
    with _locked_file(path.with_suffix(".lock")):
        payload = _read_json_dict(path)
        private_pem = str(payload.get("private_pem") or "").strip()
        public_key = str(payload.get("public_key") or "").strip()
        if private_pem and public_key:
            return {"private_pem": private_pem, "public_key": public_key}

        private_key = ec.generate_private_key(ec.SECP256R1())
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        public_key = _b64url_encode(_ec_public_key_bytes(private_key.public_key()))
        payload = {
            "private_pem": private_pem,
            "public_key": public_key,
            "created_at": int(time.time()),
        }
        _write_json_atomic(path, payload)
        return {"private_pem": private_pem, "public_key": public_key}


def vapid_public_key(repo_root: Path | str) -> str:
    return ensure_vapid_keypair(repo_root)["public_key"]


def _load_session_state(repo_root: Path | str, session_name: str, workspace: str) -> dict:
    path = _session_push_state_path(repo_root, session_name, workspace)
    payload = _read_json_dict(path)
    subscriptions = payload.get("subscriptions")
    if not isinstance(subscriptions, dict):
        subscriptions = {}
    payload["subscriptions"] = subscriptions
    payload["session_name"] = session_name
    payload["workspace"] = workspace
    return payload


def _subscription_id(endpoint: str) -> str:
    return _sha1_hex(str(endpoint or "").strip())[:16]


def _normalize_subscription(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    endpoint = str(raw.get("endpoint") or "").strip()
    keys = raw.get("keys")
    if not endpoint or not isinstance(keys, dict):
        return None
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()
    if not p256dh or not auth:
        return None
    expiration = raw.get("expirationTime")
    if expiration in ("", "null"):
        expiration = None
    if expiration is not None:
        try:
            expiration = int(expiration)
        except Exception:
            expiration = None
    return {
        "endpoint": endpoint,
        "expirationTime": expiration,
        "keys": {
            "p256dh": p256dh,
            "auth": auth,
        },
    }


def load_push_subscriptions(repo_root: Path | str, session_name: str, workspace: str) -> list[dict]:
    payload = _load_session_state(repo_root, session_name, workspace)
    items = []
    for sub_id, entry in payload.get("subscriptions", {}).items():
        if not isinstance(entry, dict):
            continue
        normalized = _normalize_subscription(entry)
        if normalized is None:
            continue
        normalized.update({
            "id": sub_id,
            "client_id": str(entry.get("client_id") or "").strip(),
            "user_agent": str(entry.get("user_agent") or "").strip(),
            "created_at": float(entry.get("created_at") or 0) or 0.0,
            "updated_at": float(entry.get("updated_at") or 0) or 0.0,
        })
        items.append(normalized)
    return items


def _load_hub_push_state(repo_root: Path | str) -> dict:
    path = _hub_push_state_path(repo_root)
    payload = _read_json_dict(path)
    subscriptions = payload.get("subscriptions")
    if not isinstance(subscriptions, dict):
        subscriptions = {}
    payload["subscriptions"] = subscriptions
    return payload


def load_hub_push_subscriptions(repo_root: Path | str) -> list[dict]:
    payload = _load_hub_push_state(repo_root)
    items = []
    for sub_id, entry in payload.get("subscriptions", {}).items():
        if not isinstance(entry, dict):
            continue
        normalized = _normalize_subscription(entry)
        if normalized is None:
            continue
        normalized.update({
            "id": sub_id,
            "client_id": str(entry.get("client_id") or "").strip(),
            "user_agent": str(entry.get("user_agent") or "").strip(),
            "created_at": float(entry.get("created_at") or 0) or 0.0,
            "updated_at": float(entry.get("updated_at") or 0) or 0.0,
        })
        items.append(normalized)
    return items


def upsert_hub_push_subscription(
    repo_root: Path | str,
    subscription: dict,
    *,
    client_id: str = "",
    user_agent: str = "",
) -> dict:
    normalized = _normalize_subscription(subscription)
    if normalized is None:
        raise ValueError("invalid push subscription")
    path = _hub_push_state_path(repo_root)
    lock_path = _hub_push_lock_path(repo_root)
    now_ts = time.time()
    sub_id = _subscription_id(normalized["endpoint"])
    with _locked_file(lock_path):
        payload = _load_hub_push_state(repo_root)
        existing = payload["subscriptions"].get(sub_id)
        created_at = float(existing.get("created_at") or 0) if isinstance(existing, dict) else 0.0
        payload["subscriptions"][sub_id] = {
            **normalized,
            "client_id": str(client_id or "").strip(),
            "user_agent": str(user_agent or "").strip()[:500],
            "created_at": created_at or now_ts,
            "updated_at": now_ts,
        }
        payload["updated_at"] = now_ts
        _write_json_atomic(path, payload)
    return {"id": sub_id, "endpoint": normalized["endpoint"]}


def remove_hub_push_subscription(repo_root: Path | str, endpoint: str) -> bool:
    sub_id = _subscription_id(endpoint)
    path = _hub_push_state_path(repo_root)
    lock_path = _hub_push_lock_path(repo_root)
    removed = False
    with _locked_file(lock_path):
        payload = _load_hub_push_state(repo_root)
        if sub_id in payload["subscriptions"]:
            del payload["subscriptions"][sub_id]
            payload["updated_at"] = time.time()
            _write_json_atomic(path, payload)
            removed = True
    return removed


def upsert_push_subscription(
    repo_root: Path | str,
    session_name: str,
    workspace: str,
    subscription: dict,
    *,
    client_id: str = "",
    user_agent: str = "",
) -> dict:
    normalized = _normalize_subscription(subscription)
    if normalized is None:
        raise ValueError("invalid push subscription")
    path = _session_push_state_path(repo_root, session_name, workspace)
    lock_path = _session_push_lock_path(repo_root, session_name, workspace)
    now_ts = time.time()
    sub_id = _subscription_id(normalized["endpoint"])
    with _locked_file(lock_path):
        payload = _load_session_state(repo_root, session_name, workspace)
        existing = payload["subscriptions"].get(sub_id)
        created_at = float(existing.get("created_at") or 0) if isinstance(existing, dict) else 0.0
        payload["subscriptions"][sub_id] = {
            **normalized,
            "client_id": str(client_id or "").strip(),
            "user_agent": str(user_agent or "").strip()[:500],
            "created_at": created_at or now_ts,
            "updated_at": now_ts,
        }
        payload["updated_at"] = now_ts
        _write_json_atomic(path, payload)
    return {"id": sub_id, "endpoint": normalized["endpoint"]}


def remove_push_subscription(
    repo_root: Path | str,
    session_name: str,
    workspace: str,
    endpoint: str,
) -> bool:
    sub_id = _subscription_id(endpoint)
    path = _session_push_state_path(repo_root, session_name, workspace)
    lock_path = _session_push_lock_path(repo_root, session_name, workspace)
    removed = False
    with _locked_file(lock_path):
        payload = _load_session_state(repo_root, session_name, workspace)
        if sub_id in payload["subscriptions"]:
            del payload["subscriptions"][sub_id]
            payload["updated_at"] = time.time()
            _write_json_atomic(path, payload)
            removed = True
    return removed


def claim_push_notification(
    repo_root: Path | str,
    session_name: str,
    workspace: str,
    msg_id: str,
) -> bool:
    candidate = str(msg_id or "").strip()
    if not candidate:
        return False
    path = _session_push_state_path(repo_root, session_name, workspace)
    lock_path = _session_push_lock_path(repo_root, session_name, workspace)
    with _locked_file(lock_path):
        payload = _load_session_state(repo_root, session_name, workspace)
        if str(payload.get("last_claimed_msg_id") or "").strip() == candidate:
            return False
        payload["last_claimed_msg_id"] = candidate
        payload["last_claimed_at"] = time.time()
        _write_json_atomic(path, payload)
        return True


def _jwt_token(private_pem: str, endpoint: str, subject: str) -> str:
    parsed = urlparse(endpoint)
    aud = f"{parsed.scheme}://{parsed.netloc}"
    header = {"typ": "JWT", "alg": "ES256"}
    payload = {
        "aud": aud,
        "exp": int(time.time()) + 12 * 60 * 60,
        "sub": subject,
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    private_key = serialization.load_pem_private_key(private_pem.encode("utf-8"), password=None)
    der_sig = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_sig)
    jose_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{header_b64}.{payload_b64}.{_b64url_encode(jose_sig)}"


def _encrypt_push_payload(payload: bytes, p256dh: str, auth: str) -> tuple[bytes, bytes]:
    user_public_bytes = _b64url_decode(p256dh)
    auth_secret = _b64url_decode(auth)
    if len(user_public_bytes) != 65 or not auth_secret:
        raise ValueError("invalid subscription keys")

    user_public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), user_public_bytes)
    server_private_key = ec.generate_private_key(ec.SECP256R1())
    server_public_bytes = _ec_public_key_bytes(server_private_key.public_key())
    shared_secret = server_private_key.exchange(ec.ECDH(), user_public_key)

    prk_key = _hkdf_extract(auth_secret, shared_secret)
    key_info = b"WebPush: info\x00" + user_public_bytes + server_public_bytes
    ikm = _hkdf_expand(prk_key, key_info, 32)

    salt = os.urandom(16)
    prk = _hkdf_extract(salt, ikm)
    cek = _hkdf_expand(prk, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf_expand(prk, b"Content-Encoding: nonce\x00", 12)

    record_size = 4096
    plaintext = payload + b"\x02"
    if len(plaintext) + 16 > record_size:
        raise ValueError("push payload too large")
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext, b"")
    header = salt + record_size.to_bytes(4, "big") + bytes([len(server_public_bytes)]) + server_public_bytes
    return header + ciphertext, server_public_bytes


def _post_web_push(endpoint: str, body: bytes, token: str, vapid_public_key: str) -> tuple[int, str]:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("unsupported push endpoint scheme")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    headers = {
        "TTL": "300",
        "Content-Type": "application/octet-stream",
        "Content-Encoding": "aes128gcm",
        "Authorization": f"vapid t={token}, k={vapid_public_key}",
        "Urgency": "normal",
        "Content-Length": str(len(body)),
    }
    connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    kwargs = {"timeout": 10}
    if parsed.scheme == "https":
        kwargs["context"] = ssl.create_default_context()
    conn = connection_cls(parsed.hostname, parsed.port, **kwargs)
    try:
        conn.request("POST", path, body=body, headers=headers)
        response = conn.getresponse()
        raw_body = response.read(2048)
        return int(response.status), raw_body.decode("utf-8", errors="replace")
    finally:
        conn.close()


def send_web_push_notifications(
    repo_root: Path | str,
    session_name: str,
    workspace: str,
    payload: dict,
    *,
    subject: str = "mailto:push@multiagent.local",
) -> dict:
    subscriptions = load_push_subscriptions(repo_root, session_name, workspace)
    if not subscriptions:
        return {"sent": 0, "failed": 0, "gone": 0}

    vapid = ensure_vapid_keypair(repo_root)
    message = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sent = 0
    failed = 0
    gone_endpoints: list[str] = []

    for subscription in subscriptions:
        endpoint = subscription["endpoint"]
        try:
            body, _server_public = _encrypt_push_payload(
                message,
                subscription["keys"]["p256dh"],
                subscription["keys"]["auth"],
            )
            token = _jwt_token(vapid["private_pem"], endpoint, subject)
            status, _response_body = _post_web_push(endpoint, body, token, vapid["public_key"])
            if status in (201, 202):
                sent += 1
            elif status in (404, 410):
                gone_endpoints.append(endpoint)
            else:
                failed += 1
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            failed += 1

    for endpoint in gone_endpoints:
        try:
            remove_push_subscription(repo_root, session_name, workspace, endpoint)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)

    return {"sent": sent, "failed": failed, "gone": len(gone_endpoints)}


def send_hub_web_push_notifications(
    repo_root: Path | str,
    payload: dict,
    *,
    subject: str = "mailto:push@multiagent.local",
) -> dict:
    subscriptions = load_hub_push_subscriptions(repo_root)
    if not subscriptions:
        return {"sent": 0, "failed": 0, "gone": 0}

    vapid = ensure_vapid_keypair(repo_root)
    message = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sent = 0
    failed = 0
    gone_endpoints: list[str] = []

    for subscription in subscriptions:
        endpoint = subscription["endpoint"]
        try:
            body, _server_public = _encrypt_push_payload(
                message,
                subscription["keys"]["p256dh"],
                subscription["keys"]["auth"],
            )
            token = _jwt_token(vapid["private_pem"], endpoint, subject)
            status, _response_body = _post_web_push(endpoint, body, token, vapid["public_key"])
            if status in (201, 202):
                sent += 1
            elif status in (404, 410):
                gone_endpoints.append(endpoint)
            else:
                failed += 1
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            failed += 1

    for endpoint in gone_endpoints:
        try:
            remove_hub_push_subscription(repo_root, endpoint)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)

    return {"sent": sent, "failed": failed, "gone": len(gone_endpoints)}


class SessionPushMonitor:
    def __init__(
        self,
        *,
        repo_root: Path | str,
        session_name: str,
        workspace: str,
        index_path: Path | str,
        settings_loader: Callable[[], dict],
    ):
        self.repo_root = Path(repo_root).resolve()
        self.session_name = str(session_name or "")
        self.workspace = str(workspace or "")
        self.index_path = Path(index_path)
        self.settings_loader = settings_loader
        self._lock = threading.Lock()
        self._presence: dict[str, dict] = {}
        self._position = self.index_path.stat().st_size if self.index_path.exists() else 0

    def record_presence(
        self,
        client_id: str,
        *,
        visible: bool,
        focused: bool,
        endpoint: str = "",
    ) -> None:
        key = str(client_id or "").strip()
        if not key:
            return
        now_ts = time.time()
        with self._lock:
            self._presence[key] = {
                "visible": bool(visible),
                "focused": bool(focused),
                "endpoint": str(endpoint or "").strip(),
                "updated_at": now_ts,
            }
            self._prune_presence(now_ts)

    def _prune_presence(self, now_ts: float | None = None) -> None:
        cutoff = float(now_ts if now_ts is not None else time.time()) - 45.0
        stale = [key for key, meta in self._presence.items() if float(meta.get("updated_at") or 0) < cutoff]
        for key in stale:
            self._presence.pop(key, None)

    def has_recent_foreground_presence(self) -> bool:
        now_ts = time.time()
        with self._lock:
            self._prune_presence(now_ts)
            return any(
                bool(meta.get("visible")) and bool(meta.get("focused"))
                for meta in self._presence.values()
            )

    def _notification_body(self, entry: dict) -> str:
        raw = re.sub(r"\[Attached:[^\]]*\]", " ", str(entry.get("message") or ""))
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            return "New agent reply"
        return f"{raw[:157]}..." if len(raw) > 160 else raw

    def _push_payload(self, entries: list[dict]) -> dict:
        agent_entries = [
            entry for entry in entries
            if str(entry.get("sender") or "").strip().lower() not in {"", "user", "system"}
        ]
        latest = agent_entries[-1]
        count = len(agent_entries)
        title = (
            f"{latest.get('sender', 'agent')} · {self.session_name}"
            if count == 1
            else f"{count} new agent replies · {self.session_name}"
        )
        return {
            "title": title,
            "body": self._notification_body(latest),
            "tag": str(latest.get("msg_id") or f"agent-reply-{int(time.time() * 1000)}"),
            "url": "./?follow=1",
            "session": self.session_name,
        }

    def _read_new_entries(self) -> list[dict]:
        if not self.index_path.exists():
            self._position = 0
            return []
        current_size = self.index_path.stat().st_size
        if current_size < self._position:
            self._position = current_size
            return []
        if current_size == self._position:
            return []
        with self.index_path.open("r", encoding="utf-8") as handle:
            handle.seek(self._position)
            chunk = handle.read()
            self._position = handle.tell()
        entries = []
        for line in chunk.splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                entries.append(item)
        return entries

    def process_once(self) -> dict:
        try:
            settings = self.settings_loader() or {}
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            settings = {}
        if not bool(settings.get("chat_browser_notifications", False)):
            self._read_new_entries()
            return {"sent": 0, "failed": 0, "gone": 0, "skipped": "disabled"}
        new_entries = self._read_new_entries()
        agent_entries = [
            entry for entry in new_entries
            if str(entry.get("sender") or "").strip().lower() not in {"", "user", "system"}
        ]
        if not agent_entries:
            return {"sent": 0, "failed": 0, "gone": 0, "skipped": "no-agent-replies"}
        if self.has_recent_foreground_presence():
            return {"sent": 0, "failed": 0, "gone": 0, "skipped": "foreground-client"}
        if load_hub_push_subscriptions(self.repo_root):
            return {"sent": 0, "failed": 0, "gone": 0, "skipped": "hub-managed"}
        subscriptions = load_push_subscriptions(self.repo_root, self.session_name, self.workspace)
        if not subscriptions:
            return {"sent": 0, "failed": 0, "gone": 0, "skipped": "no-subscriptions"}
        latest_msg_id = str(agent_entries[-1].get("msg_id") or "").strip()
        if latest_msg_id and not claim_push_notification(self.repo_root, self.session_name, self.workspace, latest_msg_id):
            return {"sent": 0, "failed": 0, "gone": 0, "skipped": "already-claimed"}
        return send_web_push_notifications(
            self.repo_root,
            self.session_name,
            self.workspace,
            self._push_payload(agent_entries),
        )

    def run_forever(self, *, interval: float = 1.0) -> None:
        while True:
            try:
                self.process_once()
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
            time.sleep(interval)


class HubPushMonitor:
    def __init__(
        self,
        *,
        repo_root: Path | str,
        settings_loader: Callable[[], dict],
        sessions_provider: Callable[[], list[dict]],
    ):
        self.repo_root = Path(repo_root).resolve()
        self.settings_loader = settings_loader
        self.sessions_provider = sessions_provider
        self._positions: dict[str, int] = {}
        self._presence: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._seed_positions()

    def _seed_positions(self) -> None:
        for session in self.sessions_provider() or []:
            index_path = Path(str(session.get("index_path") or "")).resolve() if session.get("index_path") else None
            if not index_path or not index_path.exists():
                continue
            self._positions[session.get("name") or str(index_path)] = index_path.stat().st_size

    def record_presence(
        self,
        client_id: str,
        *,
        visible: bool,
        focused: bool,
        endpoint: str = "",
    ) -> None:
        key = str(client_id or "").strip()
        if not key:
            return
        now_ts = time.time()
        with self._lock:
            self._presence[key] = {
                "visible": bool(visible),
                "focused": bool(focused),
                "endpoint": str(endpoint or "").strip(),
                "updated_at": now_ts,
            }
            self._prune_presence(now_ts)

    def _prune_presence(self, now_ts: float | None = None) -> None:
        cutoff = float(now_ts if now_ts is not None else time.time()) - 45.0
        stale = [key for key, meta in self._presence.items() if float(meta.get("updated_at") or 0) < cutoff]
        for key in stale:
            self._presence.pop(key, None)

    def has_recent_foreground_presence(self) -> bool:
        now_ts = time.time()
        with self._lock:
            self._prune_presence(now_ts)
            return any(bool(meta.get("visible")) and bool(meta.get("focused")) for meta in self._presence.values())

    def _read_new_entries(self, session_name: str, index_path: Path) -> list[dict]:
        key = session_name or str(index_path)
        if not index_path.exists():
            self._positions[key] = 0
            return []
        previous = self._positions.get(key)
        if previous is None:
            self._positions[key] = index_path.stat().st_size
            return []
        current_size = index_path.stat().st_size
        if current_size < previous:
            self._positions[key] = current_size
            return []
        if current_size == previous:
            return []
        with index_path.open("r", encoding="utf-8") as handle:
            handle.seek(previous)
            chunk = handle.read()
            self._positions[key] = handle.tell()
        entries = []
        for line in chunk.splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                entries.append(item)
        return entries

    def _notification_body(self, entry: dict) -> str:
        raw = re.sub(r"\[Attached:[^\]]*\]", " ", str(entry.get("message") or ""))
        raw = re.sub(r"^\[From:\s*[^\]]+\]\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            return "New agent reply"
        return f"{raw[:157]}..." if len(raw) > 160 else raw

    def _build_payload(self, session: dict, entries: list[dict]) -> dict:
        agent_entries = [
            entry for entry in entries
            if str(entry.get("sender") or "").strip().lower() not in {"", "user", "system"}
        ]
        latest = agent_entries[-1]
        count = len(agent_entries)
        session_name = str(session.get("name") or "session")
        title = (
            f"{latest.get('sender', 'agent')} · {session_name}"
            if count == 1
            else f"{count} new agent replies · {session_name}"
        )
        session_slug = quote(session_name, safe="")
        return {
            "title": title,
            "body": self._notification_body(latest),
            "tag": f"{session_name}:{latest.get('msg_id') or int(time.time() * 1000)}",
            "url": f"/session/{session_slug}/?follow=1",
            "session": session_name,
        }

    def process_once(self) -> dict:
        try:
            settings = self.settings_loader() or {}
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            settings = {}
        if not bool(settings.get("chat_browser_notifications", False)):
            for session in self.sessions_provider() or []:
                index_path = str(session.get("index_path") or "")
                if index_path:
                    self._read_new_entries(str(session.get("name") or ""), Path(index_path))
            return {"sent": 0, "failed": 0, "gone": 0, "skipped": "disabled"}
        if self.has_recent_foreground_presence():
            for session in self.sessions_provider() or []:
                index_path = str(session.get("index_path") or "")
                if index_path:
                    self._read_new_entries(str(session.get("name") or ""), Path(index_path))
            return {"sent": 0, "failed": 0, "gone": 0, "skipped": "foreground-hub"}

        sent = failed = gone = 0
        for session in self.sessions_provider() or []:
            index_path_raw = str(session.get("index_path") or "").strip()
            if not index_path_raw:
                continue
            index_path = Path(index_path_raw)
            entries = self._read_new_entries(str(session.get("name") or ""), index_path)
            agent_entries = [
                entry for entry in entries
                if str(entry.get("sender") or "").strip().lower() not in {"", "user", "system"}
            ]
            if not agent_entries:
                continue
            result = send_hub_web_push_notifications(self.repo_root, self._build_payload(session, agent_entries))
            sent += int(result.get("sent") or 0)
            failed += int(result.get("failed") or 0)
            gone += int(result.get("gone") or 0)
        return {"sent": sent, "failed": failed, "gone": gone}

    def run_forever(self, *, interval: float = 1.0) -> None:
        while True:
            try:
                self.process_once()
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
            time.sleep(interval)
