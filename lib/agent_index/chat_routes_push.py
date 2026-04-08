from __future__ import annotations

import json


def _read_json_body(handler):
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8") or "{}"), None
    except json.JSONDecodeError:
        return None, "invalid json"


def _get_push_config(handler, _parsed, ctx) -> None:
    settings = ctx["load_chat_settings_fn"]()
    handler._send_json(
        200,
        {
            "enabled": bool(settings.get("chat_browser_notifications", False)),
            "public_key": ctx["vapid_public_key_fn"](ctx["repo_root"]),
        },
    )


def _post_push_subscribe(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    try:
        result = ctx["upsert_push_subscription_fn"](
            ctx["repo_root"],
            ctx["session_name"],
            ctx["workspace"],
            data.get("subscription") or {},
            client_id=str(data.get("client_id") or "").strip(),
            user_agent=str(data.get("user_agent") or "").strip(),
        )
    except ValueError as exc:
        handler._send_json(400, {"ok": False, "error": str(exc)})
        return
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    endpoint = str((data.get("subscription") or {}).get("endpoint") or "").strip()
    if endpoint:
        try:
            ctx["push_monitor"].record_presence(
                str(data.get("client_id") or "").strip(),
                visible=not bool(data.get("hidden", False)),
                focused=not bool(data.get("hidden", False)),
                endpoint=endpoint,
            )
        except Exception:
            pass
    handler._send_json(200, {"ok": True, **result})


def _post_push_unsubscribe(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    endpoint = str(data.get("endpoint") or "").strip()
    if not endpoint:
        handler._send_json(400, {"ok": False, "error": "endpoint required"})
        return
    try:
        removed = ctx["remove_push_subscription_fn"](
            ctx["repo_root"],
            ctx["session_name"],
            ctx["workspace"],
            endpoint,
        )
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    handler._send_json(200, {"ok": True, "removed": bool(removed)})


def _post_push_presence(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    client_id = str(data.get("client_id") or "").strip()
    if not client_id:
        handler._send_json(400, {"ok": False, "error": "client_id required"})
        return
    try:
        ctx["push_monitor"].record_presence(
            client_id,
            visible=bool(data.get("visible", False)),
            focused=bool(data.get("focused", False)),
            endpoint=str(data.get("endpoint") or "").strip(),
        )
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    handler._send_json(200, {"ok": True})


_GET_ROUTES = {
    "/push-config": _get_push_config,
}

_POST_ROUTES = {
    "/push/subscribe": _post_push_subscribe,
    "/push/unsubscribe": _post_push_unsubscribe,
    "/push/presence": _post_push_presence,
}


def dispatch_get_push_route(handler, parsed, ctx) -> bool:
    route = _GET_ROUTES.get(parsed.path)
    if route is None:
        return False
    route(handler, parsed, ctx)
    return True


def dispatch_post_push_route(handler, parsed, ctx) -> bool:
    route = _POST_ROUTES.get(parsed.path)
    if route is None:
        return False
    route(handler, parsed, ctx)
    return True
