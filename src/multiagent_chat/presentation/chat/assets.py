from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ...agents.registry import (
    ALL_AGENT_NAMES,
    SELECTABLE_AGENT_NAMES,
    agent_names_js_set,
    agent_names_js_array,
)
from .bootstrap import build_chat_bootstrap_payload, encode_chat_bootstrap_payload
from .script_assets import (
    CHAT_ANSI_UP_HEAD_TAG,
    CHAT_HEADER_ACTIONS_HTML,
    CHAT_HEADER_PANELS_HTML,
    CHAT_KATEX_HEAD_TAGS,
    build_chat_app_script_assets,
)
from .render import apply_chat_template_replacements, build_chat_template_replacements
from .template_loader import load_chat_template
from ...color_constants import apply_color_tokens
from ..desktop_app_assets import DESKTOP_APP_CHAT_CSS, DESKTOP_APP_CHAT_JS
from ..hub.header_assets import HUB_PAGE_HEADER_CSS, render_hub_page_header

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CHAT_TEMPLATE_DIR = Path(__file__).resolve().parent


CHAT_DESKTOP_HTML = load_chat_template("desktop")
CHAT_MOBILE_HTML = load_chat_template("mobile")
CHAT_HTML = CHAT_DESKTOP_HTML
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


def _normalized_chat_client(client: str = "", *, variant: str = "desktop") -> str:
    normalized_variant = _normalized_chat_variant(variant)
    lowered = str(client or "").strip().lower()
    if normalized_variant == "mobile":
        return "mobile-web"
    if lowered in {"desktop-app", "tauri", "tauri-app"}:
        return "desktop-app"
    return "desktop-web"


def _chat_client_css(*, variant: str = "desktop", client: str = "") -> str:
    normalized_client = _normalized_chat_client(client, variant=variant)
    if normalized_client == "desktop-app":
        return DESKTOP_APP_CHAT_CSS
    return ""


def _chat_client_js(*, variant: str = "desktop", client: str = "") -> str:
    normalized_client = _normalized_chat_client(client, variant=variant)
    if normalized_client == "desktop-app":
        return DESKTOP_APP_CHAT_JS
    return ""


