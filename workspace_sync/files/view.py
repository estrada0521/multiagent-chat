from __future__ import annotations

import logging
import json
import os
import re
from pathlib import Path
from html import escape as html_escape
from urllib.parse import quote as url_quote

from hub_backend.color_constants import DARK_BG, LIGHT_FG, resolve_theme_palette
from backend_core.access.settings import load_hub_settings
from .preview_3d import render_3d_preview
from .view_scripts import (
    build_gutter_scroll_sync_js,
    build_line_selection_js,
    build_progressive_loader_js,
    build_vertical_bias_wheel_js,
)


def _chat_markdown_preview_css() -> str:
    css_path = Path(__file__).resolve().parents[2] / "apps/desktop/web/chat/styles/transcript.css"
    css = css_path.read_text(encoding="utf-8")
    start = css.index("    .md-body {")
    end = css.index("    .message-deferred-actions", start)
    markdown_css = css[start:end]
    replacements = {
        "__AGENT_SEL_MD_BODY__": ".md-body",
        "__AGENT_SEL_MD_BODY_LI__": ".md-body li",
        "__AGENT_SEL_GOTHIC_MD_BODY__": 'html[data-agent-font-mode="gothic"] .md-body',
        "__AGENT_SEL_GOTHIC_MD_LI__": 'html[data-agent-font-mode="gothic"] .md-body li',
    }
    for placeholder, value in replacements.items():
        markdown_css = markdown_css.replace(placeholder, value)
    return markdown_css


