from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .agent_registry import (
    ALL_AGENT_NAMES,
    SELECTABLE_AGENT_NAMES,
    agent_names_js_set,
    agent_names_js_array,
)
from .chat_bootstrap_core import build_chat_bootstrap_payload, encode_chat_bootstrap_payload
from .chat_assets_script_core import (
    CHAT_ANSI_UP_HEAD_TAG,
    CHAT_HEADER_ACTIONS_HTML,
    CHAT_HEADER_PANELS_HTML,
    CHAT_KATEX_HEAD_TAGS,
    build_chat_app_script_assets,
)
from .chat_pane_trace_core import build_pane_trace_view_model
from .chat_render_core import apply_chat_template_replacements, build_chat_template_replacements
from .hub_header_assets import HUB_PAGE_HEADER_CSS, render_hub_page_header

_CHAT_TEMPLATE_DIR = Path(__file__).resolve().parent


def _read_chat_template(filename: str) -> str:
    path = _CHAT_TEMPLATE_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Chat template not found: {path}")
    return path.read_text()


CHAT_DESKTOP_HTML = _read_chat_template("chat_template_desktop.html")
CHAT_MOBILE_HTML = _read_chat_template("chat_template_mobile.html")
CHAT_HTML = CHAT_DESKTOP_HTML
_CHAT_PWA_STATIC_DIR = _CHAT_TEMPLATE_DIR / "static" / "pwa"


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


