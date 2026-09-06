from __future__ import annotations

import hashlib
from pathlib import Path

from backend_core.agents.registry import agent_names_js_set, agent_names_js_array
from .script_assets import (
    CHAT_ANSI_UP_HEAD_TAG,
    CHAT_HEADER_ACTIONS_HTML,
    CHAT_HEADER_ACTIONS_HTML_MOBILE,
    CHAT_SHEET_PANELS_HTML,
    CHAT_KATEX_HEAD_TAGS,
)
from .render import apply_chat_template_replacements, build_chat_template_replacements
from .template_loader import load_chat_template
from appearance.colors import apply_color_tokens
from appearance.theme import MOBILE_THEME_SETTING
from appearance.typography import DESKTOP_TEXT_SIZE, apply_font_tokens, chat_font_style
from hub_backend.branding import APP_DISPLAY_NAME
from ..hub.header_assets import PAGE_HEADER_CSS, render_page_header

_REPO_ROOT = Path(__file__).resolve().parents[3]


CHAT_DESKTOP_HTML = load_chat_template("desktop")
CHAT_MOBILE_HTML = load_chat_template("mobile")
_CHAT_PWA_STATIC_DIR = _REPO_ROOT / "apps" / "shared" / "pwa"


def _chat_pwa_asset_version(filename: str) -> str:
    try:
        return hashlib.sha256((_CHAT_PWA_STATIC_DIR / filename).read_bytes()).hexdigest()[:12]
    except Exception:
        return "0"


def _chat_pwa_asset_url(path: str, filename: str, chat_base_path: str = "") -> str:
    base_path = chat_base_path.rstrip("/")
    asset_path = f"{base_path}{path}" if base_path else path
    version = _chat_pwa_asset_version(filename)
    sep = "&" if "?" in asset_path else "?"
    return f"{asset_path}{sep}v={version}"


def render_chat_service_worker_html() -> str:
    # CHAT_BASE_PATH is declared by the main app script, which always
    # precedes this block in the page -- classic (non-module) <script> tags
    # share one top-level lexical scope, so a later tag can read an earlier
    # tag's const/let bindings directly.
    return (
        "  <script>\n"
        "    (() => {\n"
        "      if (!(\"serviceWorker\" in navigator)) return;\n"
        "      const isLocalHost = location.hostname === \"localhost\" || location.hostname === \"127.0.0.1\" || location.hostname === \"[::1]\";\n"
        "      if (!(window.isSecureContext || isLocalHost)) return;\n"
        "      const basePath = CHAT_BASE_PATH.replace(/\\/$/, \"\");\n"
        "      const scriptUrl = `${basePath}/service-worker.js`;\n"
        "      const scope = `${basePath || \"\"}/` || \"/\";\n"
        "      window.addEventListener(\"load\", () => {\n"
        "        navigator.serviceWorker.register(scriptUrl, { scope }).catch((err) => {\n"
        "          console.warn(\"chat service worker registration failed\", err);\n"
        "        });\n"
        "      }, { once: true });\n"
        "    })();\n"
        "  </script>"
    )


def _agent_css_selectors() -> dict[str, str]:
    def _sel(suffix="", prefix=""):
        return f"    {prefix}.message:not(.user):not(.system){suffix}"
    def _row_sel(inner):
        return f"    .message-row:not(.user):not(.system) {inner}"
    def _cross(suffixes, prefix=""):
        parts = [f"    {prefix}.message:not(.user):not(.system) .md-body {s}" for s in suffixes]
        return ",\n".join(parts)
    return {
        "__AGENT_MESSAGE_SELECTORS__": _sel(),
        "__AGENT_ROW_MESSAGE_SELECTORS__": _row_sel(".message"),
        "__AGENT_ROW_META_SELECTORS__": _row_sel(".meta"),
        "__AGENT_SEL_MD_BODY__": _sel(" .md-body"),
        "__AGENT_SEL_MD_HEADING__": _cross(["h1", "h2", "h3", "h4"]),
        "__AGENT_SEL_MD_BODY_TEXT__": _cross(["p", "li", "blockquote"]),
        "__AGENT_ICON_NAMES_JS_SET__": agent_names_js_set(),
        "__ALL_BASE_AGENTS_JS_ARRAY__": agent_names_js_array(),
    }


def _normalized_chat_variant(variant: str = "desktop") -> str:
    return "mobile" if str(variant or "").strip().lower() == "mobile" else "desktop"


def _chat_html(variant: str = "desktop") -> str:
    return CHAT_MOBILE_HTML if _normalized_chat_variant(variant) == "mobile" else CHAT_DESKTOP_HTML


def render_chat_html(
    *,
    icon_data_uris,
    server_instance,
    hub_port,
    chat_base_path="",
    eager_optional_vendors=True,
    variant="desktop",
    session_name="",
    theme="dark",
    text_size=DESKTOP_TEXT_SIZE,
):
    normalized_variant = _normalized_chat_variant(variant)
    base_path = chat_base_path.rstrip("/")
    normalized_session_name = str(session_name or "").strip()
    chat_document_title = f"{normalized_session_name} · {APP_DISPLAY_NAME}" if normalized_session_name else APP_DISPLAY_NAME
    actions_html = CHAT_HEADER_ACTIONS_HTML_MOBILE if normalized_variant == "mobile" else CHAT_HEADER_ACTIONS_HTML
    panels_html = CHAT_SHEET_PANELS_HTML if normalized_variant == "mobile" else ""
    chat_header_html = render_page_header(
        title_href="/",
        title_id="pageTitleLink",
        actions_html=actions_html,
        panels_html=panels_html,
    )
    html = _chat_html(normalized_variant)
    if not eager_optional_vendors:
        html = html.replace(CHAT_ANSI_UP_HEAD_TAG, "", 1)
        html = html.replace(CHAT_KATEX_HEAD_TAGS, "", 1)
    for placeholder, value in _agent_css_selectors().items():
        html = html.replace(placeholder, value)
    if "__CHAT_HEADER_HTML__" in html:
        html = html.replace("__CHAT_HEADER_HTML__", chat_header_html)
    else:
        html = html.replace('<section class="shell">', f'<section class="shell">{chat_header_html}', 1)
    replacements = build_chat_template_replacements(
        icon_data_uris=icon_data_uris,
        base_path=base_path,
        chat_manifest_url=_chat_pwa_asset_url("/app.webmanifest", "icon-192.png", base_path),
        chat_pwa_icon_192_url=_chat_pwa_asset_url("/pwa-icon-192.png", "icon-192.png", base_path),
        chat_apple_touch_icon_url=_chat_pwa_asset_url("/apple-touch-icon.png", "apple-touch-icon.png", base_path),
        chat_service_worker_html=render_chat_service_worker_html(),
        server_instance=server_instance,
        hub_port=hub_port,
        chat_font_settings_inline_style=chat_font_style(text_size=text_size),
        hub_header_css=PAGE_HEADER_CSS,
        chat_document_title=chat_document_title,
    )
    html = apply_chat_template_replacements(html, replacements)
    html = apply_font_tokens(html)
    html = apply_color_tokens(
        html,
        theme=theme,
        mobile_theme_setting=MOBILE_THEME_SETTING,
    )
    return html