def render_file_view(
    runtime,
    rel: str,
    *,
    embed: bool = False,
    pane: bool = False,
    base_path: str = "",
    preview_base_theme: str = "",
    agent_font_mode: str = "serif",
    agent_font_family: str | None = None,
    agent_text_size: int | None = None,
    message_bold: bool = False,
    force_progressive_text: bool = False,
) -> str:
    full = runtime._resolve_path(rel)
    if not os.path.exists(full):
        raise FileNotFoundError(full)

    ext = os.path.splitext(rel)[1].lower()
    filename = os.path.basename(rel)
    prefix = (base_path or "").rstrip("/")
    raw_url = f"{prefix}/file-raw?path={url_quote(rel)}"
    size = os.path.getsize(full)
    agent_font_mode = "gothic" if str(agent_font_mode or "").strip().lower() == "gothic" else "serif"
    code_font_family = (
        '"SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, "Liberation Mono", monospace'
    )
    try:
        resolved_text_size = int(agent_text_size or 13)
    except (TypeError, ValueError):
        resolved_text_size = 13
    resolved_text_size = max(8, min(18, resolved_text_size))
    resolved_line_height = resolved_text_size + 9
    theme_palette = None
    if runtime.repo_root:
        try:
            theme_palette = resolve_theme_palette(load_hub_settings(runtime.repo_root))
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
    requested_base_theme = str(preview_base_theme or "").strip().lower()
    if requested_base_theme in {"dark", "black-hole"}:
        theme_palette = resolve_theme_palette({"theme": "black-hole"})
    elif requested_base_theme == "light":
        theme_palette = resolve_theme_palette({"theme": "light"})
    dark_theme_palette = resolve_theme_palette({"theme": "black-hole"})
    pane_bg = str((theme_palette or {}).get("dark_bg") or DARK_BG)
    embed_bg = "transparent" if embed else pane_bg
    pane_fg = str((theme_palette or {}).get("light_fg") or LIGHT_FG)
    pane_muted = pane_fg
    pane_line = "rgba(255,255,255,0.08)"
    pane_gutter_bg = "transparent"
    pane_gutter_divider = "rgba(255,255,255,0.16)"
    gutter_padding_left = 1
    gutter_padding_right = 5
    code_cell_padding_left = 12
    preview_scrollbar_thumb = "rgba(255,255,255,0.20)"
    preview_scrollbar_thumb_hover = "rgba(255,255,255,0.34)"
    preview_scrollbar_thumb_light = "rgba(20,20,19,0.18)"
    preview_scrollbar_thumb_hover_light = "rgba(20,20,19,0.30)"
    preview_selected_line_bg = "rgba(255,255,255,0.10)"
    preview_text_size_sync_js = (
        'window.addEventListener("message",(e)=>{'
        'const d=e?.data;if(d?.type!=="agent-preview-text-size")return;'
        'const s=Number(d.size);if(!Number.isFinite(s)||s<8)return;'
        'document.documentElement.style.setProperty("--message-text-size",s+"px");'
        'document.documentElement.style.setProperty("--message-text-line-height",(s+9)+"px");'
        '});'
    )
    font_base = prefix or ""
    font_face_css = (
        f'@font-face{{font-family:"jetbrainsMono";src:local("JetBrains Mono"),local("JetBrainsMono-Regular"),url("{font_base}/font/jetbrains-mono.ttf") format("truetype-variations"),url("{font_base}/font/jetbrains-mono.ttf") format("truetype");font-style:normal;font-weight:100 800;font-display:swap}}'
    )
    preview_top_offset = "max(48px, calc(21px + env(safe-area-inset-top)))" if embed else "0px"
    base_css = (
        f':root{{color-scheme: dark;--code-font-family:{code_font_family};--message-text-size:{resolved_text_size}px;--message-text-line-height:{resolved_line_height}px;--tpad:{preview_top_offset};--preview-scrollbar-size:6px;--preview-scrollbar-thumb:{preview_scrollbar_thumb};--preview-scrollbar-thumb-hover:{preview_scrollbar_thumb_hover};--preview-gutter-bg:{pane_gutter_bg};--preview-gutter-divider:{pane_gutter_divider};--preview-selected-line-bg:{preview_selected_line_bg};}}'
        f"{font_face_css}"
        f"*{{box-sizing:border-box}}"
        '.md-preview-shell,.view-container,.html-preview-text-wrap,.html-preview-text-scroll,.code-scroll,.table-scroll,.katex-display,.md-body pre{scrollbar-width:thin;scrollbar-color:var(--preview-scrollbar-thumb) transparent}'
        '.md-preview-shell::-webkit-scrollbar,.view-container::-webkit-scrollbar,.html-preview-text-wrap::-webkit-scrollbar,.html-preview-text-scroll::-webkit-scrollbar,.code-scroll::-webkit-scrollbar,.table-scroll::-webkit-scrollbar,.katex-display::-webkit-scrollbar,.md-body pre::-webkit-scrollbar{width:var(--preview-scrollbar-size);height:var(--preview-scrollbar-size)}'
        '.md-preview-shell::-webkit-scrollbar-track,.view-container::-webkit-scrollbar-track,.html-preview-text-wrap::-webkit-scrollbar-track,.html-preview-text-scroll::-webkit-scrollbar-track,.code-scroll::-webkit-scrollbar-track,.table-scroll::-webkit-scrollbar-track,.katex-display::-webkit-scrollbar-track,.md-body pre::-webkit-scrollbar-track{background:transparent}'
        '.md-preview-shell::-webkit-scrollbar-thumb,.view-container::-webkit-scrollbar-thumb,.html-preview-text-wrap::-webkit-scrollbar-thumb,.html-preview-text-scroll::-webkit-scrollbar-thumb,.code-scroll::-webkit-scrollbar-thumb,.table-scroll::-webkit-scrollbar-thumb,.katex-display::-webkit-scrollbar-thumb,.md-body pre::-webkit-scrollbar-thumb{background:var(--preview-scrollbar-thumb);border-radius:999px;border:1px solid transparent;background-clip:padding-box}'
        '.md-preview-shell::-webkit-scrollbar-thumb:hover,.view-container::-webkit-scrollbar-thumb:hover,.html-preview-text-wrap::-webkit-scrollbar-thumb:hover,.html-preview-text-scroll::-webkit-scrollbar-thumb:hover,.code-scroll::-webkit-scrollbar-thumb:hover,.table-scroll::-webkit-scrollbar-thumb:hover,.katex-display::-webkit-scrollbar-thumb:hover,.md-body pre::-webkit-scrollbar-thumb:hover{background:var(--preview-scrollbar-thumb-hover);background-clip:padding-box}'
        f"html,body{{margin:0;background:{embed_bg};color:{pane_fg};font-family:sans-serif;display:flex;flex-direction:column;height:100vh;font-size:var(--message-text-size);line-height:var(--message-text-line-height)}}"
        f".hdr{{padding:10px 16px;background:{embed_bg};border-bottom:0.5px solid {pane_line};display:flex;align-items:center;gap:8px;flex-shrink:0}}"
        f".fn{{font-weight:700;font-size:14px;color:{pane_fg}}}"
    )
    header = "" if embed else (
        f'<div class="hdr"><span>{{icon}}</span><span class="fn">{html_escape(filename)}</span>'
        f"</div>"
    )

    def build_gutter_metrics(
        line_count: int,
        *,
        min_content_width: int = 0,
    ) -> tuple[int, int]:
        gutter_content_width = max(
            min_content_width,
            len(str(max(1, line_count))) * 8 + 6,
        )
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
            f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}.wrap{{flex:1;overflow:auto;display:flex;align-items:center;justify-content:center;padding:16px;background:{embed_bg};padding-top:calc(16px + var(--tpad,0px))}}'
            f'img{{max-width:100%;max-height:100%;object-fit:contain}}</style></head>'
            f'<body>{header.format(icon="🖼️")}<div class="wrap"><img src="{raw_url}" alt="{html_escape(filename)}"></div></body></html>'
        )
    if ext in runtime.PDF_EXTS:
        return (
            f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}.wrap{{flex:1;min-height:0;background:{embed_bg};padding-top:var(--tpad,0px)}}iframe{{width:100%;height:100%;border:0;background:{embed_bg}}}</style></head>'
            f'<body>{header.format(icon="📕")}<div class="wrap"><iframe src="{raw_url}" title="{html_escape(filename)}"></iframe></div></body></html>'
        )
    if ext in runtime.VIDEO_EXTS:
        return (
            f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}.wrap{{flex:1;display:flex;align-items:center;justify-content:center;background:{embed_bg};padding-top:var(--tpad,0px)}}'
            f'video{{max-width:100%;max-height:100%}}</style></head>'
            f'<body>{header.format(icon="🎬")}<div class="wrap"><video controls src="{raw_url}"></video></div></body></html>'
        )
    if ext in runtime.AUDIO_EXTS:
        audio_js = (
            'const audio=document.getElementById("audioPreview");'
            'const cv=document.getElementById("blobCanvas");'
            'const ctx=cv?cv.getContext("2d"):null;'
            'let frame=0,analyser=null,aCtx=null,freqData=null,bands=[0,0,0,0];'
            'const fit=()=>{'
            '  if(!cv)return;const dpr=Math.max(1,devicePixelRatio||1);'
            '  const s=Math.min(cv.clientWidth,cv.clientHeight)||200;'
            '  cv.width=Math.round(s*dpr);cv.height=Math.round(s*dpr);'
            '  if(ctx)ctx.setTransform(dpr,0,0,dpr,0,0);'
            '};'
            'const ensureAudio=async()=>{'
            '  if(analyser)return;try{'
            '  const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return;'
            '  aCtx=new AC();analyser=aCtx.createAnalyser();analyser.fftSize=128;'
            '  analyser.smoothingTimeConstant=0.82;'
            '  freqData=new Uint8Array(analyser.frequencyBinCount);'
            '  const src=aCtx.createMediaElementSource(audio);'
            '  src.connect(analyser);analyser.connect(aCtx.destination);'
            '  }catch(_){}'
            '};'
            'const getBands=()=>{'
            '  if(!analyser||!freqData){bands=[0,0,0,0];return;}'
            '  analyser.getByteFrequencyData(freqData);'
            '  const n=freqData.length;const q=Math.floor(n/4);'
            '  for(let b=0;b<4;b++){'
            '    let sum=0;for(let i=b*q;i<(b+1)*q&&i<n;i++)sum+=freqData[i];'
            '    bands[b]=bands[b]*0.6+(sum/(q*255))*0.4;'
            '  }'
            '};'
            'const draw=()=>{'
            '  if(!ctx||!cv)return;fit();'
            '  const s=Math.min(cv.clientWidth,cv.clientHeight)||200;'
            '  const cx=s/2,cy=s/2;'
            '  const playing=!audio.paused&&!audio.ended;'
            '  const progress=audio.duration?audio.currentTime/audio.duration:0;'
            '  const t=performance.now()*0.001;'
            '  if(playing)getBands();'
            '  ctx.clearRect(0,0,s,s);'
            '  const baseR=s*0.28;'
            '  const energyBoost=playing?(bands[0]*0.3+bands[1]*0.2)*baseR:0;'
            '  const breathe=Math.sin(t*0.8)*baseR*0.015;'
            '  const R=baseR+energyBoost+breathe;'
            '  const N=24;'
            '  const pts=[];'
            '  for(let i=0;i<N;i++){'
            '    const angle=(i/N)*Math.PI*2;'
            '    let deform=0;'
            '    deform+=Math.sin(angle*2+t*1.2)*0.02;'
            '    deform+=Math.sin(angle*3-t*0.9)*0.012;'
            '    deform+=Math.sin(angle*5+t*2.1)*0.006;'
            '    if(playing){'
            '      deform+=Math.sin(angle*2+t*3)*bands[0]*0.25;'
            '      deform+=Math.sin(angle*4-t*2.5)*bands[1]*0.18;'
            '      deform+=Math.sin(angle*6+t*4)*bands[2]*0.12;'
            '      deform+=Math.sin(angle*10-t*5)*bands[3]*0.08;'
            '    }'
            '    const r=R*(1+deform);'
            '    pts.push([cx+Math.cos(angle)*r, cy+Math.sin(angle)*r]);'
            '  }'
            '  ctx.beginPath();'
            '  for(let i=0;i<N;i++){'
            '    const p0=pts[(i-1+N)%N],p1=pts[i],p2=pts[(i+1)%N],p3=pts[(i+2)%N];'
            '    const cp1x=p1[0]+(p2[0]-p0[0])/6;'
            '    const cp1y=p1[1]+(p2[1]-p0[1])/6;'
            '    const cp2x=p2[0]-(p3[0]-p1[0])/6;'
            '    const cp2y=p2[1]-(p3[1]-p1[1])/6;'
            '    if(i===0)ctx.moveTo(p1[0],p1[1]);'
            '    ctx.bezierCurveTo(cp1x,cp1y,cp2x,cp2y,p2[0],p2[1]);'
            '  }'
            '  ctx.closePath();'
            '  const gAngle=progress*Math.PI*2-Math.PI/2;'
            '  const gR=R*1.2;'
            '  const grad=ctx.createLinearGradient('
            '    cx+Math.cos(gAngle)*gR, cy+Math.sin(gAngle)*gR,'
            '    cx+Math.cos(gAngle+Math.PI)*gR, cy+Math.sin(gAngle+Math.PI)*gR'
            '  );'
            '  const alpha=playing?0.35+bands[0]*0.25:0.18;'
            '  grad.addColorStop(0, "rgba(252,252,252,"+alpha.toFixed(3)+")");'
            '  grad.addColorStop(0.5, "rgba(220,220,220,"+(alpha*0.7).toFixed(3)+")");'
            '  grad.addColorStop(1, "rgba(200,200,200,"+(alpha*0.5).toFixed(3)+")");'
            '  ctx.fillStyle=grad;'
            '  ctx.fill();'
            '  ctx.strokeStyle="rgba(252,252,252,"+(playing?0.25+bands[1]*0.3:0.1).toFixed(3)+")";'
            '  ctx.lineWidth=1;'
            '  ctx.stroke();'
            '  if(playing&&(bands[0]>0.1||bands[1]>0.1)){'
            '    ctx.save();ctx.globalAlpha=Math.min(0.15,bands[0]*0.2);'
            '    ctx.filter="blur("+Math.round(8+bands[0]*12)+"px)";'
            '    ctx.fillStyle="rgba(252,252,252,1)";ctx.fill();'
            '    ctx.restore();'
            '  }'
            '};'
            'const tick=()=>{draw();frame=requestAnimationFrame(tick);};'
            'audio.addEventListener("play",async()=>{'
            '  await ensureAudio();if(aCtx&&aCtx.state==="suspended")await aCtx.resume();'
            '});'
            'fit();tick();'
        )
        return (
            f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}.wrap{{flex:1;display:flex;align-items:center;justify-content:center;padding:32px;background:{embed_bg};padding-top:calc(32px + var(--tpad,0px))}}'
            f'.audio-shell{{width:100%;max-width:500px;display:flex;flex-direction:column;align-items:center;gap:14px}}'
            f'#blobCanvas{{width:200px;height:200px;display:block}}'
            f'audio{{width:100%;max-width:500px;min-width:0}}'
            f'</style></head>'
            f'<body>{header.format(icon="🎵")}<div class="wrap"><div class="audio-shell">'
            f'<canvas id="blobCanvas" width="200" height="200"></canvas>'
            f'<audio id="audioPreview" controls src="{raw_url}"></audio></div></div>'
            f'<script>{audio_js}</script></body></html>'
        )
    if ext in runtime.MODEL_3D_EXTS:
        return render_3d_preview(
            ext=ext,
            filename=filename,
            header_html=header.format(icon="🧊"),
            raw_url=raw_url,
            base_css=base_css,
            embed_bg=embed_bg,
            pane_muted=pane_muted,
            pane_line=pane_line,
        )
    is_text_like = ext in runtime.EDITABLE_TEXT_EXTS or runtime._is_probably_text_file(full)
    if ext in {".html", ".htm"}:
        progressive_html = bool(force_progressive_text) or size > runtime.INLINE_PROGRESSIVE_PREVIEW_MAX_BYTES
        if progressive_html:
            gutter_width, title_offset = build_gutter_metrics(
                max(1, int(size / 12)),
                min_content_width=42,
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
            'if(event.origin!==window.location.origin)return;'
            'const data=event.data||{};'
            'if(data.type==="agent-index-file-preview-mode"){setMode(data.mode);return;}'
            'if(data.type==="agent-preview-text-size"){const sz=Number(data.size);if(Number.isFinite(sz)&&sz>=8){document.documentElement.style.setProperty("--message-text-size",sz+"px");document.documentElement.style.setProperty("--message-text-line-height",(sz+9)+"px");}}'
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
            '.html-preview-tab{appearance:none;border:1px solid rgba(255,255,255,0.08);background:transparent;color:rgba(252,252,252,0.68);border-radius:999px;padding:6px 12px;font:inherit;font-size:12px;line-height:1;cursor:pointer;transition:color .14s ease,border-color .14s ease,background .14s ease}'
            '.html-preview-tab.active{color:rgb(252,252,252);background:rgba(255,255,255,0.06);border-color:rgba(255,255,255,0.16)}'
            '.html-preview-panels{flex:1;min-height:0;position:relative}'
            '.html-preview-panel{display:none;width:100%;height:100%}'
            '.html-preview-panel.active{display:flex}'
            '.html-preview-panel-web{min-height:0;flex-direction:column;padding-top:var(--tpad,0px)}'
            '.html-preview-panel-web iframe{flex:1;min-height:0;width:100%;border:0;background:white}'
            '.html-preview-panel-text{min-height:0;flex-direction:column}'
            f'.html-preview-text-wrap{{--preview-gutter-width:{gutter_width}px;flex:1;min-height:0;display:flex;min-width:0;position:relative;overflow:hidden;background:transparent}}'
            '.html-preview-gutter{position:relative;flex:0 0 var(--preview-gutter-width);min-width:var(--preview-gutter-width);overflow:hidden;border-right:1px solid var(--preview-gutter-divider);background:var(--preview-gutter-bg);padding-top:var(--tpad,0px)}'
            '.html-preview-gutter-inner{min-width:0;will-change:transform}'
            '.html-preview-gutter-table{border-collapse:collapse;width:100%;table-layout:fixed;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height)}'
            '.html-preview-gutter-table td{padding:0;vertical-align:top}'
            f'.html-preview-gutter-table .ln{{padding:0 {gutter_padding_right}px 0 {gutter_padding_left}px;width:{gutter_width}px;min-width:{gutter_width}px;box-sizing:border-box;text-align:right;color:{pane_fg};user-select:none;font-variant-numeric:tabular-nums;line-height:var(--message-text-line-height);font-family:var(--code-font-family);font-size:var(--message-text-size);background:transparent}}'
            '.html-preview-text-scroll{position:relative;z-index:1;flex:1;min-height:0;min-width:0;width:auto;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:auto;padding-top:var(--tpad,0px)}'
            '.html-preview-text-table{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height)}'
            '.html-preview-text-table td{padding:0;vertical-align:top}'
            '.html-preview-text-table .lc{padding-left:12px;padding-right:min(7vw,52px)}'
            '.html-preview-gutter-table tbody tr.is-selected .ln,.html-preview-text-table tbody tr.is-selected .lc{background:var(--preview-selected-line-bg)}'
            '.html-preview-text-table .lc pre{margin:0;min-height:var(--message-text-line-height);line-height:var(--message-text-line-height);font:inherit;white-space:pre}'
            '.html-preview-gutter-table tbody tr:last-child .ln,.html-preview-text-table tbody tr:last-child .lc pre{padding-bottom:24px}'
            '</style></head>'
            f'<body>{header.format(icon="🌐")}<div class="html-preview-shell">{tabs_markup}'
            '<div class="html-preview-panels">'
            f'<div class="html-preview-panel html-preview-panel-web" data-preview-panel="web"><iframe src="{raw_url}" title="{html_escape(filename)}" sandbox="allow-same-origin allow-scripts allow-forms allow-popups"></iframe></div>'
            f'<div class="html-preview-panel html-preview-panel-text active" data-preview-panel="text"><div class="html-preview-text-wrap" id="htmlTextViewContainer"><div class="html-preview-gutter" id="htmlTextGutter"><div class="html-preview-gutter-inner" id="htmlTextGutterInner"><table class="html-preview-gutter-table" role="presentation"><tbody id="htmlTextGutterBody">{gutter_rows}</tbody></table></div></div><div class="html-preview-text-scroll" id="htmlTextCodeScroll"><table class="html-preview-text-table" role="presentation"><tbody id="htmlTextCodeBody">{code_rows}</tbody></table></div></div></div>'
            f'</div><script>{toggle_js}{build_line_selection_js(table_selector=".html-preview-text-table", gutter_selector=".html-preview-gutter-table")}</script></div></body></html>'
        )
    if is_text_like and ext != ".md" and (bool(force_progressive_text) or size > runtime.INLINE_PROGRESSIVE_PREVIEW_MAX_BYTES):
        chunk_bytes = runtime.PROGRESSIVE_TEXT_PREVIEW_CHUNK_BYTES
        gutter_width, title_offset = build_gutter_metrics(
            max(1, int(size / 12)),
            min_content_width=42,
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
            f'.hdr{{background:{embed_bg};border-bottom-color:{pane_line}}}'
            f'.fn{{color:{pane_fg}}}'
            f'.view-container{{--preview-gutter-width:{gutter_width}px;height:{height};display:flex;min-width:0;position:relative;overflow:hidden;background:{embed_bg}}}'
            '.code-gutter{position:relative;flex:0 0 var(--preview-gutter-width);min-width:var(--preview-gutter-width);overflow:hidden;border-right:1px solid var(--preview-gutter-divider);background:var(--preview-gutter-bg);padding-top:var(--tpad,0px)}'
            '.code-gutter-inner{min-width:0;will-change:transform}'
            '.code-gutter-table{border-collapse:collapse;width:100%;table-layout:fixed;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height)}'
            '.code-gutter-table td{padding:0;vertical-align:top}'
            f'.code-gutter-table .ln{{padding:0 {gutter_padding_right}px 0 {gutter_padding_left}px;width:{gutter_width}px;min-width:{gutter_width}px;box-sizing:border-box;text-align:right;color:{pane_fg};user-select:none;font-variant-numeric:tabular-nums;line-height:var(--message-text-line-height);font-family:var(--code-font-family);font-size:var(--message-text-size);background:transparent}}'
            '.code-scroll{position:relative;z-index:1;flex:1;min-width:0;min-height:0;width:auto;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:auto;padding-top:var(--tpad,0px)}'
            '.code-table{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height)}'
            '.code-table td{padding:0;vertical-align:top}'
            '.code-table .lc{padding-left:12px;padding-right:min(7vw,52px)}'
            '.code-gutter-table tbody tr.is-selected .ln,.code-table tbody tr.is-selected .lc{background:var(--preview-selected-line-bg)}'
            '.code-table .lc pre{margin:0;min-height:var(--message-text-line-height);line-height:var(--message-text-line-height);font:inherit;white-space:pre}'
            '.code-gutter-table tbody tr:last-child .ln,.code-table tbody tr:last-child .lc pre{padding-bottom:24px}'
            '</style></head>'
            f'<body>{header.format(icon="📄")}'
            '<div class="view-container" id="viewContainer">'
            '<div class="code-gutter" id="codeGutter"><div class="code-gutter-inner" id="codeGutterInner"><table class="code-gutter-table" role="presentation"><tbody id="codeGutterBody"></tbody></table></div></div>'
            '<div class="code-scroll" id="codeScroll"><table class="code-table" role="presentation"><tbody id="codeBody"></tbody></table></div>'
            f'</div><script>{build_vertical_bias_wheel_js(view_container_id="viewContainer", code_scroll_id="codeScroll")}{build_gutter_scroll_sync_js(code_scroll_id="codeScroll", gutter_id="codeGutter", gutter_inner_id="codeGutterInner")}{build_line_selection_js(table_selector=".code-table", gutter_selector=".code-gutter-table")}{progressive_loader_js}{preview_text_size_sync_js}</script></body></html>'
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
            f'.hdr{{background:{embed_bg};border-bottom-color:{pane_line}}}'
            f'.fn{{color:{pane_fg}}}'
            f'.view-container{{--preview-gutter-width:{gutter_width}px;height:{height};display:flex;min-width:0;position:relative;overflow:hidden;background:{embed_bg}}}'
            '.code-gutter{position:relative;flex:0 0 var(--preview-gutter-width);min-width:var(--preview-gutter-width);overflow:hidden;border-right:1px solid var(--preview-gutter-divider);background:var(--preview-gutter-bg);padding-top:var(--tpad,0px)}'
            '.code-gutter-inner{min-width:0;will-change:transform}'
            '.code-gutter-table{border-collapse:collapse;width:100%;table-layout:fixed;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height)}'
            '.code-gutter-table td{padding:0;vertical-align:top}'
            f'.code-gutter-table .ln{{padding:0 {gutter_padding_right}px 0 {gutter_padding_left}px;width:{gutter_width}px;min-width:{gutter_width}px;box-sizing:border-box;text-align:right;color:{pane_fg};user-select:none;font-variant-numeric:tabular-nums;line-height:var(--message-text-line-height);font-family:var(--code-font-family);font-size:var(--message-text-size);background:transparent}}'
            '.code-scroll{position:relative;z-index:1;flex:1;min-width:0;min-height:0;width:auto;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:auto;padding-top:var(--tpad,0px)}'
            '.code-table{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height)}'
            '.code-table td{padding:0;vertical-align:top}'
            '.code-table .lc{padding-left:12px;padding-right:min(7vw,52px)}'
            '.code-gutter-table tbody tr.is-selected .ln,.code-table tbody tr.is-selected .lc{background:var(--preview-selected-line-bg)}'
            '.code-table .lc pre{margin:0;min-height:var(--message-text-line-height);line-height:var(--message-text-line-height);font:inherit;white-space:pre}'
            '.code-gutter-table tbody tr:last-child .ln,.code-table tbody tr:last-child .lc pre{padding-bottom:24px}'
            '</style></head>'
            f'<body>{header.format(icon="📄")}'
            f'<div class="view-container" id="viewContainer"><div class="code-gutter" id="codeGutter"><div class="code-gutter-inner" id="codeGutterInner"><table class="code-gutter-table" role="presentation"><tbody>{gutter_rows}</tbody></table></div></div><div class="code-scroll" id="codeScroll"><table class="code-table" role="presentation"><tbody>{code_rows}</tbody></table></div></div><script>{build_vertical_bias_wheel_js(view_container_id="viewContainer", code_scroll_id="codeScroll")}{build_gutter_scroll_sync_js(code_scroll_id="codeScroll", gutter_id="codeGutter", gutter_inner_id="codeGutterInner")}{build_line_selection_js(table_selector=".code-table", gutter_selector=".code-gutter-table")}{preview_text_size_sync_js}</script></body></html>'
        )
    if ext == ".md":
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        content_json = json.dumps(content)
        rel_json = json.dumps(rel.replace("\\", "/"))
        prefix_json = json.dumps(prefix)
        has_fenced_code = "```" in content
        has_math = bool(re.search(r"(\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$\$[\s\S]+?\$\$|(?<!\$)\$[^$\n]+\$)", content))
        prism_aliases = {
            "py": "python",
            "python": "python",
            "js": "javascript",
            "javascript": "javascript",
            "node": "javascript",
            "ts": "typescript",
            "typescript": "typescript",
            "tsx": "typescript",
            "sh": "bash",
            "bash": "bash",
            "shell": "bash",
            "zsh": "bash",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "css": "css",
            "html": "markup",
            "xml": "markup",
            "svg": "markup",
            "sql": "sql",
        }
        prism_langs: list[str] = []
        if has_fenced_code:
            for match in re.finditer(r"```([^\n`]*)", content):
                raw_lang = str(match.group(1) or "").strip().split(" ", 1)[0].strip().lower()
                if not raw_lang:
                    continue
                resolved_lang = prism_aliases.get(raw_lang)
                if not resolved_lang or resolved_lang in prism_langs:
                    continue
                prism_langs.append(resolved_lang)
        markdown_head_tags = ['<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>']
        if has_fenced_code:
            markdown_head_tags.extend([
                '<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>',
            ])
            markdown_head_tags.extend(
                f'<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-{lang}.min.js"></script>'
                for lang in prism_langs
            )
        if has_math:
            markdown_head_tags.extend([
                '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">',
                '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>',
                '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>',
            ])
        markdown_head_libs = "".join(markdown_head_tags)
        markdown_preview_css = _chat_markdown_preview_css()
        initial_preview_theme = "light" if str((theme_palette or {}).get("theme") or "").lower() == "light" else "dark"
        markdown_theme_css = (
            f':root[data-preview-theme="dark"]{{color-scheme:dark;--bg-rgb:{str(dark_theme_palette.get("dark_bg_channels") or "0, 0, 0")};--bg:{str(dark_theme_palette.get("dark_bg") or DARK_BG)};--fg:{str(dark_theme_palette.get("light_fg") or LIGHT_FG)};--muted:{str(dark_theme_palette.get("gray_muted") or "rgb(158,158,158)")};--icon-fg:{str(dark_theme_palette.get("icon_fg") or "rgb(255,255,255)")};--icon-muted:{str(dark_theme_palette.get("icon_muted") or "rgb(158,158,158)")};--icon-hover:{str(dark_theme_palette.get("icon_hover") or "rgb(220,220,220)")};--inline-file-link-fg:var(--link-blue);--code-copy-bg:transparent;--code-copy-hover-bg:{str(dark_theme_palette.get("code_copy_hover_bg") or "rgba(255,255,255,0.09)")};--external-link-fg:rgb(255,107,107);--link-blue:rgb(88,166,255);--link-blue-channels:88,166,255;--git-ins-green:rgb(74,222,128);--git-ins-green-channels:74,222,128;--git-del-red:rgb(248,113,113);--git-del-red-channels:248,113,113;--code-bg:rgba(255,255,255,0.05);--code-scrollbar-thumb:rgba(255,255,255,0.45);--code-scrollbar-thumb-hover:rgba(255,255,255,0.65);--line:{str(dark_theme_palette.get("line") or pane_line)};--line-strong:{str(dark_theme_palette.get("line_strong") or "rgba(255,255,255,0.12)")};}}'
            'html[data-preview-theme="light"]{color-scheme:light;--bg-rgb:255,255,255;--bg:rgb(255,255,255);--fg:rgb(0,0,0);--muted:rgb(120,120,120);--icon-fg:rgb(0,0,0);--icon-muted:rgb(120,120,120);--icon-hover:rgb(35,35,35);--inline-file-link-fg:var(--link-blue);--code-copy-bg:transparent;--code-copy-hover-bg:rgba(0,0,0,0.08);--external-link-fg:rgb(207,34,46);--link-blue:rgb(9,105,218);--link-blue-channels:9,105,218;--git-ins-green:rgb(26,127,55);--git-ins-green-channels:26,127,55;--git-del-red:rgb(207,34,46);--git-del-red-channels:207,34,46;--code-bg:rgba(0,0,0,0.05);--code-scrollbar-thumb:rgba(0,0,0,0.25);--code-scrollbar-thumb-hover:rgba(0,0,0,0.45);--line:rgba(0,0,0,0.10);--line-strong:rgba(0,0,0,0.18);}'
            'html,body{background:transparent;color:var(--fg)}'
            'html[data-preview-explicit-bg="1"] body{background:var(--bg)}'
            '.md-preview-shell{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;background:transparent;scrollbar-gutter:auto;padding-top:0}'
            'html[data-preview-explicit-bg="1"] .md-preview-shell{background:var(--bg)}'
        )
        markdown_top_offset = "max(48px, calc(21px + env(safe-area-inset-top)))" if embed else "0px"
        markdown_layout_css = (
            f'.md-preview-shell>.md-body{{padding:calc(14px + {markdown_top_offset}) 16px 18px}}'
        )
        return (
            f'<!DOCTYPE html><html data-preview-theme="{initial_preview_theme}" data-agent-font-mode="{agent_font_mode}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>{html_escape(filename)}</title>'
            f'{markdown_head_libs}'
            f'<style>{base_css}{markdown_theme_css}{markdown_preview_css}{markdown_layout_css}'
            '</style></head>'
            f'<body>{header.format(icon="📝")}<div class="md-preview-shell"><div class="md-body" id="out"></div></div>'
            f'''<script>
const __mdText = {content_json};
const __mdRel = {rel_json};
const __fileBase = {prefix_json};
const __previewEmbed = {json.dumps(embed)};
const __previewPane = {json.dumps(pane)};
const __previewBasePath = {prefix_json};
const __previewAgentFontMode = {json.dumps(agent_font_mode)};
const __previewAgentTextSize = {json.dumps(resolved_text_size)};
const __previewMessageBold = {json.dumps(bool(message_bold))};
const __rawBase = `${{__fileBase}}/file-raw?path=`;
const __root = document.documentElement;
const __isExternalSrc = (src) => /^(https?:|data:|blob:|file:|\\/\\/)/i.test(src || "");
const buildPreviewHref = (relPath) => {{
  const params = new URLSearchParams();
  params.set("path", String(relPath || ""));
  if (__previewEmbed) params.set("embed", "1");
  if (__previewPane) params.set("pane", "1");
  if (__previewBasePath) params.set("base_path", __previewBasePath);
  if (__previewAgentFontMode) params.set("agent_font_mode", __previewAgentFontMode);
  if (__previewAgentTextSize) params.set("agent_text_size", String(__previewAgentTextSize));
  params.set("message_bold", __previewMessageBold ? "1" : "0");
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
const mathRenderOptions = {{
  delimiters: [
{{left: "$$", right: "$$", display: true}},
{{left: "$", right: "$", display: false}},
{{left: "\\\\[", right: "\\\\]", display: true}}
  ],
  ignoredClasses: ["no-math"],
  throwOnError: false
}};
const renderMarkdown = (text) => {{
  if (typeof marked === "undefined") return "<pre>" + escapeHtml(text) + "</pre>";
  try {{
const mathBlocks = [];
let placeholderCount = 0;
const codeBlocks = [];
let codeCount = 0;
let processedText = String(text || "").replace(/(```[\\s\\S]*?```|`[^`\\n]+`)/g, (match) => {{
  const id = `code-placeholder-${{codeCount++}}`;
  codeBlocks.push({{ id, content: match }});
  return `\\x00CODE:${{id}}\\x00`;
}});
processedText = processedText.replace(/(?<!\\$)\\$([A-Z_][A-Z0-9_]+)/g, '<span class="no-math">&#36;$1</span>');
processedText = processedText.replace(/\\$([{{(]][^}})\\n]*[}})])/g, '<span class="no-math">&#36;$1</span>');
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
tempDiv.querySelectorAll(".MATH_SAFE_BLOCK").forEach((span) => {{
  const block = mathBlocks.find((entry) => entry.id === span.dataset.id);
  if (block) span.outerHTML = block.content;
}});
if (mathBlocks.length) {{
  const marker = document.createElement("span");
  marker.className = "math-render-needed";
  marker.hidden = true;
  tempDiv.prepend(marker);
}}
if (typeof Prism !== "undefined") {{
  tempDiv.querySelectorAll('code[class*="language-"]').forEach((codeEl) => {{
    if (codeEl.classList.contains("language-diff")) return;
    Prism.highlightElement(codeEl);
  }});
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
const applyPreviewTheme = (theme, baseTheme = "dark") => {{
  const nextTheme = theme === "light" ? "light" : "dark";
  const nextBase = baseTheme === "light" ? "light" : "dark";
  __root.setAttribute("data-preview-theme", nextTheme);
  if (nextTheme === nextBase) {{
    __root.removeAttribute("data-preview-explicit-bg");
  }} else {{
    __root.setAttribute("data-preview-explicit-bg", "1");
  }}
}};
window.__agentIndexApplyPreviewTheme = applyPreviewTheme;
const renderMathInScope = (scope) => {{
  if (!scope || !scope.querySelector(".math-render-needed") || typeof renderMathInElement !== "function") return;
  renderMathInElement(scope, mathRenderOptions);
  scope.querySelectorAll(".math-render-needed").forEach((marker) => marker.remove());
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
  applyPreviewTheme(data.theme, data.baseTheme);
}});
window.addEventListener("message", (event) => {{
  const data = event?.data;
  if (!data || data.type !== "agent-preview-text-size") return;
  const sz = Number(data.size);
  if (!Number.isFinite(sz) || sz < 8) return;
  document.documentElement.style.setProperty("--message-text-size", sz + "px");
  document.documentElement.style.setProperty("--message-text-line-height", (sz + 9) + "px");
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
        f'<style>{base_css}body{{background:{embed_bg};color:{pane_fg};font-family:var(--code-font-family);font-size:13px}}'
        f'.hdr{{padding:10px 16px;background:{embed_bg};border-bottom:1px solid {pane_line};display:flex;align-items:center;gap:8px}}'
        f'.fn{{font-weight:700;font-size:14px;color:{pane_fg}}}'
        f'pre{{margin:0;padding:16px;white-space:pre;overflow:auto;height:{pre_height};background:{embed_bg};padding-top:calc(16px + var(--tpad,0px))}}</style></head>'
        f'<body>{header.format(icon="📄")}<pre>{escaped}</pre></body></html>'
    )
