from __future__ import annotations

import json
import os
from pathlib import Path
from html import escape as html_escape
from urllib.parse import quote as url_quote

from appearance.colors import (
    MOBILE_DARK_ICON_HOVER,
    MOBILE_LIGHT_ICON_HOVER,
    TEXT_DIFF_DELETE_DARK_CHANNELS,
    TEXT_DIFF_DELETE_LIGHT_CHANNELS,
    TEXT_DIFF_INSERT_DARK_CHANNELS,
    TEXT_DIFF_INSERT_LIGHT_CHANNELS,
    TEXT_EXTERNAL_LINK_DARK_CHANNELS,
    TEXT_EXTERNAL_LINK_LIGHT_CHANNELS,
    TEXT_LINK_DARK_CHANNELS,
    TEXT_LINK_LIGHT_CHANNELS,
    TEXT_MUTED_DARK_CHANNELS,
    TEXT_MUTED_LIGHT_CHANNELS,
    TEXT_PRIMARY_MOBILE_DARK_CHANNELS,
    TEXT_PRIMARY_MOBILE_LIGHT_CHANNELS,
    TEXT_STRONG_MOBILE_DARK_CHANNELS,
    TEXT_STRONG_MOBILE_LIGHT_CHANNELS,
    resolve_theme_palette,
)
from hub_backend.presentation.chat.script_assets import (
    KATEX_CDN_AUTO_RENDER_SRC,
    KATEX_CDN_CSS_HREF,
    KATEX_CDN_JS_SRC,
    MARKED_CDN_SRC,
)
from appearance.typography import body_typography_css
from .view_scripts import (
    build_gutter_scroll_sync_js,
    build_progressive_loader_js,
    build_vertical_bias_wheel_js,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Same @font-face declarations the chat UI loads (apps/shared/chat/font-faces.css,
# included there via __CHAT_INCLUDE__); this preview pane isn't part of that
# template pipeline, so it reads the one shared source directly instead of
# carrying its own copy.
_FONT_FACES_CSS = (_REPO_ROOT / "apps" / "shared" / "chat" / "font-faces.css").read_text()


def _chat_markdown_preview_css() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    theme_vars_css = (repo_root / "apps/shared/chat/markdown-theme-vars.css").read_text(encoding="utf-8")
    inline_code_css = (repo_root / "apps/shared/chat/markdown-inline-code.css").read_text(encoding="utf-8")
    code_block_css = (repo_root / "apps/shared/chat/markdown-code-block.css").read_text(encoding="utf-8")
    shared_body_css = (repo_root / "apps/shared/chat/markdown-body.css").read_text(encoding="utf-8")
    variant_body_css = (repo_root / "apps/shared/chat/markdown-body-mobile.css").read_text(encoding="utf-8")
    markdown_css = f"{shared_body_css}\n{variant_body_css}"
    replacements = {
        "__AGENT_SEL_MD_BODY__": ".md-body",
        "__AGENT_SEL_MD_BODY_LI__": ".md-body li",
        "__AGENT_SEL_MD_HEADING__": ".md-body h1, .md-body h2, .md-body h3, .md-body h4",
    }
    for placeholder, value in replacements.items():
        markdown_css = markdown_css.replace(placeholder, value)
    return f"{theme_vars_css}\n{inline_code_css}\n{code_block_css}\n{markdown_css}"


def _chat_markdown_frontmatter_js() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / "apps/shared/chat/markdown-frontmatter.js").read_text(encoding="utf-8")


def render_file_view(
    runtime,
    rel: str,
    *,
    embed: bool = False,
    base_path: str = "",
    preview_base_theme: str = "",
    agent_font_family: str | None = None,
    agent_code_font: str | None = None,
    agent_text_size: int | None = None,
    force_progressive_text: bool = False,
) -> str:
    full = runtime._resolve_reference_path(rel)
    if not os.path.exists(full):
        raise FileNotFoundError(full)

    ext = os.path.splitext(rel)[1].lower()
    filename = os.path.basename(rel)
    prefix = (base_path or "").rstrip("/")
    raw_url = f"{prefix}/file-raw?path={url_quote(rel)}"
    size = os.path.getsize(full)
    resolved_agent_font_family = str(agent_font_family).strip() if agent_font_family else ""
    code_font_family = str(agent_code_font).strip() if agent_code_font else ""
    try:
        resolved_text_size = int(agent_text_size or 13)
    except (TypeError, ValueError):
        resolved_text_size = 13
    resolved_line_height = round(resolved_text_size * 1.5)
    requested_base_theme = str(preview_base_theme or "").strip().lower()
    if requested_base_theme in ("dark", "light"):
        theme_palette = resolve_theme_palette(requested_base_theme)
    else:
        theme_palette = resolve_theme_palette("dark")
    dark_theme_palette = resolve_theme_palette("dark")
    pane_bg = str(theme_palette["dark_bg"])
    embed_bg = "transparent" if embed else pane_bg
    pane_fg = str(theme_palette["light_fg"])
    pane_fg_channels = str(theme_palette["light_fg_channels"])
    is_light_theme = str(theme_palette.get("theme") or "").lower() == "light"
    # Line numbers are text, not decoration: read text-muted directly rather
    # than a translucent tint of the code pane's own (separate) fg system.
    pane_ln_color = f"rgb({TEXT_MUTED_LIGHT_CHANNELS if is_light_theme else TEXT_MUTED_DARK_CHANNELS})"
    pane_line = f"rgba({pane_fg_channels},0.08)"
    pane_gutter_bg = f"rgba({pane_fg_channels},0.06)"
    pane_gutter_divider = f"rgba({pane_fg_channels},0.16)"
    gutter_padding_left = 1
    gutter_padding_right = 5
    code_cell_padding_left = 12
    preview_text_size_sync_js = (
        'window.addEventListener("message",(e)=>{'
        'const d=e?.data;if(d?.type!=="agent-preview-text-size")return;'
        'const s=Number(d.size);if(!Number.isFinite(s)||s<8)return;'
        'document.documentElement.style.setProperty("--text-size",s+"px");'
        'document.documentElement.style.setProperty("--text-line-height",Math.round(s*1.5)+"px");'
        '});'
    )
    font_base = prefix or ""
    message_font_family = resolved_agent_font_family.split(",", 1)[0].strip().strip('"')
    code_font_family_name = code_font_family.split(",", 1)[0].strip().strip('"')
    font_face_css = (
        _FONT_FACES_CSS.replace("__CHAT_BASE_PATH__", font_base)
        .replace("__MESSAGE_FONT_FAMILY__", message_font_family)
        .replace("__CODE_FONT_FAMILY__", code_font_family_name)
    )
    preview_top_offset = "max(48px, calc(21px + env(safe-area-inset-top)))" if embed else "0px"
    base_css = (
        f':root{{color-scheme: dark;--font-main:{resolved_agent_font_family};--font-code:{code_font_family};--text-size:{resolved_text_size}px;--text-line-height:{resolved_line_height}px;--body-weight:{"430" if is_light_theme else "300"};--tpad:{preview_top_offset};--preview-gutter-bg:{pane_gutter_bg};--preview-gutter-divider:{pane_gutter_divider};}}'
        f"{font_face_css}"
        f"*{{box-sizing:border-box}}"
        f"html,body{{margin:0;background:{embed_bg};color:{pane_fg};font-family:sans-serif;display:flex;flex-direction:column;height:100vh;font-size:var(--text-size);line-height:var(--text-line-height);font-weight:var(--body-weight);-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;font-synthesis:none}}"
    )

    def build_gutter_metrics(line_count: int) -> tuple[int, int]:
        gutter_content_width = len(str(max(1, line_count))) * 8 + 2
        gutter_column_width = gutter_content_width + gutter_padding_left + gutter_padding_right
        title_offset = gutter_column_width + code_cell_padding_left
        return gutter_column_width, title_offset

    def preview_shell_attrs(
        *,
        gutter_width: int = 0,
        title_offset: int = 0,
    ) -> str:
        if gutter_width <= 0 and title_offset <= 0:
            return ""
        attrs = [
            f'data-preview-gutter-width="{max(0, int(gutter_width))}"',
            f'data-preview-title-offset="{max(0, int(title_offset))}"',
            f'data-preview-gutter-bg="{html_escape(pane_gutter_bg)}"',
            f'data-preview-gutter-divider="{html_escape(pane_gutter_divider)}"',
        ]
        return " " + " ".join(attrs)

    def build_text_table_markup(text_content: str) -> tuple[str, str, int, int]:
        escaped = html_escape(text_content)
        highlighted_lines = escaped.split("\n")
        line_count = max(1, len(highlighted_lines))
        gutter_width, title_offset = build_gutter_metrics(line_count)
        gutter_rows = "".join(
            f'<tr data-line="{idx}"><td class="ln">{idx}</td></tr>'
            for idx, _line in enumerate(highlighted_lines, start=1)
        )
        code_rows = "".join(
            f'<tr data-line="{idx}"><td class="lc"><pre>{line if line else " "}</pre></td></tr>'
            for idx, line in enumerate(highlighted_lines, start=1)
        )
        return gutter_rows, code_rows, gutter_width, title_offset

    if ext in runtime.IMAGE_EXTS:
        return (
            f'<!DOCTYPE html><html><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'<title>{html_escape(filename)}</title>'
            f'<style>{base_css}'
            f'.wrap{{flex:1;overflow:auto;display:flex;align-items:center;justify-content:center;padding:16px;background:{embed_bg};padding-top:calc(16px + var(--tpad,0px))}}'
            f'@media (max-width: 480px) {{.wrap{{padding-left:0;padding-right:0}}}}'
            f'img{{max-width:100%;max-height:100%;object-fit:contain}}</style></head>'
            f'<body><div class="wrap"><img src="{raw_url}" alt="{html_escape(filename)}"></div></body></html>'
        )
    if ext in runtime.PDF_EXTS:
        return (
            f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}.wrap{{flex:1;min-height:0;background:{embed_bg};padding-top:var(--tpad,0px)}}iframe{{width:100%;height:100%;border:0;background:{embed_bg}}}</style></head>'
            f'<body><div class="wrap"><iframe src="{raw_url}" title="{html_escape(filename)}"></iframe></div></body></html>'
        )
    if ext in runtime.VIDEO_EXTS:
        return (
            f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}.wrap{{flex:1;display:flex;align-items:center;justify-content:center;background:{embed_bg};padding-top:var(--tpad,0px)}}'
            f'video{{max-width:100%;max-height:100%}}</style></head>'
            f'<body><div class="wrap"><video controls src="{raw_url}"></video></div></body></html>'
        )
    if ext in runtime.AUDIO_EXTS:
        return (
            f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}.wrap{{flex:1;display:flex;align-items:center;justify-content:center;background:{embed_bg};padding-top:var(--tpad,0px)}}'
            f'audio{{width:100%;max-width:500px}}</style></head>'
            f'<body><div class="wrap"><audio controls src="{raw_url}"></audio></div></body></html>'
        )
    is_text_like = ext in runtime.EDITABLE_TEXT_EXTS or runtime._is_probably_text_file(full)
    if ext in {".html", ".htm"}:
        progressive_html = bool(force_progressive_text) or size > runtime.INLINE_PROGRESSIVE_PREVIEW_MAX_BYTES
        if progressive_html:
            gutter_width, title_offset = build_gutter_metrics(
                max(1, int(size / 32)),
            )
            gutter_rows = ""
            code_rows = ""
            html_progressive_loader_js = build_progressive_loader_js(
                raw_url_value=raw_url,
                total_bytes=size,
                chunk_bytes=runtime.PROGRESSIVE_TEXT_PREVIEW_CHUNK_BYTES,
                view_container_id="htmlTextViewContainer",
                code_scroll_id="htmlTextCodeScroll",
                gutter_body_id="htmlTextGutterBody",
                code_body_id="htmlTextCodeBody",
            )
        else:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            gutter_rows, code_rows, gutter_width, title_offset = build_text_table_markup(
                content,
            )
            html_progressive_loader_js = ""

        tabs_markup = "" if embed else (
            '<div class="html-preview-tabs" role="tablist" aria-label="HTML preview mode">'
            '<button class="html-preview-tab" type="button" data-preview-mode="web" aria-selected="false">Web</button>'
            '<button class="html-preview-tab active" type="button" data-preview-mode="text" aria-selected="true">Text</button>'
            '</div>'
        )
        toggle_js = (
            'const root=document.documentElement;'
            'const buttons=Array.from(document.querySelectorAll("[data-preview-mode]"));'
            'const panels=Array.from(document.querySelectorAll("[data-preview-panel]"));'
            'const setMode=(mode)=>{'
            'const nextMode=mode==="text"?"text":"web";'
            'root.dataset.previewMode=nextMode;'
            'window.__agentIndexHtmlPreviewMode=nextMode;'
            'buttons.forEach((button)=>{const active=button.dataset.previewMode===nextMode;button.classList.toggle("active",active);button.setAttribute("aria-selected",active?"true":"false");});'
            'panels.forEach((panel)=>panel.classList.toggle("active",panel.dataset.previewPanel===nextMode));'
            '};'
            'window.__agentIndexApplyHtmlPreviewMode=setMode;'
            'window.addEventListener("message",(event)=>{'
            'const data=event.data||{};'
            'if(data.type==="agent-index-file-preview-mode"){setMode(data.mode);return;}'
            'if(data.type==="agent-preview-text-size"){const sz=Number(data.size);if(Number.isFinite(sz)&&sz>=8){document.documentElement.style.setProperty("--text-size",sz+"px");document.documentElement.style.setProperty("--text-line-height",Math.round(sz*1.5)+"px");}}'
            '});'
            'const bindButtons=()=>{'
            'buttons.forEach((button)=>button.addEventListener("click",()=>setMode(button.dataset.previewMode||"text")));'
            '};'
            'bindButtons();'
            + build_vertical_bias_wheel_js(
                view_container_id="htmlTextViewContainer",
                code_scroll_id="htmlTextCodeScroll",
            )
            + build_gutter_scroll_sync_js(
                code_scroll_id="htmlTextCodeScroll",
                gutter_id="htmlTextGutter",
                gutter_inner_id="htmlTextGutterInner",
            )
            + html_progressive_loader_js
            + 'setMode("text");'
        )
        return (
            f'<!DOCTYPE html><html data-preview-mode="text"{preview_shell_attrs(gutter_width=gutter_width, title_offset=title_offset)}><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}'
            f'.html-preview-shell{{flex:1;min-height:0;display:flex;flex-direction:column;background:{embed_bg}}}'
            f'html[data-preview-mode="text"] .html-preview-shell{{background:transparent}}'
            f'.html-preview-tabs{{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid {pane_line};background:rgba(20,20,19,0.88);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}}'
            f'.html-preview-tab{{appearance:none;border:1px solid rgba({pane_fg_channels},0.08);background:transparent;color:rgba({pane_fg_channels},0.68);border-radius:999px;padding:6px 12px;font:inherit;font-size:12px;line-height:1;cursor:pointer;transition:color .14s ease,border-color .14s ease,background .14s ease}}'
            f'.html-preview-tab.active{{color:rgb({pane_fg_channels});background:rgba({pane_fg_channels},0.06);border-color:rgba({pane_fg_channels},0.16)}}'
            '.html-preview-panels{flex:1;min-height:0;position:relative}'
            '.html-preview-panel{display:none;width:100%;height:100%}'
            '.html-preview-panel.active{display:flex}'
            '.html-preview-panel-web{min-height:0;flex-direction:column;padding-top:var(--tpad,0px)}'
            '.html-preview-panel-web iframe{flex:1;min-height:0;width:100%;border:0;background:white}'
            '.html-preview-panel-text{min-height:0;flex-direction:column}'
            f'.html-preview-text-wrap{{--preview-gutter-width:{gutter_width}px;flex:1;min-height:0;display:flex;min-width:0;position:relative;overflow:hidden;background:transparent}}'
            '.html-preview-gutter{position:relative;flex:0 0 var(--preview-gutter-width);min-width:var(--preview-gutter-width);overflow:hidden;border-right:1px solid var(--preview-gutter-divider);background:var(--preview-gutter-bg);padding-top:var(--tpad,0px)}'
            '.html-preview-gutter-inner{min-width:0;will-change:transform}'
            '.html-preview-gutter-table{border-collapse:collapse;width:100%;table-layout:fixed;font-family:var(--font-code);font-size:var(--text-size);line-height:var(--text-line-height)}'
            '.html-preview-gutter-table td{padding:0;vertical-align:top}'
            f'.html-preview-gutter-table .ln{{padding:0 {gutter_padding_right}px 0 {gutter_padding_left}px;width:{gutter_width}px;min-width:{gutter_width}px;box-sizing:border-box;text-align:right;color:{pane_ln_color};user-select:none;font-variant-numeric:tabular-nums;line-height:var(--text-line-height);font-family:var(--font-code);font-size:var(--text-size);background:transparent}}'
            '.html-preview-text-scroll{position:relative;z-index:1;flex:1;min-height:0;min-width:0;width:auto;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:auto;padding-top:var(--tpad,0px)}'
            '.html-preview-text-table{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;font-family:var(--font-code);font-size:var(--text-size);line-height:var(--text-line-height)}'
            '.html-preview-text-table td{padding:0;vertical-align:top}'
            '.html-preview-text-table .lc{padding-left:12px;padding-right:min(7vw,52px)}'
            '.html-preview-text-table .lc pre{margin:0;min-height:var(--text-line-height);line-height:var(--text-line-height);font:inherit;white-space:pre}'
            '.html-preview-gutter-table tbody tr:last-child .ln,.html-preview-text-table tbody tr:last-child .lc pre{padding-bottom:24px}'
            '</style></head>'
            f'<body><div class="html-preview-shell">{tabs_markup}'
            '<div class="html-preview-panels">'
            f'<div class="html-preview-panel html-preview-panel-web" data-preview-panel="web"><iframe src="{raw_url}" title="{html_escape(filename)}"></iframe></div>'
            f'<div class="html-preview-panel html-preview-panel-text active" data-preview-panel="text"><div class="html-preview-text-wrap" id="htmlTextViewContainer"><div class="html-preview-gutter" id="htmlTextGutter"><div class="html-preview-gutter-inner" id="htmlTextGutterInner"><table class="html-preview-gutter-table" role="presentation"><tbody id="htmlTextGutterBody">{gutter_rows}</tbody></table></div></div><div class="html-preview-text-scroll" id="htmlTextCodeScroll"><table class="html-preview-text-table" role="presentation"><tbody id="htmlTextCodeBody">{code_rows}</tbody></table></div></div></div>'
            f'</div><script>{toggle_js}</script></div></body></html>'
        )
    if is_text_like and ext != ".md" and (bool(force_progressive_text) or size > runtime.INLINE_PROGRESSIVE_PREVIEW_MAX_BYTES):
        chunk_bytes = runtime.PROGRESSIVE_TEXT_PREVIEW_CHUNK_BYTES
        gutter_width, title_offset = build_gutter_metrics(
            max(1, int(size / 32)),
        )
        height = "100vh" if embed else "calc(100vh - 43px)"
        progressive_loader_js = build_progressive_loader_js(
            raw_url_value=raw_url,
            total_bytes=size,
            chunk_bytes=chunk_bytes,
            view_container_id="viewContainer",
            code_scroll_id="codeScroll",
            gutter_body_id="codeGutterBody",
            code_body_id="codeBody",
        )
        return (
            f'<!DOCTYPE html><html{preview_shell_attrs(gutter_width=gutter_width, title_offset=title_offset)}><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}body{{background:{embed_bg};color:{pane_fg}}}'
            f'.view-container{{--preview-gutter-width:{gutter_width}px;height:{height};display:flex;min-width:0;position:relative;overflow:hidden;background:{embed_bg}}}'
            '.code-gutter{position:relative;flex:0 0 var(--preview-gutter-width);min-width:var(--preview-gutter-width);overflow:hidden;border-right:1px solid var(--preview-gutter-divider);background:var(--preview-gutter-bg);padding-top:var(--tpad,0px)}'
            '.code-gutter-inner{min-width:0;will-change:transform}'
            '.code-gutter-table{border-collapse:collapse;width:100%;table-layout:fixed;font-family:var(--font-code);font-size:var(--text-size);line-height:var(--text-line-height)}'
            '.code-gutter-table td{padding:0;vertical-align:top}'
            f'.code-gutter-table .ln{{padding:0 {gutter_padding_right}px 0 {gutter_padding_left}px;width:{gutter_width}px;min-width:{gutter_width}px;box-sizing:border-box;text-align:right;color:{pane_ln_color};user-select:none;font-variant-numeric:tabular-nums;line-height:var(--text-line-height);font-family:var(--font-code);font-size:var(--text-size);background:transparent}}'
            '.code-scroll{position:relative;z-index:1;flex:1;min-width:0;min-height:0;width:auto;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:auto;padding-top:var(--tpad,0px)}'
            '.code-table{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;font-family:var(--font-code);font-size:var(--text-size);line-height:var(--text-line-height)}'
            '.code-table td{padding:0;vertical-align:top}'
            '.code-table .lc{padding-left:12px;padding-right:min(7vw,52px)}'
            '.code-table .lc pre{margin:0;min-height:var(--text-line-height);line-height:var(--text-line-height);font:inherit;white-space:pre}'
            '.code-gutter-table tbody tr:last-child .ln,.code-table tbody tr:last-child .lc pre{padding-bottom:24px}'
            '</style></head>'
            f'<body>'
            '<div class="view-container" id="viewContainer">'
            '<div class="code-gutter" id="codeGutter"><div class="code-gutter-inner" id="codeGutterInner"><table class="code-gutter-table" role="presentation"><tbody id="codeGutterBody"></tbody></table></div></div>'
            '<div class="code-scroll" id="codeScroll"><table class="code-table" role="presentation"><tbody id="codeBody"></tbody></table></div>'
            f'</div><script>{build_vertical_bias_wheel_js(view_container_id="viewContainer", code_scroll_id="codeScroll")}{build_gutter_scroll_sync_js(code_scroll_id="codeScroll", gutter_id="codeGutter", gutter_inner_id="codeGutterInner")}{progressive_loader_js}{preview_text_size_sync_js}</script></body></html>'
        )
    if is_text_like and ext != ".md":
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        gutter_rows, code_rows, gutter_width, title_offset = build_text_table_markup(
            content,
        )
        height = "100vh" if embed else "calc(100vh - 43px)"
        return (
            f'<!DOCTYPE html><html{preview_shell_attrs(gutter_width=gutter_width, title_offset=title_offset)}><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}body{{background:{embed_bg};color:{pane_fg}}}'
            f'.view-container{{--preview-gutter-width:{gutter_width}px;height:{height};display:flex;min-width:0;position:relative;overflow:hidden;background:{embed_bg}}}'
            '.code-gutter{position:relative;flex:0 0 var(--preview-gutter-width);min-width:var(--preview-gutter-width);overflow:hidden;border-right:1px solid var(--preview-gutter-divider);background:var(--preview-gutter-bg);padding-top:var(--tpad,0px)}'
            '.code-gutter-inner{min-width:0;will-change:transform}'
            '.code-gutter-table{border-collapse:collapse;width:100%;table-layout:fixed;font-family:var(--font-code);font-size:var(--text-size);line-height:var(--text-line-height)}'
            '.code-gutter-table td{padding:0;vertical-align:top}'
            f'.code-gutter-table .ln{{padding:0 {gutter_padding_right}px 0 {gutter_padding_left}px;width:{gutter_width}px;min-width:{gutter_width}px;box-sizing:border-box;text-align:right;color:{pane_ln_color};user-select:none;font-variant-numeric:tabular-nums;line-height:var(--text-line-height);font-family:var(--font-code);font-size:var(--text-size);background:transparent}}'
            '.code-scroll{position:relative;z-index:1;flex:1;min-width:0;min-height:0;width:auto;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:auto;padding-top:var(--tpad,0px)}'
            '.code-table{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;font-family:var(--font-code);font-size:var(--text-size);line-height:var(--text-line-height)}'
            '.code-table td{padding:0;vertical-align:top}'
            '.code-table .lc{padding-left:12px;padding-right:min(7vw,52px)}'
            '.code-table .lc pre{margin:0;min-height:var(--text-line-height);line-height:var(--text-line-height);font:inherit;white-space:pre}'
            '.code-gutter-table tbody tr:last-child .ln,.code-table tbody tr:last-child .lc pre{padding-bottom:24px}'
            '</style></head>'
            f'<body>'
            f'<div class="view-container" id="viewContainer"><div class="code-gutter" id="codeGutter"><div class="code-gutter-inner" id="codeGutterInner"><table class="code-gutter-table" role="presentation"><tbody>{gutter_rows}</tbody></table></div></div><div class="code-scroll" id="codeScroll"><table class="code-table" role="presentation"><tbody>{code_rows}</tbody></table></div></div><script>{build_vertical_bias_wheel_js(view_container_id="viewContainer", code_scroll_id="codeScroll")}{build_gutter_scroll_sync_js(code_scroll_id="codeScroll", gutter_id="codeGutter", gutter_inner_id="codeGutterInner")}{preview_text_size_sync_js}</script></body></html>'
        )
    if ext == ".md":
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        content_json = json.dumps(content)
        rel_json = json.dumps(rel.replace("\\", "/"))
        prefix_json = json.dumps(prefix)
        # Match the chat shell's cascade: KaTeX loads before its Chat-derived
        # markdown CSS, with no preview-only math typography overrides.
        markdown_head_tags = [
            f'<script src="{MARKED_CDN_SRC}"></script>',
            f'<link rel="stylesheet" href="{KATEX_CDN_CSS_HREF}">',
            f'<script src="{KATEX_CDN_JS_SRC}"></script>',
            f'<script src="{KATEX_CDN_AUTO_RENDER_SRC}"></script>',
        ]
        markdown_head_libs = "".join(markdown_head_tags)
        markdown_preview_css = _chat_markdown_preview_css()
        markdown_typography_css = body_typography_css()
        markdown_frontmatter_js = _chat_markdown_frontmatter_js()
        initial_preview_theme = "light" if str((theme_palette or {}).get("theme") or "").lower() == "light" else "dark"
        dark_preview_fg_channels = TEXT_PRIMARY_MOBILE_DARK_CHANNELS.replace(" ", "")
        dark_preview_fg = f"rgb({dark_preview_fg_channels})"
        light_preview_fg_channels = TEXT_PRIMARY_MOBILE_LIGHT_CHANNELS.replace(" ", "")
        light_preview_fg = f"rgb({light_preview_fg_channels})"
        light_preview_bg_channels = "249,249,247"
        light_preview_bg = f"rgb({light_preview_bg_channels})"
        dark_preview_fg_bold = f"rgb({TEXT_STRONG_MOBILE_DARK_CHANNELS})"
        light_preview_fg_bold = f"rgb({TEXT_STRONG_MOBILE_LIGHT_CHANNELS})"
        dark_preview_muted = f"rgb({TEXT_MUTED_DARK_CHANNELS})"
        light_preview_muted = f"rgb({TEXT_MUTED_LIGHT_CHANNELS})"
        dark_preview_link = f"rgb({TEXT_LINK_DARK_CHANNELS})"
        light_preview_link = f"rgb({TEXT_LINK_LIGHT_CHANNELS})"
        dark_preview_external_link = f"rgb({TEXT_EXTERNAL_LINK_DARK_CHANNELS})"
        light_preview_external_link = f"rgb({TEXT_EXTERNAL_LINK_LIGHT_CHANNELS})"
        dark_preview_diff_insert = f"rgb({TEXT_DIFF_INSERT_DARK_CHANNELS})"
        light_preview_diff_insert = f"rgb({TEXT_DIFF_INSERT_LIGHT_CHANNELS})"
        dark_preview_diff_delete = f"rgb({TEXT_DIFF_DELETE_DARK_CHANNELS})"
        light_preview_diff_delete = f"rgb({TEXT_DIFF_DELETE_LIGHT_CHANNELS})"
        markdown_theme_css = (
            f':root[data-preview-theme="dark"]{{color-scheme:dark;--bg-rgb:{str(dark_theme_palette.get("dark_bg_channels") or "0, 0, 0")};--bg:{str(dark_theme_palette["dark_bg"])};--fg:{dark_preview_fg};--fg-bold:{dark_preview_fg_bold};--muted:{dark_preview_muted};--icon-fg:{dark_preview_fg};--icon-muted:{dark_preview_muted};--icon-hover:{MOBILE_DARK_ICON_HOVER};--inline-file-link-fg:var(--link-blue);--code-copy-bg:transparent;--code-copy-hover-bg:rgba({dark_preview_fg_channels},0.09);--external-link-fg:{dark_preview_external_link};--link-blue:{dark_preview_link};--link-blue-channels:{TEXT_LINK_DARK_CHANNELS};--git-ins-green:{dark_preview_diff_insert};--git-ins-green-channels:{TEXT_DIFF_INSERT_DARK_CHANNELS};--git-del-red:{dark_preview_diff_delete};--git-del-red-channels:{TEXT_DIFF_DELETE_DARK_CHANNELS};--line:rgba({dark_preview_fg_channels},0.07);--line-strong:rgba({dark_preview_fg_channels},0.12);}}'
            f'html[data-preview-theme="light"]{{color-scheme:light;--bg-rgb:{light_preview_bg_channels};--bg:{light_preview_bg};--fg:{light_preview_fg};--fg-bold:{light_preview_fg_bold};--muted:{light_preview_muted};--icon-fg:{light_preview_fg};--icon-muted:{light_preview_muted};--icon-hover:{MOBILE_LIGHT_ICON_HOVER};--inline-file-link-fg:var(--link-blue);--code-copy-bg:transparent;--code-copy-hover-bg:rgba(0,0,0,0.08);--external-link-fg:{light_preview_external_link};--link-blue:{light_preview_link};--link-blue-channels:{TEXT_LINK_LIGHT_CHANNELS};--git-ins-green:{light_preview_diff_insert};--git-ins-green-channels:{TEXT_DIFF_INSERT_LIGHT_CHANNELS};--git-del-red:{light_preview_diff_delete};--git-del-red-channels:{TEXT_DIFF_DELETE_LIGHT_CHANNELS};--line:rgba(0,0,0,0.10);--line-strong:rgba(0,0,0,0.18);}}'
            'html,body{background:transparent;color:var(--fg)}'
            '.md-preview-shell{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;background:transparent;scrollbar-gutter:auto;padding-top:0}'
        )
        markdown_top_padding = "calc(14px + max(48px, calc(21px + env(safe-area-inset-top))))" if embed else "14px"
        markdown_layout_css = (
            f'.md-preview-shell>.md-body{{padding:{markdown_top_padding} 16px 18px}}'
        )
        return (
            f'<!DOCTYPE html><html data-preview-theme="{initial_preview_theme}" data-theme="{initial_preview_theme}" data-mobile-chat="1" data-mobile="1"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>{html_escape(filename)}</title>'
            f'{markdown_head_libs}'
            f'<style>{base_css}{markdown_theme_css}{markdown_preview_css}{markdown_typography_css}{markdown_layout_css}'
            '</style></head>'
            f'<body><div class="md-preview-shell"><div class="md-body" id="out"></div></div>'
            f'''<script>
const __mdText = {content_json};
const __mdRel = {rel_json};
const __fileBase = {prefix_json};
const __previewEmbed = {json.dumps(embed)};
const __previewBasePath = {prefix_json};
const __previewAgentTextSize = {json.dumps(resolved_text_size)};
const __rawBase = `${{__fileBase}}/file-raw?path=`;
const __root = document.documentElement;
const KATEX_CSS_HREF = {json.dumps(KATEX_CDN_CSS_HREF)};
const KATEX_JS_SRC = {json.dumps(KATEX_CDN_JS_SRC)};
const KATEX_AUTO_RENDER_SRC = {json.dumps(KATEX_CDN_AUTO_RENDER_SRC)};
const loadExternalScriptOnce = (() => {{
  const pending = new Map();
  return (src) => {{
    const raw = String(src || "").trim();
    if (!raw) return Promise.resolve(false);
    const href = new URL(raw, window.location.href).href;
    for (const script of document.scripts) {{
      if ((script.src || "") === href) return Promise.resolve(true);
    }}
    if (pending.has(href)) return pending.get(href);
    const promise = new Promise((resolve, reject) => {{
      const script = document.createElement("script");
      script.src = href;
      script.onload = () => resolve(true);
      script.onerror = () => reject(new Error(`failed to load ${{href}}`));
      document.head.appendChild(script);
    }}).catch(() => false);
    pending.set(href, promise);
    return promise;
  }};
}})();
const loadExternalStylesheetOnce = (() => {{
  const pending = new Map();
  return (href) => {{
    const raw = String(href || "").trim();
    if (!raw) return Promise.resolve(false);
    const absHref = new URL(raw, window.location.href).href;
    for (const link of document.querySelectorAll('link[rel="stylesheet"]')) {{
      if ((link.href || "") === absHref) return Promise.resolve(true);
    }}
    if (pending.has(absHref)) return pending.get(absHref);
    const promise = new Promise((resolve, reject) => {{
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = absHref;
      link.onload = () => resolve(true);
      link.onerror = () => reject(new Error(`failed to load ${{absHref}}`));
      document.head.appendChild(link);
    }}).catch(() => false);
    pending.set(absHref, promise);
    return promise;
  }};
}})();
let katexLoadPromise = null;
const ensureKatexReady = async () => {{
  if (typeof renderMathInElement === "function") return true;
  if (katexLoadPromise) return katexLoadPromise;
  katexLoadPromise = (async () => {{
    const cssReady = await loadExternalStylesheetOnce(KATEX_CSS_HREF);
    const katexReady = await loadExternalScriptOnce(KATEX_JS_SRC);
    const autoRenderReady = katexReady ? await loadExternalScriptOnce(KATEX_AUTO_RENDER_SRC) : false;
    return cssReady && katexReady && autoRenderReady && typeof renderMathInElement === "function";
  }})().catch(() => false);
  return katexLoadPromise;
}};
const __isExternalSrc = (src) => /^(https?:|data:|blob:|file:|\\/\\/)/i.test(src || "");
const buildPreviewHref = (relPath) => {{
  const params = new URLSearchParams();
  params.set("path", String(relPath || ""));
  if (__previewEmbed) params.set("embed", "1");
  if (__previewBasePath) params.set("base_path", __previewBasePath);
  if (__previewAgentTextSize) params.set("agent_text_size", String(__previewAgentTextSize));
  return `${{__fileBase}}/file-view?${{params.toString()}}`;
}};
const __normalizeMdPath = (baseRel, src) => {{
  const cleanSrc = String(src || "").trim();
  if (!cleanSrc || __isExternalSrc(cleanSrc) || cleanSrc.startsWith("#")) return cleanSrc;
  const withoutQuery = cleanSrc.split(/[?#]/, 1)[0];
  const normalizedBaseRel = String(baseRel || "").replaceAll("\\\\", "/");
  const baseIsAbsolute = normalizedBaseRel.startsWith("/");
  const srcIsAbsolute = withoutQuery.startsWith("/");
  const baseParts = normalizedBaseRel.split("/").slice(0, -1);
  const rawParts = srcIsAbsolute
? withoutQuery.replace(/^\\/+/, "").split("/")
: baseParts.concat(withoutQuery.split("/"));
  const out = [];
  for (const part of rawParts) {{
if (!part || part === ".") continue;
if (part === "..") {{
  if (out.length) out.pop();
  continue;
}}
out.push(part);
  }}
  const normalized = out.join("/");
  if (!normalized) return srcIsAbsolute || baseIsAbsolute ? "/" : "";
  return srcIsAbsolute || baseIsAbsolute ? `/${{normalized}}` : normalized;
}};
const __rewriteMarkdownImages = (root) => {{
  root.querySelectorAll("img").forEach((img) => {{
const src = img.getAttribute("src") || "";
if (!src || __isExternalSrc(src)) return;
const resolved = __normalizeMdPath(__mdRel, src);
if (!resolved) return;
img.setAttribute("src", __rawBase + encodeURIComponent(resolved));
  }});
}};
const __rewriteMarkdownLinks = (root) => {{
  root.querySelectorAll("a[href]").forEach((anchor) => {{
const href = String(anchor.getAttribute("href") || "").trim();
if (!href || href.startsWith("#") || __isExternalSrc(href)) return;
const cutIndex = [href.indexOf("?"), href.indexOf("#")].filter((idx) => idx >= 0).sort((a, b) => a - b)[0] ?? -1;
const pathPart = cutIndex >= 0 ? href.slice(0, cutIndex) : href;
const suffix = cutIndex >= 0 ? href.slice(cutIndex) : "";
const resolved = __normalizeMdPath(__mdRel, pathPart);
if (!resolved) return;
anchor.setAttribute("href", buildPreviewHref(resolved) + suffix);
  }});
}};
const escapeHtml = (value) => String(value || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
{markdown_frontmatter_js}
const mathRenderOptions = {{
  delimiters: [
{{left: "$$", right: "$$", display: true}},
{{left: "$", right: "$", display: false}},
{{left: "\\\\[", right: "\\\\]", display: true}},
{{left: "\\\\(", right: "\\\\)", display: false}}
  ],
  ignoredClasses: ["no-math"],
  throwOnError: false
}};
const renderMarkdown = (text) => {{
  if (typeof marked === "undefined") return "<pre>" + escapeHtml(text) + "</pre>";
  try {{
let frontmatterHtml = "";
const frontmatter = extractFrontmatter(text);
if (frontmatter) {{
  const parsed = parseSimpleFrontmatter(frontmatter.yamlText);
  if (Object.keys(parsed).length) {{
    frontmatterHtml = frontmatterTableHtml(parsed);
    text = frontmatter.body;
  }}
}}
const mathBlocks = [];
let placeholderCount = 0;
const codeBlocks = [];
let codeCount = 0;
let processedText = String(text || "").replace(/(```[\\s\\S]*?```|`[^`\\n]+`)/g, (match) => {{
  const id = `code-placeholder-${{codeCount++}}`;
  codeBlocks.push({{ id, content: match }});
  return `\\x00CODE:${{id}}\\x00`;
}});
processedText = processedText.replace(/(\\\\\\[[\\s\\S]+?\\\\\\]|\\\\\\([\\s\\S]+?\\\\\\)|\\$\\$[\\s\\S]+?\\$\\$|\\$[\\s\\S]+?\\$)/g, (match) => {{
  const id = `math-placeholder-${{placeholderCount++}}`;
  mathBlocks.push({{ id, content: match }});
  return `<span class="MATH_SAFE_BLOCK" data-id="${{id}}"></span>`;
}});
processedText = processedText.replace(/\\x00CODE:(code-placeholder-\\d+)\\x00/g, (_, id) => {{
  const block = codeBlocks.find((entry) => entry.id === id);
  return block ? block.content : "";
}});
const tempDiv = document.createElement("div");
tempDiv.innerHTML = marked.parse(processedText, {{ breaks: true, gfm: true }});
if (typeof marked.lexer === "function") {{
  const values = [];
  const walk = (tokens) => {{
    for (const token of tokens || []) {{
      if (token.type === "list" && token.ordered) {{
        for (const item of token.items || []) {{
          const match = String(item.raw || "").match(/^\\s*(\\d{{1,9}})[.)]/);
          values.push(match ? match[1] : "");
          walk(item.tokens);
        }}
      }} else if (token.tokens) {{
        walk(token.tokens);
      }}
    }}
  }};
  walk(marked.lexer(processedText, {{ breaks: true, gfm: true }}));
  const items = tempDiv.querySelectorAll("ol > li");
  if (values.length && values.length === items.length) {{
    items.forEach((item, index) => {{
      if (values[index]) item.setAttribute("value", values[index]);
    }});
  }}
}}
tempDiv.querySelectorAll(".MATH_SAFE_BLOCK").forEach((span) => {{
  const block = mathBlocks.find((entry) => entry.id === span.dataset.id);
  if (block) span.replaceWith(document.createTextNode(block.content));
}});
if (mathBlocks.length) {{
  const marker = document.createElement("span");
  marker.className = "math-render-needed";
  marker.hidden = true;
  tempDiv.prepend(marker);
}}
tempDiv.querySelectorAll("code.language-diff").forEach((codeEl) => {{
  const raw = codeEl.textContent || "";
  codeEl.innerHTML = raw.split("\\n").map((line) => {{
    if (line.startsWith("+")) return `<span class="diff-add"><span class="diff-sign">+</span>${{escapeHtml(line.slice(1))}}</span>`;
    if (line.startsWith("-")) return `<span class="diff-del"><span class="diff-sign">-</span>${{escapeHtml(line.slice(1))}}</span>`;
    return escapeHtml(line);
  }}).join("\\n");
}});
const copySvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
tempDiv.querySelectorAll("pre").forEach((pre) => {{
  const wrap = document.createElement("div");
  wrap.className = "code-block-wrap";
  pre.parentNode.insertBefore(wrap, pre);
  wrap.appendChild(pre);
  wrap.insertAdjacentHTML("beforeend", `<button class="code-copy-btn" type="button" title="Copy">${{copySvg}}</button>`);
}});
if (frontmatterHtml) tempDiv.insertAdjacentHTML("afterbegin", frontmatterHtml);
return tempDiv.innerHTML;
  }} catch (_) {{
return "<pre>" + escapeHtml(text) + "</pre>";
  }}
}};
const ensureWideTables = (scope = document) => {{
  scope.querySelectorAll(".md-body table").forEach((table) => {{
if (table.closest(".table-scroll")) return;
const parent = table.parentNode;
if (!parent) return;
const scroll = document.createElement("div");
scroll.className = "table-scroll";
parent.insertBefore(scroll, table);
scroll.appendChild(table);
  }});
}};
const applyPreviewTheme = (theme) => {{
  const nextTheme = theme === "light" ? "light" : "dark";
  __root.setAttribute("data-preview-theme", nextTheme);
  __root.setAttribute("data-theme", nextTheme);
}};
window.__agentIndexApplyPreviewTheme = applyPreviewTheme;
const renderMathInScope = (scope) => {{
  if (!scope || !scope.querySelector(".math-render-needed")) return;
  const applyMath = () => {{
    if (typeof renderMathInElement !== "function") return;
    renderMathInElement(scope, mathRenderOptions);
    scope.querySelectorAll(".math-render-needed").forEach((marker) => marker.remove());
  }};
  if (typeof renderMathInElement === "function") {{
    applyMath();
    return;
  }}
  ensureKatexReady().then((ready) => {{
    if (ready) applyMath();
  }});
}};
const copyText = async (text) => {{
  if (navigator.clipboard?.writeText) {{
await navigator.clipboard.writeText(text);
return;
  }}
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "absolute";
  area.style.left = "-9999px";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}};
const codeCopySvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
const codeCheckSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
document.addEventListener("click", async (event) => {{
  const btn = event.target.closest(".code-copy-btn");
  if (!btn) return;
  const wrap = btn.closest(".code-block-wrap");
  if (!wrap) return;
  const code = wrap.querySelector("code") || wrap.querySelector("pre") || wrap;
  try {{
await copyText(code.textContent || "");
btn.innerHTML = codeCheckSvg;
btn.title = "Copied";
setTimeout(() => {{
  btn.innerHTML = codeCopySvg;
  btn.title = "Copy";
}}, 1500);
  }} catch (_) {{}}
}});
window.addEventListener("message", (event) => {{
  const data = event?.data;
  if (!data || data.type !== "agent-index-file-preview-theme") return;
  applyPreviewTheme(data.theme);
}});
window.addEventListener("message", (event) => {{
  const data = event?.data;
  if (!data || data.type !== "agent-preview-text-size") return;
  const sz = Number(data.size);
  if (!Number.isFinite(sz) || sz < 8) return;
  document.documentElement.style.setProperty("--text-size", sz + "px");
  document.documentElement.style.setProperty("--text-line-height", Math.round(sz * 1.5) + "px");
}});
const out = document.getElementById("out");
out.innerHTML = renderMarkdown(__mdText);
__rewriteMarkdownImages(out);
__rewriteMarkdownLinks(out);
ensureWideTables(out);
renderMathInScope(out);
applyPreviewTheme("dark");
</script></body></html>'''
        )

    with open(full, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    escaped = html_escape(content)
    pre_height = "100vh" if embed else "calc(100vh - 43px)"
    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
        f'<style>{base_css}body{{background:{embed_bg};color:{pane_fg};font-family:var(--font-code);font-size:13px}}'
        f'pre{{margin:0;padding:16px;white-space:pre;overflow:auto;height:{pre_height};background:{embed_bg};padding-top:calc(16px + var(--tpad,0px))}}'
        '</style></head>'
        f'<body><pre>{escaped}</pre></body></html>'
    )