def render_chat_app_bootstrap_html(*, icon_data_uris, server_instance, hub_port, chat_settings, chat_base_path="", client_variant="desktop-web") -> str:
    payload = build_chat_bootstrap_payload(
        icon_data_uris=icon_data_uris,
        server_instance=server_instance,
        hub_port=hub_port,
        chat_settings=chat_settings,
        chat_base_path=chat_base_path,
        agent_icon_names=list(ALL_AGENT_NAMES),
        all_base_agents=list(SELECTABLE_AGENT_NAMES),
        client_variant=client_variant,
    )
    payload_json = encode_chat_bootstrap_payload(payload)
    return (
        f"  <script>window.__CHAT_BOOTSTRAP__ = {payload_json};</script>\n"
        "  <script>\n"
        "    (() => {\n"
        "      if (!(\"serviceWorker\" in navigator)) return;\n"
        "      const isLocalHost = location.hostname === \"localhost\" || location.hostname === \"127.0.0.1\" || location.hostname === \"[::1]\";\n"
        "      if (!(window.isSecureContext || isLocalHost)) return;\n"
        "      const basePath = (window.__CHAT_BOOTSTRAP__ && typeof window.__CHAT_BOOTSTRAP__.basePath === \"string\")\n"
        "        ? window.__CHAT_BOOTSTRAP__.basePath.replace(/\\/$/, \"\")\n"
        "        : \"\";\n"
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


def _agent_css_selectors(theme: str = "black-hole") -> dict[str, str]:
    def _sel(suffix="", prefix=""):
        return f"    {prefix}.message:not(.user):not(.system){suffix}"
    def _row_sel(inner):
        return f"    .message-row:not(.user):not(.system) {inner}"
    def _cross(suffixes, prefix=""):
        parts = [f"    {prefix}.message:not(.user):not(.system) .md-body {s}" for s in suffixes]
        return ",\n".join(parts)
    gothic = 'html[data-agent-font-mode="gothic"] '
    return {
        "__AGENT_MESSAGE_SELECTORS__": _sel(),
        "__AGENT_ROW_MESSAGE_SELECTORS__": _row_sel(".message"),
        "__AGENT_ROW_META_SELECTORS__": _row_sel(".meta"),
        "__AGENT_SEL_MD_BODY__": _sel(" .md-body"),
        "__AGENT_SEL_MD_HEADING__": _cross(["p", "li", "h1", "h2", "h3", "h4"]),
        "__AGENT_SEL_MD_BODY_TEXT__": _cross(["p", "li", "blockquote"]),
        "__AGENT_SEL_MD_BODY_LI__": _sel(" .md-body li"),
        "__AGENT_SEL_GOTHIC_MD_BODY__": _sel(" .md-body", prefix=gothic),
        "__AGENT_SEL_GOTHIC_MD_DETAIL__": _cross(["p", "li", "blockquote"], prefix=gothic),
        "__AGENT_SEL_GOTHIC_MD_HEADING__": _cross(["h1", "h2", "h3", "h4"], prefix=gothic),
        "__AGENT_SEL_GOTHIC_MD_LI__": _sel(" .md-body li", prefix=gothic),
        "__AGENT_ICON_NAMES_JS_SET__": agent_names_js_set(),
        "__ALL_BASE_AGENTS_JS_ARRAY__": agent_names_js_array(),
    }


_CHAT_MAIN_STYLE_OPEN = "  <style>\n"
_CHAT_MAIN_STYLE_CLOSE = "  </style>\n"


@dataclass(frozen=True)
class _ChatAssetVariant:
    html: str
    app_script_block: str
    app_script_template: str
    app_script_asset: str
    app_script_version: str
    main_style_block: str
    main_style_template: str
    main_style_asset: str
    main_style_version: str


def _normalized_chat_variant(variant: str = "desktop") -> str:
    return "mobile" if str(variant or "").strip().lower() == "mobile" else "desktop"


def _build_chat_asset_variant(html: str, *, variant: str = "desktop", client: str = "") -> _ChatAssetVariant:
    normalized_variant = _normalized_chat_variant(variant)
    normalized_client = _normalized_chat_client(client, variant=normalized_variant)
    app_assets = build_chat_app_script_assets(html)
    main_style_start = html.find(_CHAT_MAIN_STYLE_OPEN)
    if main_style_start < 0:
        raise ValueError("chat main style block not found")
    main_style_end = html.find(_CHAT_MAIN_STYLE_CLOSE, main_style_start)
    if main_style_end < 0:
        raise ValueError("chat main style close tag not found")
    main_style_block = html[main_style_start:main_style_end + len(_CHAT_MAIN_STYLE_CLOSE)]
    main_style_template = html[main_style_start + len(_CHAT_MAIN_STYLE_OPEN):main_style_end]
    main_style_asset = main_style_template
    for font_name in (
        "anthropic-serif-roman.ttf",
        "anthropic-serif-italic.ttf",
        "anthropic-sans-roman.ttf",
        "anthropic-sans-italic.ttf",
        "jetbrains-mono.ttf",
    ):
        main_style_asset = main_style_asset.replace(
            f'"__CHAT_BASE_PATH__/font/{font_name}"',
            f'"../font/{font_name}"',
        )
    extra_css = _chat_client_css(variant=normalized_variant, client=normalized_client)
    if extra_css:
        main_style_asset = f"{main_style_asset.rstrip()}\n{extra_css}"
    app_script_asset = app_assets.asset
    extra_js = _chat_client_js(variant=normalized_variant, client=normalized_client)
    if extra_js:
        app_script_asset = f"{app_script_asset.rstrip()}\n{extra_js}"
    for placeholder, value in {
        **_agent_css_selectors(),
        "__HUB_HEADER_CSS__": HUB_PAGE_HEADER_CSS,
    }.items():
        main_style_asset = main_style_asset.replace(placeholder, value)
    return _ChatAssetVariant(
        html=html,
        app_script_block=app_assets.block,
        app_script_template=app_assets.template,
        app_script_asset=app_script_asset,
        app_script_version=hashlib.sha256(app_script_asset.encode("utf-8")).hexdigest()[:12],
        main_style_block=main_style_block,
        main_style_template=main_style_template,
        main_style_asset=main_style_asset,
        main_style_version=hashlib.sha256(main_style_asset.encode("utf-8")).hexdigest()[:12],
    )


_CHAT_VARIANTS = {
    ("desktop", "desktop-web"): _build_chat_asset_variant(CHAT_DESKTOP_HTML, variant="desktop", client="desktop-web"),
    ("desktop", "desktop-app"): _build_chat_asset_variant(CHAT_DESKTOP_HTML, variant="desktop", client="desktop-app"),
    ("mobile", "mobile-web"): _build_chat_asset_variant(CHAT_MOBILE_HTML, variant="mobile", client="mobile-web"),
}


def _chat_variant(variant: str = "desktop", client: str = "") -> _ChatAssetVariant:
    normalized_variant = _normalized_chat_variant(variant)
    normalized_client = _normalized_chat_client(client, variant=normalized_variant)
    return _CHAT_VARIANTS[(normalized_variant, normalized_client)]


CHAT_APP_SCRIPT_BLOCK = _CHAT_VARIANTS[("desktop", "desktop-web")].app_script_block
CHAT_APP_SCRIPT_TEMPLATE = _CHAT_VARIANTS[("desktop", "desktop-web")].app_script_template
CHAT_APP_SCRIPT_ASSET = _CHAT_VARIANTS[("desktop", "desktop-web")].app_script_asset
CHAT_APP_SCRIPT_VERSION = _CHAT_VARIANTS[("desktop", "desktop-web")].app_script_version
CHAT_MAIN_STYLE_BLOCK = _CHAT_VARIANTS[("desktop", "desktop-web")].main_style_block
CHAT_MAIN_STYLE_TEMPLATE = _CHAT_VARIANTS[("desktop", "desktop-web")].main_style_template
CHAT_MAIN_STYLE_ASSET = _CHAT_VARIANTS[("desktop", "desktop-web")].main_style_asset
CHAT_MAIN_STYLE_VERSION = _CHAT_VARIANTS[("desktop", "desktop-web")].main_style_version

CHAT_MOBILE_APP_SCRIPT_BLOCK = _CHAT_VARIANTS[("mobile", "mobile-web")].app_script_block
CHAT_MOBILE_APP_SCRIPT_TEMPLATE = _CHAT_VARIANTS[("mobile", "mobile-web")].app_script_template
CHAT_MOBILE_APP_SCRIPT_ASSET = _CHAT_VARIANTS[("mobile", "mobile-web")].app_script_asset
CHAT_MOBILE_APP_SCRIPT_VERSION = _CHAT_VARIANTS[("mobile", "mobile-web")].app_script_version
CHAT_MOBILE_MAIN_STYLE_BLOCK = _CHAT_VARIANTS[("mobile", "mobile-web")].main_style_block
CHAT_MOBILE_MAIN_STYLE_TEMPLATE = _CHAT_VARIANTS[("mobile", "mobile-web")].main_style_template
CHAT_MOBILE_MAIN_STYLE_ASSET = _CHAT_VARIANTS[("mobile", "mobile-web")].main_style_asset
CHAT_MOBILE_MAIN_STYLE_VERSION = _CHAT_VARIANTS[("mobile", "mobile-web")].main_style_version


def chat_app_script_asset(variant: str = "desktop", client: str = "") -> str:
    return _chat_variant(variant, client).app_script_asset


def chat_main_style_asset(variant: str = "desktop", client: str = "") -> str:
    return _chat_variant(variant, client).main_style_asset


def chat_style_asset_url(chat_base_path: str = "", *, variant: str = "desktop", client: str = "") -> str:
    normalized_variant = _normalized_chat_variant(variant)
    normalized_client = _normalized_chat_client(client, variant=normalized_variant)
    base_path = chat_base_path.rstrip("/")
    asset_path = f"{base_path}/chat-assets/chat-app.css" if base_path else "/chat-assets/chat-app.css"
    return f"{asset_path}?v={_chat_variant(normalized_variant, normalized_client).main_style_version}&view={normalized_variant}&client={normalized_client}"


def chat_app_asset_url(chat_base_path: str = "", *, variant: str = "desktop", client: str = "") -> str:
    normalized_variant = _normalized_chat_variant(variant)
    normalized_client = _normalized_chat_client(client, variant=normalized_variant)
    base_path = chat_base_path.rstrip("/")
    asset_path = f"{base_path}/chat-assets/chat-app.js" if base_path else "/chat-assets/chat-app.js"
    return f"{asset_path}?v={_chat_variant(normalized_variant, normalized_client).app_script_version}&view={normalized_variant}&client={normalized_client}"


def render_chat_html(*, icon_data_uris, server_instance, hub_port, chat_settings, agent_font_mode_inline_style, follow, chat_base_path="", externalize_app_script=False, externalize_main_style=False, eager_optional_vendors=True, variant="desktop", client=""):
    normalized_variant = _normalized_chat_variant(variant)
    normalized_client = _normalized_chat_client(client, variant=normalized_variant)
    asset_variant = _chat_variant(normalized_variant, normalized_client)
    base_path = chat_base_path.rstrip("/")
    chat_header_html = render_hub_page_header(
        title_href="/",
        title_id="hubPageTitleLink",
        title_aria_label="Hub",
        title_alt="Hub",
        actions_html=CHAT_HEADER_ACTIONS_HTML,
        panels_html=CHAT_HEADER_PANELS_HTML,
    )
    html = asset_variant.html
    if asset_variant.main_style_asset != asset_variant.main_style_template:
        html = html.replace(
            asset_variant.main_style_block,
            f"  <style>\n{asset_variant.main_style_asset}  </style>\n",
            1,
        )
    if asset_variant.app_script_asset != asset_variant.app_script_template:
        html = html.replace(
            asset_variant.app_script_block,
            f"  <script>\n{asset_variant.app_script_asset}  </script>\n",
            1,
        )
    if not eager_optional_vendors:
        html = html.replace(CHAT_ANSI_UP_HEAD_TAG, "", 1)
        html = html.replace(CHAT_KATEX_HEAD_TAGS, "", 1)
    if externalize_main_style:
        html = html.replace(
            asset_variant.main_style_block,
            '  <link rel="stylesheet" href="__CHAT_STYLE_ASSET_URL__">\n',
            1,
        )
    if externalize_app_script:
        html = html.replace(
            asset_variant.app_script_block,
            "__CHAT_APP_BOOTSTRAP__\n  <script src=\"__CHAT_APP_ASSET_URL__\"></script>\n",
            1,
        )
    current_theme = str(chat_settings.get("theme", "black-hole") or "black-hole")
    for placeholder, value in _agent_css_selectors(current_theme).items():
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
        chat_style_asset_url=chat_style_asset_url(base_path, variant=normalized_variant, client=normalized_client) if externalize_main_style else "",
        chat_app_bootstrap_html=(
            render_chat_app_bootstrap_html(
                icon_data_uris=icon_data_uris,
                server_instance=server_instance,
                hub_port=hub_port,
                chat_settings=chat_settings,
                chat_base_path=base_path,
                client_variant=normalized_client,
            )
            if externalize_app_script
            else ""
        ),
        chat_app_asset_url=chat_app_asset_url(base_path, variant=normalized_variant, client=normalized_client) if externalize_app_script else "",
        server_instance=server_instance,
        hub_port=hub_port,
        chat_settings=chat_settings,
        agent_font_mode_inline_style=agent_font_mode_inline_style(chat_settings),
        hub_header_css=HUB_PAGE_HEADER_CSS,
    )
    html = apply_chat_template_replacements(html, replacements)
    html = apply_color_tokens(html, settings=chat_settings)
    return html.replace("mode: snapshot", f"mode: {'follow' if follow == '1' else 'snapshot'}")