def render_chat_app_bootstrap_html(*, icon_data_uris, server_instance, hub_port, chat_settings, chat_base_path="") -> str:
    payload = build_chat_bootstrap_payload(
        icon_data_uris=icon_data_uris,
        server_instance=server_instance,
        hub_port=hub_port,
        chat_settings=chat_settings,
        chat_base_path=chat_base_path,
        agent_icon_names=list(ALL_AGENT_NAMES),
        all_base_agents=list(SELECTABLE_AGENT_NAMES),
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
    """Generate CSS selector placeholders for agent message styling."""
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


def _build_chat_asset_variant(html: str) -> _ChatAssetVariant:
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
    for placeholder, value in {
        **_agent_css_selectors(),
        "__HUB_HEADER_CSS__": HUB_PAGE_HEADER_CSS,
    }.items():
        main_style_asset = main_style_asset.replace(placeholder, value)
    return _ChatAssetVariant(
        html=html,
        app_script_block=app_assets.block,
        app_script_template=app_assets.template,
        app_script_asset=app_assets.asset,
        app_script_version=app_assets.version,
        main_style_block=main_style_block,
        main_style_template=main_style_template,
        main_style_asset=main_style_asset,
        main_style_version=hashlib.sha256(main_style_asset.encode("utf-8")).hexdigest()[:12],
    )


_CHAT_VARIANTS = {
    "desktop": _build_chat_asset_variant(CHAT_DESKTOP_HTML),
    "mobile": _build_chat_asset_variant(CHAT_MOBILE_HTML),
}


def _chat_variant(variant: str = "desktop") -> _ChatAssetVariant:
    return _CHAT_VARIANTS[_normalized_chat_variant(variant)]


CHAT_APP_SCRIPT_BLOCK = _CHAT_VARIANTS["desktop"].app_script_block
CHAT_APP_SCRIPT_TEMPLATE = _CHAT_VARIANTS["desktop"].app_script_template
CHAT_APP_SCRIPT_ASSET = _CHAT_VARIANTS["desktop"].app_script_asset
CHAT_APP_SCRIPT_VERSION = _CHAT_VARIANTS["desktop"].app_script_version
CHAT_MAIN_STYLE_BLOCK = _CHAT_VARIANTS["desktop"].main_style_block
CHAT_MAIN_STYLE_TEMPLATE = _CHAT_VARIANTS["desktop"].main_style_template
CHAT_MAIN_STYLE_ASSET = _CHAT_VARIANTS["desktop"].main_style_asset
CHAT_MAIN_STYLE_VERSION = _CHAT_VARIANTS["desktop"].main_style_version

CHAT_MOBILE_APP_SCRIPT_BLOCK = _CHAT_VARIANTS["mobile"].app_script_block
CHAT_MOBILE_APP_SCRIPT_TEMPLATE = _CHAT_VARIANTS["mobile"].app_script_template
CHAT_MOBILE_APP_SCRIPT_ASSET = _CHAT_VARIANTS["mobile"].app_script_asset
CHAT_MOBILE_APP_SCRIPT_VERSION = _CHAT_VARIANTS["mobile"].app_script_version
CHAT_MOBILE_MAIN_STYLE_BLOCK = _CHAT_VARIANTS["mobile"].main_style_block
CHAT_MOBILE_MAIN_STYLE_TEMPLATE = _CHAT_VARIANTS["mobile"].main_style_template
CHAT_MOBILE_MAIN_STYLE_ASSET = _CHAT_VARIANTS["mobile"].main_style_asset
CHAT_MOBILE_MAIN_STYLE_VERSION = _CHAT_VARIANTS["mobile"].main_style_version


def chat_app_script_asset(variant: str = "desktop") -> str:
    return _chat_variant(variant).app_script_asset


def chat_main_style_asset(variant: str = "desktop") -> str:
    return _chat_variant(variant).main_style_asset


def chat_style_asset_url(chat_base_path: str = "", *, variant: str = "desktop") -> str:
    normalized_variant = _normalized_chat_variant(variant)
    base_path = chat_base_path.rstrip("/")
    asset_path = f"{base_path}/chat-assets/chat-app.css" if base_path else "/chat-assets/chat-app.css"
    return f"{asset_path}?v={_chat_variant(normalized_variant).main_style_version}&view={normalized_variant}"


def chat_app_asset_url(chat_base_path: str = "", *, variant: str = "desktop") -> str:
    normalized_variant = _normalized_chat_variant(variant)
    base_path = chat_base_path.rstrip("/")
    asset_path = f"{base_path}/chat-assets/chat-app.js" if base_path else "/chat-assets/chat-app.js"
    return f"{asset_path}?v={_chat_variant(normalized_variant).app_script_version}&view={normalized_variant}"


def render_chat_html(*, icon_data_uris, logo_data_uri, server_instance, hub_port, chat_settings, agent_font_mode_inline_style, follow, chat_base_path="", externalize_app_script=False, externalize_main_style=False, eager_optional_vendors=True, variant="desktop"):
    normalized_variant = _normalized_chat_variant(variant)
    asset_variant = _chat_variant(normalized_variant)
    base_path = chat_base_path.rstrip("/")
    logo_src = logo_data_uri
    chat_header_html = render_hub_page_header(
        logo_data_uri=logo_src,
        title_href="/",
        title_id="hubPageTitleLink",
        title_aria_label="Hub",
        title_alt="Hub",
        actions_html=CHAT_HEADER_ACTIONS_HTML,
        panels_html=CHAT_HEADER_PANELS_HTML,
    )
    html = asset_variant.html
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
    # Replace agent-specific CSS/JS placeholders
    current_theme = str(chat_settings.get("theme", "black-hole") or "black-hole")
    for placeholder, value in _agent_css_selectors(current_theme).items():
        html = html.replace(placeholder, value)
    if "__CHAT_HEADER_HTML__" in html:
        html = html.replace("__CHAT_HEADER_HTML__", chat_header_html)
    else:
        html = html.replace('<section class="shell">', f'<section class="shell">{chat_header_html}', 1)
    replacements = build_chat_template_replacements(
        icon_data_uris=icon_data_uris,
        logo_src=logo_src,
        base_path=base_path,
        chat_manifest_url=_chat_pwa_asset_url("/app.webmanifest", "icon-192.png", base_path),
        chat_pwa_icon_192_url=_chat_pwa_asset_url("/pwa-icon-192.png", "icon-192.png", base_path),
        chat_apple_touch_icon_url=_chat_pwa_asset_url("/apple-touch-icon.png", "apple-touch-icon.png", base_path),
        chat_style_asset_url=chat_style_asset_url(base_path, variant=normalized_variant) if externalize_main_style else "",
        chat_app_bootstrap_html=(
            render_chat_app_bootstrap_html(
                icon_data_uris=icon_data_uris,
                server_instance=server_instance,
                hub_port=hub_port,
                chat_settings=chat_settings,
                chat_base_path=base_path,
            )
            if externalize_app_script
            else ""
        ),
        chat_app_asset_url=chat_app_asset_url(base_path, variant=normalized_variant) if externalize_app_script else "",
        server_instance=server_instance,
        hub_port=hub_port,
        chat_settings=chat_settings,
        agent_font_mode_inline_style=agent_font_mode_inline_style(chat_settings),
        hub_header_css=HUB_PAGE_HEADER_CSS,
    )
    html = apply_chat_template_replacements(html, replacements)
    return html.replace("mode: snapshot", f"mode: {'follow' if follow == '1' else 'snapshot'}")


def render_pane_trace_popup_html(*, agent: str, agents: list[str] | None = None, bg: str, text: str, chat_base_path: str = "") -> str:
    view_model = build_pane_trace_view_model(
        agent=agent,
        agents=agents,
        bg=bg,
        text=text,
        chat_base_path=chat_base_path,
    )
    bg_value = view_model["bg_value"]
    text_value = view_model["text_value"]
    agents_json = view_model["agents_json"]
    initial_agent_json = view_model["initial_agent_json"]
    bg_json = view_model["bg_json"]
    text_json = view_model["text_json"]
    bg_effective = view_model["bg_effective"]
    header_overlay_bg = view_model["header_overlay_bg"]
    body_fg = view_model["body_fg"]
    body_dim_fg = view_model["body_dim_fg"]
    trace_path_prefix = view_model["trace_path_prefix"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="{bg_value}">
  <title>Pane Trace</title>
  <script src="https://cdn.jsdelivr.net/npm/ansi_up@5.1.0/ansi_up.min.js"></script>
  <style>
    :root {{
      color-scheme: dark;
      --popup-bg: {bg_value};
      --popup-text: {text_value};
      --pane-trace-body-bg: {bg_effective};
      --pane-trace-body-fg: {body_fg};
      --pane-trace-body-dim-fg: {body_dim_fg};
    }}
    html, body {{
      margin: 0;
      background: var(--pane-trace-body-bg);
      color: var(--popup-text);
      height: 100%;
      font-family: "SF Mono", "SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, monospace;
      font-weight: 400;
      font-style: normal;
    }}
    body {{
      display: flex;
      flex-direction: column;
      position: relative;
      overflow: hidden;
    }}
    .pane-trace-tabs {{
      position: relative;
      z-index: 10;
      display: flex;
      align-items: flex-end;
      --pane-trace-tab-overlap: 1px;
      --pane-trace-tab-strip-bg: rgb(10,10,10);
      gap: 2px;
      padding: 0 8px;
      height: 35px;
      margin-bottom: calc(-1 * var(--pane-trace-tab-overlap));
      background: linear-gradient(
        to bottom,
        var(--pane-trace-tab-strip-bg) 0 calc(100% - var(--pane-trace-tab-overlap)),
        transparent calc(100% - var(--pane-trace-tab-overlap))
      );
      flex: 0 0 auto;
      min-width: 0;
      overflow-x: auto;
      overflow-y: hidden;
      -webkit-overflow-scrolling: touch;
      justify-content: flex-start;
      -webkit-app-region: drag;
      scrollbar-width: none;
    }}
    .pane-trace-tabs::-webkit-scrollbar {{ display: none; }}
    .pane-trace-tab {{
      position: relative;
      display: flex;
      align-items: center;
      flex-shrink: 0;
      padding: 0 16px;
      height: 34px;
      box-sizing: border-box;
      font: 500 12px/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
      color: rgba(255,255,255,0.5);
      background: transparent;
      border: none;
      border-radius: 10px 10px 0 0;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s ease;
      min-width: 0;
      max-width: 200px;
      overflow: visible;
      text-overflow: ellipsis;
      -webkit-app-region: no-drag;
    }}
    @media (hover: hover) and (pointer: fine) {{
    .pane-trace-tab:hover {{
      color: rgba(255,255,255,0.9);
      background: rgba(255,255,255,0.1);
    }}
    }}
    .pane-trace-tab.active {{
      color: #fff;
      background: {bg_effective};
      box-shadow: none;
      z-index: 2;
      margin-bottom: calc(-1 * var(--pane-trace-tab-overlap));
      border-radius: 10px 10px 0 0;
    }}
    .pane-trace-tab-label {{
      display: inline-flex;
      align-items: baseline;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .pane-trace-thinking-char {{
      color: rgba(252,252,252,0.42);
      animation: thinking-char-pulse 1.5s linear infinite;
    }}
    .pane-trace-tab:not(.pane-trace-tab-thinking) .pane-trace-thinking-char {{
      color: inherit;
      animation: none;
    }}
    .pane-trace-content {{
      position: relative;
      z-index: 1;
      flex: 1 1 auto;
      min-height: 0;
      display: grid;
      grid-template-columns: 1fr;
      grid-template-rows: 1fr;
    }}
    .pane-trace-content.split-h {{ grid-template-columns: 1fr 1fr; }}
    .pane-trace-content.split-v {{ grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3bl {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3bl [data-slot="0"] {{ grid-column: 1; grid-row: 1; }}
    .pane-trace-content.split-3bl [data-slot="1"] {{ grid-column: 2; grid-row: 1 / -1; }}
    .pane-trace-content.split-3bl [data-slot="2"] {{ grid-column: 1; grid-row: 2; }}
    .pane-trace-content.split-3br {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3br [data-slot="0"] {{ grid-column: 1; grid-row: 1 / -1; }}
    .pane-trace-content.split-3br [data-slot="1"] {{ grid-column: 2; grid-row: 1; }}
    .pane-trace-content.split-3br [data-slot="2"] {{ grid-column: 2; grid-row: 2; }}
    .pane-trace-content.split-3span {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3span [data-slot="2"] {{ grid-column: 1 / -1; }}
    .pane-trace-content.split-4 {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-pane {{
      position: relative;
      min-width: 0;
      min-height: 0;
      display: flex;
      flex-direction: column;
      border: 0.5px solid rgba(255,255,255,0.06);
      overflow: hidden;
    }}
    .pane-trace-header-shadow {{
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 40px;
      background: linear-gradient({bg_effective} 0%, transparent 100%);
      pointer-events: none;
      z-index: 2;
    }}
    .pane-trace-pane-badge {{
      position: absolute;
      top: 6px; left: 8px; z-index: 11;
      width: 28px; height: 28px;
      padding: 4px;
      box-sizing: border-box;
      background: none;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: visible;
      transition: background 0.15s;
      user-select: none;
    }}
    .pane-trace-pane-badge-inner {{
      position: relative;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .pane-trace-pane-badge-glow {{
      position: absolute;
      inset: 0;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(250,249,245,0.65) 0%, rgba(250,249,245,0) 70%);
      pointer-events: none;
      animation: thinking-glow-follow 1s ease-in-out infinite;
      animation-delay: var(--agent-pulse-delay, 0s);
    }}
    .agent-icon-slot {{
      position: relative;
      display: inline-flex;
      align-items: flex-end;
      justify-content: center;
      width: 100%;
      height: 100%;
      line-height: 0;
      --agent-icon-sub-size: 10px;
      --agent-icon-sub-font-size: 6px;
      --agent-icon-sub-offset-x: 14%;
      --agent-icon-sub-offset-y: 10%;
    }}
    .agent-icon-instance-sub {{
      position: absolute;
      right: 0;
      bottom: 0;
      margin: 0;
      min-width: var(--agent-icon-sub-size);
      height: var(--agent-icon-sub-size);
      padding: 0 0.14em;
      border-radius: 999px;
      font-size: var(--agent-icon-sub-font-size);
      font-weight: 700;
      line-height: 1;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
      font-variant-numeric: tabular-nums;
      letter-spacing: -0.01em;
      color: rgba(252,252,252,0.96);
      pointer-events: none;
      background: rgba(8, 10, 14, 0.9);
      border: 1px solid rgba(255,255,255,0.14);
      box-shadow: 0 1px 3px rgba(0,0,0,0.34);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transform: translate(var(--agent-icon-sub-offset-x), var(--agent-icon-sub-offset-y));
    }}
    .pane-trace-pane-badge-icon {{
      width: 100%; height: 100%;
      object-fit: contain;
      display: block;
      position: relative;
      filter: brightness(0) invert(0.92);
    }}
    .pane-trace-pane-badge-thinking .pane-trace-pane-badge-icon {{
      animation: thinking-icon-heartbeat 1s ease-in-out infinite;
      animation-delay: var(--agent-pulse-delay, 0s);
    }}
    .pane-trace-pane-badge:not(.pane-trace-pane-badge-thinking) .pane-trace-pane-badge-glow {{
      display: none;
    }}
    .pane-trace-pane-badge-thinking .pane-trace-pane-badge-glow {{
      display: block;
    }}
    .pane-trace-pane-badge:hover {{ background: rgba(220,40,40,0.7); }}
    .pane-trace-pane-badge:hover .pane-trace-pane-badge-icon {{ filter: brightness(0) invert(1); }}
    @keyframes thinking-glow-follow {{
      0%   {{ transform: scale(0.5); opacity: 0; }}
      50%  {{ transform: scale(1.4); opacity: 0.12; }}
      100% {{ transform: scale(0.5); opacity: 0; }}
    }}
    @keyframes thinking-icon-heartbeat {{
      0%   {{ transform: translateY(0);    filter: brightness(0) invert(0.92); }}
      50%  {{ transform: translateY(-1px); filter: brightness(0) invert(1); }}
      100% {{ transform: translateY(0);    filter: brightness(0) invert(0.92); }}
    }}
    @keyframes thinking-char-pulse {{
      0%   {{ color: rgba(252, 252, 252, 0.62); }}
      10%  {{ color: rgba(252, 252, 252, 0.82); }}
      22%  {{ color: rgba(252, 252, 252, 0.62); }}
      34%  {{ color: rgba(252, 252, 252, 0.42); }}
      88%  {{ color: rgba(252, 252, 252, 0.42); }}
      100% {{ color: rgba(252, 252, 252, 0.62); }}
    }}
    .pane-trace-drop-indicator {{
      position: absolute;
      background: rgba(255,255,255,0.1);
      border: 1.5px solid rgba(255,255,255,0.4);
      border-radius: 4px;
      z-index: 10;
      pointer-events: none;
      display: none;
    }}
    .pane-trace-body {{
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      padding: 10px 12px;
      padding-bottom: calc(10px + env(safe-area-inset-bottom, 0px));
      box-sizing: border-box;
      -webkit-overflow-scrolling: touch;
      font-family: "SF Mono", "SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, monospace;
      font-weight: 400;
      font-style: normal;
      font-size: 11.5px;
      line-height: 1.15;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-wrap: anywhere;
      color: var(--pane-trace-body-fg);
    }}
    .pane-trace-body .ansi-bright-black-fg {{ color: var(--pane-trace-body-dim-fg); }}
    .trace-dot {{
      font-family: -apple-system, "Helvetica Neue", sans-serif;
      font-variant-emoji: text;
      text-rendering: geometricPrecision;
    }}
    @media (prefers-reduced-motion: reduce) {{
      .pane-trace-pane-badge-thinking .pane-trace-pane-badge-icon {{
        animation: none;
        filter: brightness(0) invert(0.92);
      }}
      .pane-trace-pane-badge-thinking .pane-trace-pane-badge-glow {{
        animation: none;
        display: none;
      }}
      .pane-trace-tab-thinking .pane-trace-thinking-char {{
        animation: none;
        color: rgba(252,252,252,0.6);
      }}
    }}
  </style>
</head>
<body>
  <div class="pane-trace-tabs" id="paneTraceTabs"></div>
  <div class="pane-trace-content" id="paneTraceContent">
    <div class="pane-trace-pane" data-slot="0">
      <span class="pane-trace-pane-badge" data-slot="0"></span>
      <div class="pane-trace-body">Loading...</div>
    </div>
  </div>
  <div class="pane-trace-drop-indicator" id="dropIndicator"></div>
  <script>
    const agents = {agents_json};
    const bg = {bg_json};
    const text = {text_json};
    document.documentElement.style.setProperty("--popup-bg", bg);
    document.documentElement.style.setProperty("--popup-text", text);

    const isLocalHost = (host) => host === "127.0.0.1" || host === "localhost" || host === "[::1]" || host.startsWith("192.168.") || host.startsWith("10.") || /^172\\.(1[6-9]|2\\d|3[01])\\./.test(host);
    const pollMs = isLocalHost(String(location.hostname || "")) ? 300 : 1500;
    const tabsEl = document.getElementById("paneTraceTabs");
    const contentEl = document.getElementById("paneTraceContent");
    const dropEl = document.getElementById("dropIndicator");
    const escapeHtml = (value) => String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
    const agentBaseName = (name) => String(name || "").toLowerCase().replace(/-\\d+$/, "");
    const agentPulseOffset = () => 0;
    const tabLabelHtml = (name) => {{
      const label = String(name || "");
      const offset = agentPulseOffset(name);
      const chars = [...label].map((ch, i) =>
        `<span class="pane-trace-thinking-char" style="animation-delay:${{offset + (i * 0.18)}}s">${{escapeHtml(ch)}}</span>`
      ).join("");
      return `<span class="pane-trace-tab-label">${{chars}}</span>`;
    }};

    /* ── state ── */
    let layout = "single";   /* "single" | "h" | "v" | "3bl" | "3br" | "3span" | "4" */
    let paneAgents = [{initial_agent_json}, null, null, null];
    let extraIntervals = [null, null, null];
    let statusInterval = null;
    let currentStatuses = {{}};
    let contentCache = Object.create(null);
    const slotCount = () => ({{ single: 1, h: 2, v: 2, "3bl": 3, "3br": 3, "3span": 3, "4": 4 }})[layout];

    /* ── ansi / fetch ── */
    let ansiUp = null;
    const traceHtml = (raw) => {{
      const txt = String(raw ?? "No output");
      if (!ansiUp) {{ try {{ if (typeof AnsiUp === "function") ansiUp = new AnsiUp(); }} catch (_) {{}} }}
      let html;
      if (ansiUp) {{ try {{ html = ansiUp.ansi_to_html(txt); }} catch (_) {{}} }}
      if (!html) html = txt.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\\n/g,"<br>");
      return html.replace(/[●⏺]/g, '<span class="trace-dot">●</span>');
    }};
    const _paneBodyAtBottom = (el) => !el || el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    const fetchTo = async (agent, bodyEl, scroll) => {{
      if (!agent || !bodyEl) return;
      if (document.hidden) return;
      if (!scroll && !_paneBodyAtBottom(bodyEl)) return;
      try {{
        const res = await fetch(`{trace_path_prefix}/trace?agent=${{encodeURIComponent(agent)}}&lines=160&ts=${{Date.now()}}`);
        if (!res.ok) return;
        const data = await res.json();
        if (document.hidden) return;
        const content = String(data.content || "");
        const atBottom = _paneBodyAtBottom(bodyEl);
        if (!scroll && contentCache[agent] === content) return;
        contentCache[agent] = content;
        bodyEl.innerHTML = traceHtml(content || "No output");
        if (scroll || atBottom) bodyEl.scrollTop = bodyEl.scrollHeight;
      }} catch (_) {{}}
    }};

    /* ── icon path helper ── */
    const agentIconInstanceSubHtml = (name) => {{
      const m = String(name || "").toLowerCase().match(/-(\\d+)$/);
      if (!m) return "";
      const d = m[1];
      return `<span class="agent-icon-instance-sub" aria-hidden="true">${{escapeHtml(d)}}</span>`;
    }};
    const agentIconUrl = (name) => `{trace_path_prefix}/icon/${{encodeURIComponent(String(name || "").toLowerCase())}}`;
    const paneBadgeHtml = (agent) => {{
      const pulse = agentPulseOffset(agent);
      return `<span class="pane-trace-pane-badge-inner" style="--agent-pulse-delay:${{pulse}}s"><span class="pane-trace-pane-badge-glow"></span><span class="agent-icon-slot agent-icon-slot--badge"><img class="pane-trace-pane-badge-icon" src="${{agentIconUrl(agent)}}" alt="${{escapeHtml(agent)}}">${{agentIconInstanceSubHtml(agent)}}</span></span>`;
    }};
    const applyThinkingState = () => {{
      tabsEl.querySelectorAll(".pane-trace-tab").forEach((tab) => {{
        const agent = tab.dataset.agent || "";
        tab.classList.toggle("pane-trace-tab-thinking", currentStatuses[agent] === "running");
      }});
      contentEl.querySelectorAll(".pane-trace-pane-badge").forEach((badge) => {{
        const slot = Number.parseInt(badge.dataset.slot || "-1", 10);
        const agent = slot >= 0 ? paneAgents[slot] : "";
        badge.classList.toggle("pane-trace-pane-badge-thinking", !!agent && currentStatuses[agent] === "running");
      }});
    }};
    const fetchStatuses = async () => {{
      try {{
        const res = await fetch(`{trace_path_prefix}/session-state?ts=${{Date.now()}}`, {{ cache: "no-store" }});
        if (!res.ok) return;
        const data = await res.json();
        currentStatuses = (data && typeof data.statuses === "object" && data.statuses) ? data.statuses : {{}};
        applyThinkingState();
      }} catch (_) {{}}
    }};

    /* ── make a pane element ── */
    const makePane = (slot, agent) => {{
      const d = document.createElement("div");
      d.className = "pane-trace-pane";
      d.setAttribute("data-slot", slot);
      d.innerHTML = `<div class="pane-trace-header-shadow"></div><span class="pane-trace-pane-badge" data-slot="${{slot}}">${{paneBadgeHtml(agent)}}</span><div class="pane-trace-body">Loading...</div>`;
      d.querySelector(".pane-trace-pane-badge").addEventListener("click", () => closePane(slot));
      return d;
    }};

    /* ── rebuild panes from state ── */
    const rebuildPanes = () => {{
      const n = slotCount();
      contentEl.className = "pane-trace-content" + (layout !== "single" ? ` split-${{layout}}` : "");
      extraIntervals.forEach((iv, i) => {{ if (iv) clearInterval(iv); extraIntervals[i] = null; }});
      contentCache = Object.create(null);
      contentEl.innerHTML = "";
      const used = new Set();
      for (let i = 0; i < n; i++) {{
        if (!paneAgents[i] || (i > 0 && used.has(paneAgents[i]))) {{
          paneAgents[i] = agents.find(a => !used.has(a)) || agents[0];
        }}
        used.add(paneAgents[i]);
        const pane = makePane(i, paneAgents[i]);
        contentEl.appendChild(pane);
        fetchTo(paneAgents[i], pane.querySelector(".pane-trace-body"), true);
        if (i > 0) {{
          const idx = i;
          extraIntervals[idx - 1] = setInterval(() => {{
            const b = contentEl.querySelector(`[data-slot="${{idx}}"] .pane-trace-body`);
            if (b && paneAgents[idx]) fetchTo(paneAgents[idx], b, false);
          }}, pollMs);
        }}
      }}
      for (let i = n; i < 4; i++) paneAgents[i] = null;
      document.title = layout === "single" ? `${{paneAgents[0]}} Pane Trace` : "Pane Trace";
      applyThinkingState();
    }};

    /* ── close a pane ── */
    const closePane = (slot) => {{
      const n = slotCount();
      if (n <= 1) return;
      paneAgents.splice(slot, 1);
      paneAgents.push(null);
      if (n === 4) {{ layout = "h"; }}
      else if (n === 3) {{ layout = "h"; }}
      else {{ layout = "single"; }}
      buildTabs();
      rebuildPanes();
    }};

    /* ── detect drop zone ── */
    const detectZone = (e) => {{
      const n = slotCount();
      if (n >= 4) {{
        const pane = e.target.closest(".pane-trace-pane");
        return pane ? {{ action: "replace", slot: parseInt(pane.getAttribute("data-slot"), 10) }} : null;
      }}
      const rect = contentEl.getBoundingClientRect();
      const rx = (e.clientX - rect.left) / rect.width;
      const ry = (e.clientY - rect.top) / rect.height;
      if (n === 1) {{
        const dRight = 1 - rx, dBottom = 1 - ry;
        if (dRight < 0.35 && dRight < dBottom) return {{ action: "split", dir: "h", zone: "right", rect }};
        if (dBottom < 0.35) return {{ action: "split", dir: "v", zone: "bottom", rect }};
        return {{ action: "replace", slot: 0 }};
      }}
      if (n === 2 && layout === "h") {{
        /* bottom edge of left or right pane → add 3rd pane */
        const isBottom = ry > 0.65;
        if (isBottom) {{
          /* left half of bottom → 3rd under left column, right half → 3rd under right column */
          /* center region → span full bottom */
          if (rx < 0.35) return {{ action: "expand3", sub: "3bl", rect }};
          if (rx > 0.65) return {{ action: "expand3", sub: "3br", rect }};
          return {{ action: "expand3", sub: "3span", rect }};
        }}
        return {{ action: "replace", slot: rx > 0.5 ? 1 : 0 }};
      }}
      if (n === 2 && layout === "v") {{
        const isRight = rx > 0.65;
        if (isRight) return {{ action: "split_to_h_then_3", rect }};
        return {{ action: "replace", slot: ry > 0.5 ? 1 : 0 }};
      }}
      if (n === 3) {{
        /* 3 panes: bottom edge → go to 4, otherwise replace */
        const isBottom = ry > 0.65;
        if (isBottom && (layout === "3bl" || layout === "3br")) {{
          return {{ action: "expand4", rect }};
        }}
        if (layout === "3span" && ry > 0.5) {{
          /* drop on bottom-span: check left/right to decide expand to 4 */
          if (rx < 0.35 || rx > 0.65) return {{ action: "expand4", rect }};
          return {{ action: "replace", slot: 2 }};
        }}
        const pane = e.target.closest(".pane-trace-pane");
        return pane ? {{ action: "replace", slot: parseInt(pane.getAttribute("data-slot"), 10) }} : null;
      }}
      return null;
    }};

    /* ── drop indicator ── */
    const showIndicator = (e) => {{
      const zone = detectZone(e);
      if (!zone) {{ dropEl.style.display = "none"; return; }}
      const cr = contentEl.getBoundingClientRect();
      dropEl.style.display = "block";
      if (zone.action === "split" && zone.zone === "right") {{
        dropEl.style.left = (cr.left + cr.width * 0.5) + "px";
        dropEl.style.top = cr.top + "px";
        dropEl.style.width = (cr.width * 0.5) + "px";
        dropEl.style.height = cr.height + "px";
      }} else if (zone.action === "split" && zone.zone === "bottom") {{
        dropEl.style.left = cr.left + "px";
        dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
        dropEl.style.width = cr.width + "px";
        dropEl.style.height = (cr.height * 0.5) + "px";
      }} else if (zone.action === "expand3") {{
        if (zone.sub === "3bl") {{
          dropEl.style.left = cr.left + "px";
          dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
          dropEl.style.width = (cr.width * 0.5) + "px";
          dropEl.style.height = (cr.height * 0.5) + "px";
        }} else if (zone.sub === "3br") {{
          dropEl.style.left = (cr.left + cr.width * 0.5) + "px";
          dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
          dropEl.style.width = (cr.width * 0.5) + "px";
          dropEl.style.height = (cr.height * 0.5) + "px";
        }} else {{
          dropEl.style.left = cr.left + "px";
          dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
          dropEl.style.width = cr.width + "px";
          dropEl.style.height = (cr.height * 0.5) + "px";
        }}
      }} else if (zone.action === "split_to_h_then_3") {{
        dropEl.style.left = (cr.left + cr.width * 0.5) + "px";
        dropEl.style.top = cr.top + "px";
        dropEl.style.width = (cr.width * 0.5) + "px";
        dropEl.style.height = cr.height + "px";
      }} else if (zone.action === "expand4") {{
        dropEl.style.left = cr.left + "px"; dropEl.style.top = cr.top + "px";
        dropEl.style.width = cr.width + "px"; dropEl.style.height = cr.height + "px";
      }} else if (zone.action === "replace") {{
        const pane = contentEl.querySelector(`[data-slot="${{zone.slot}}"]`);
        if (pane) {{
          const pr = pane.getBoundingClientRect();
          dropEl.style.left = pr.left + "px"; dropEl.style.top = pr.top + "px";
          dropEl.style.width = pr.width + "px"; dropEl.style.height = pr.height + "px";
        }}
      }}
    }};

    /* ── drag events on content ── */
    contentEl.addEventListener("dragover", e => {{ e.preventDefault(); showIndicator(e); }});
    contentEl.addEventListener("dragleave", () => {{ dropEl.style.display = "none"; }});
    contentEl.addEventListener("drop", e => {{
      e.preventDefault();
      dropEl.style.display = "none";
      const agent = e.dataTransfer.getData("text/plain");
      if (!agent || !agents.includes(agent)) return;
      const zone = detectZone(e);
      if (!zone) return;
      if (zone.action === "replace") {{
        paneAgents[zone.slot] = agent;
        const body = contentEl.querySelector(`[data-slot="${{zone.slot}}"] .pane-trace-body`);
        const badge = contentEl.querySelector(`[data-slot="${{zone.slot}}"].pane-trace-pane-badge, .pane-trace-pane[data-slot="${{zone.slot}}"] .pane-trace-pane-badge`);
        if (body) {{ body.innerHTML = "Loading..."; fetchTo(agent, body, true); }}
        if (badge) {{ badge.innerHTML = paneBadgeHtml(agent); }}
        if (zone.slot === 0) buildTabs();
        return;
      }}
      if (zone.action === "split") {{
        layout = zone.dir;
        paneAgents[1] = agent;
        buildTabs();
        rebuildPanes();
        return;
      }}
      if (zone.action === "expand3") {{
        /* 2 → 3: add one pane in the chosen sub-layout */
        layout = zone.sub;
        paneAgents[2] = agent;
        buildTabs();
        rebuildPanes();
        return;
      }}
      if (zone.action === "split_to_h_then_3") {{
        /* v2 → rearrange as 3bl (top-left, top-right=new, bottom-left=old-slot1) */
        const old1 = paneAgents[1];
        layout = "3span";
        paneAgents[1] = agent;
        paneAgents[2] = old1;
        buildTabs();
        rebuildPanes();
        return;
      }}
      if (zone.action === "expand4") {{
        const prevN = slotCount();
        layout = "4";
        if (prevN === 3) {{
          paneAgents[3] = agent;
        }} else {{
          paneAgents[2] = agent;
          paneAgents[3] = agents.find(a => a !== paneAgents[0] && a !== paneAgents[1] && a !== agent) || agents[0];
        }}
        buildTabs();
        rebuildPanes();
      }}
    }});

    /* ── tab bar ── */
    const buildTabs = () => {{
      const n = slotCount();
      const activeSet = new Set(paneAgents.slice(0, n).filter(Boolean));
      tabsEl.innerHTML = agents.map(a =>
        `<button class="pane-trace-tab${{activeSet.has(a) ? " active" : ""}}" data-agent="${{escapeHtml(a)}}" draggable="true">${{tabLabelHtml(a)}}</button>`
      ).join("");
      tabsEl.querySelectorAll(".pane-trace-tab").forEach(tab => {{
        tab.addEventListener("click", () => switchAgent(tab.dataset.agent));
        tab.addEventListener("dragstart", (e) => {{
          e.dataTransfer.setData("text/plain", tab.dataset.agent);
          e.dataTransfer.effectAllowed = "copyMove";
        }});
      }});
      applyThinkingState();
      requestAnimationFrame(() => {{
        const active = tabsEl.querySelector(".pane-trace-tab.active");
        if (active) active.scrollIntoView({{ inline: "center", block: "nearest" }});
      }});
    }};

    /* ── switch main agent (slot 0) ── */
    const switchAgent = (agent) => {{
      if (!agents.includes(agent)) return;
      paneAgents[0] = agent;
      document.title = layout === "single" ? `${{agent}} Pane Trace` : "Pane Trace";
      buildTabs();
      const body = contentEl.querySelector('[data-slot="0"] .pane-trace-body');
      const badge = contentEl.querySelector('.pane-trace-pane[data-slot="0"] .pane-trace-pane-badge');
      if (body) {{ body.innerHTML = "Loading..."; fetchTo(agent, body, true); }}
      if (badge) {{ badge.innerHTML = paneBadgeHtml(agent); }}
    }};

    /* ── postMessage from parent ── */
    window.addEventListener("message", (e) => {{
      if (e.data && e.data.type === "switchAgent" && e.data.agent) switchAgent(e.data.agent);
    }});

    /* ── init ── */
    buildTabs();
    rebuildPanes();
    fetchStatuses();
    statusInterval = setInterval(fetchStatuses, pollMs);
    setInterval(() => {{
      const body = contentEl.querySelector('[data-slot="0"] .pane-trace-body');
      if (body && paneAgents[0]) fetchTo(paneAgents[0], body, false);
    }}, pollMs);
    document.addEventListener("visibilitychange", () => {{
      if (document.hidden) return;
      const n = slotCount();
      for (let i = 0; i < n; i++) {{
        const body = contentEl.querySelector(`[data-slot="${{i}}"] .pane-trace-body`);
        if (body && paneAgents[i]) fetchTo(paneAgents[i], body, false);
      }}
      fetchStatuses();
    }});
  </script>
</body>
</html>"""
