from __future__ import annotations

import logging
import json
import os
import re
from html import escape as html_escape
from urllib.parse import quote as url_quote

from ..color_constants import DARK_BG, LIGHT_FG, resolve_theme_palette
from ..runtime.state import load_hub_settings
from .preview_3d import render_3d_preview
from .view_scripts import (
    build_gutter_scroll_sync_js,
    build_line_selection_js,
    build_progressive_loader_js,
    build_vertical_bias_wheel_js,
)


def highlight_text(escaped_text: str, ext: str, *, theme_comment: str, theme_keyword: str, theme_string: str,
                    theme_number: str, theme_func: str, theme_type: str, theme_prop: str,
                    theme_tag: str, theme_punct: str, theme_builtin: str) -> str:
    def hl(pattern, replacement, value):
        parts = re.split(r"(<[^>]*>)", value)
        return "".join(re.sub(pattern, replacement, chunk) if not chunk.startswith("<") else chunk for chunk in parts)

    if ext in {".py", ".sh", ".yaml", ".yml"}:
        escaped_text = re.sub(r"(^[ \t]*#[^\n]*)", rf'<span style="color:{theme_comment}">\1</span>', escaped_text, flags=re.MULTILINE)
    elif ext in {".js", ".ts", ".css", ".sql", ".json"}:
        escaped_text = re.sub(r"(//[^\n]*)", rf'<span style="color:{theme_comment}">\1</span>', escaped_text)
    elif ext == ".tex":
        escaped_text = re.sub(r"(^[ \t]*%[^\n]*)", rf'<span style="color:{theme_comment}">\1</span>', escaped_text, flags=re.MULTILINE)

    escaped_text = hl(r'("(?:[^"\\<\n]|\\.)*"|\'(?:[^\'\\<\n]|\\.)*\')', rf'<span style="color:{theme_string}">\1</span>', escaped_text)
    escaped_text = hl(r"(?<![\w#])(-?\d+(?:\.\d+)?)", rf'<span style="color:{theme_number}">\1</span>', escaped_text)

    if ext in {".json", ".yaml", ".yml"}:
        escaped_text = hl(r"(^[ \t-]*)([A-Za-z_][\w.-]*)(\s*:)", rf'\1<span style="color:{theme_prop}">\2</span>\3', escaped_text)
    if ext == ".tex":
        escaped_text = hl(r"(\\[A-Za-z@]+)", rf'<span style="color:{theme_tag}">\1</span>', escaped_text)
    if ext == ".html":
        escaped_text = hl(r"(&lt;/?)([A-Za-z][\w:-]*)", rf'\1<span style="color:{theme_tag}">\2</span>', escaped_text)
        escaped_text = hl(r"([A-Za-z_:][\w:.-]*)(=)(&quot;.*?&quot;)", rf'<span style="color:{theme_prop}">\1</span>\2<span style="color:{theme_string}">\3</span>', escaped_text)
    if ext == ".css":
        escaped_text = hl(r"(^[ \t]*)([.#]?[A-Za-z_-][\w:-]*)(\s*\{)", rf'\1<span style="color:{theme_tag}">\2</span>\3', escaped_text)
        escaped_text = hl(r"([A-Za-z-]+)(\s*:)", rf'<span style="color:{theme_prop}">\1</span>\2', escaped_text)
    if ext in {".py", ".js", ".sh", ".sql"}:
        escaped_text = hl(r"(^[ \t]*@[\w.]+)", rf'<span style="color:{theme_tag}">\1</span>', escaped_text)

    escaped_text = hl(r"\b(def|class|import|from|return|if|else|elif|for|while|try|except|with|as|yield|await|async|function|const|let|var|type|interface|enum|public|private|protected|static|readonly|do|switch|case|default|break|continue|new|delete|typeof|instanceof|void|this|super|in|of|null|undefined|true|false)\b", rf'<span style="color:{theme_keyword}">\1</span>', escaped_text)
    escaped_text = hl(r"\b(str|int|float|bool|list|dict|tuple|set|None|self|cls|SELECT|FROM|WHERE|GROUP|ORDER|BY|JOIN|LEFT|RIGHT|INNER|OUTER|LIMIT|INSERT|UPDATE|DELETE|CREATE|TABLE|VALUES)\b", rf'<span style="color:{theme_type}">\1</span>', escaped_text)
    escaped_text = hl(r"\b(print|len|range|echo|printf|console|log)\b", rf'<span style="color:{theme_builtin}">\1</span>', escaped_text)
    escaped_text = hl(r"\b([A-Za-z_][\w]*)(?=\()", rf'<span style="color:{theme_func}">\1</span>', escaped_text)
    escaped_text = hl(r"(?<=\.)\b([A-Za-z_][\w]*)\b", rf'<span style="color:{theme_prop}">\1</span>', escaped_text)
    escaped_text = hl(r"([{}()[\],.:;=+\-/*<>])", rf'<span style="color:{theme_punct}">\1</span>', escaped_text)
    return escaped_text

def render_file_view(
    runtime,
    rel: str,
    *,
    embed: bool = False,
    pane: bool = False,
    base_path: str = "",
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
    default_agent_font_family = (
        '"anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Meiryo", sans-serif'
        if agent_font_mode == "gothic"
        else '"anthropicSerif", "anthropicSerif Fallback", "Anthropic Serif", "Hiragino Mincho ProN", "Yu Mincho", "YuMincho", "Noto Serif JP", Georgia, "Times New Roman", Times, serif'
    )
    code_font_family = (
        '"SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, "Liberation Mono", monospace'
    )
    agent_font_family = str(agent_font_family or default_agent_font_family).strip() or default_agent_font_family
    try:
        resolved_text_size = int(agent_text_size or 13)
    except (TypeError, ValueError):
        resolved_text_size = 13
    resolved_text_size = max(11, min(18, resolved_text_size))
    resolved_line_height = resolved_text_size + 9
    theme_palette = None
    if runtime.repo_root:
        try:
            theme_palette = resolve_theme_palette(load_hub_settings(runtime.repo_root))
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
    pane_bg = str((theme_palette or {}).get("dark_bg") or DARK_BG)
    embed_bg = "transparent" if embed else pane_bg
    pane_fg = str((theme_palette or {}).get("light_fg") or LIGHT_FG)
    pane_muted = pane_fg
    pane_line = "rgba(255,255,255,0.08)"
    pane_gutter_text = "rgba(252,252,252,0.68)"
    pane_gutter_bg = "transparent"
    pane_gutter_divider = "rgba(255,255,255,0.16)"
    gutter_padding_left = 1
    gutter_padding_right = 5
    code_cell_padding_left = 12
    markdown_body_weight = 620 if message_bold else 360
    markdown_body_variation = "normal" if message_bold else '"wght" 360'
    markdown_heading_weight = 700 if message_bold else 600
    markdown_heading_variation = "normal" if message_bold else '"wght" 530'
    markdown_strong_weight = 700 if message_bold else 530
    markdown_strong_variation = f'"wght" {markdown_strong_weight}'
    markdown_gothic_body_variation = f'"wght" {markdown_body_weight},"opsz" 16'
    markdown_gothic_strong_variation = f'"wght" {markdown_strong_weight},"opsz" 16'
    preview_body_weight = 620 if message_bold else 360
    preview_body_variation = "normal" if message_bold else '"wght" 360'
    preview_code_weight = 500 if message_bold else 360
    preview_code_variation = "normal" if message_bold else '"wght" 360'
    preview_scrollbar_thumb = "rgba(255,255,255,0.20)"
    preview_scrollbar_thumb_hover = "rgba(255,255,255,0.34)"
    preview_scrollbar_thumb_light = "rgba(20,20,19,0.18)"
    preview_scrollbar_thumb_hover_light = "rgba(20,20,19,0.30)"
    preview_selected_line_bg = "rgba(255,255,255,0.10)"
    font_base = prefix or ""
    font_face_css = (
        f'@font-face{{font-family:"anthropicSerif";src:url("{font_base}/font/anthropic-serif-roman.ttf") format("truetype");font-style:normal;font-weight:300 800;font-display:swap}}'
        f'@font-face{{font-family:"anthropicSerif";src:url("{font_base}/font/anthropic-serif-italic.ttf") format("truetype");font-style:italic;font-weight:300 800;font-display:swap}}'
        f'@font-face{{font-family:"anthropicSans";src:url("{font_base}/font/anthropic-sans-roman.ttf") format("truetype");font-style:normal;font-weight:300 800;font-display:swap}}'
        f'@font-face{{font-family:"anthropicSans";src:url("{font_base}/font/anthropic-sans-italic.ttf") format("truetype");font-style:italic;font-weight:300 800;font-display:swap}}'
        f'@font-face{{font-family:"jetbrainsMono";src:local("JetBrains Mono"),local("JetBrainsMono-Regular"),url("{font_base}/font/jetbrains-mono.ttf") format("truetype-variations"),url("{font_base}/font/jetbrains-mono.ttf") format("truetype");font-style:normal;font-weight:100 800;font-display:swap}}'
    )
    base_css = (
        f':root{{color-scheme: dark;--agent-font-family:{agent_font_family};--code-font-family:{code_font_family};--message-text-size:{resolved_text_size}px;--message-text-line-height:{resolved_line_height}px;--tpad:{"0px" if pane else "max(72px, calc(32px + env(safe-area-inset-top)))" if embed else "0px"};--preview-scrollbar-size:6px;--preview-scrollbar-thumb:{preview_scrollbar_thumb};--preview-scrollbar-thumb-hover:{preview_scrollbar_thumb_hover};--preview-gutter-bg:{pane_gutter_bg};--preview-gutter-divider:{pane_gutter_divider};--preview-selected-line-bg:{preview_selected_line_bg};}}'
        f"{font_face_css}"
        f"*{{box-sizing:border-box}}"
        '.md-preview-shell,.view-container,.html-preview-text-wrap,.html-preview-text-scroll,.code-scroll,.table-scroll,.katex-display,.md-body pre{scrollbar-width:thin;scrollbar-color:var(--preview-scrollbar-thumb) transparent}'
        '.md-preview-shell::-webkit-scrollbar,.view-container::-webkit-scrollbar,.html-preview-text-wrap::-webkit-scrollbar,.html-preview-text-scroll::-webkit-scrollbar,.code-scroll::-webkit-scrollbar,.table-scroll::-webkit-scrollbar,.katex-display::-webkit-scrollbar,.md-body pre::-webkit-scrollbar{width:var(--preview-scrollbar-size);height:var(--preview-scrollbar-size)}'
        '.md-preview-shell::-webkit-scrollbar-track,.view-container::-webkit-scrollbar-track,.html-preview-text-wrap::-webkit-scrollbar-track,.html-preview-text-scroll::-webkit-scrollbar-track,.code-scroll::-webkit-scrollbar-track,.table-scroll::-webkit-scrollbar-track,.katex-display::-webkit-scrollbar-track,.md-body pre::-webkit-scrollbar-track{background:transparent}'
        '.md-preview-shell::-webkit-scrollbar-thumb,.view-container::-webkit-scrollbar-thumb,.html-preview-text-wrap::-webkit-scrollbar-thumb,.html-preview-text-scroll::-webkit-scrollbar-thumb,.code-scroll::-webkit-scrollbar-thumb,.table-scroll::-webkit-scrollbar-thumb,.katex-display::-webkit-scrollbar-thumb,.md-body pre::-webkit-scrollbar-thumb{background:var(--preview-scrollbar-thumb);border-radius:999px;border:1px solid transparent;background-clip:padding-box}'
        '.md-preview-shell::-webkit-scrollbar-thumb:hover,.view-container::-webkit-scrollbar-thumb:hover,.html-preview-text-wrap::-webkit-scrollbar-thumb:hover,.html-preview-text-scroll::-webkit-scrollbar-thumb:hover,.code-scroll::-webkit-scrollbar-thumb:hover,.table-scroll::-webkit-scrollbar-thumb:hover,.katex-display::-webkit-scrollbar-thumb:hover,.md-body pre::-webkit-scrollbar-thumb:hover{background:var(--preview-scrollbar-thumb-hover);background-clip:padding-box}'
        f"html,body{{margin:0;background:{embed_bg};color:{pane_fg};font-family:var(--agent-font-family);display:flex;flex-direction:column;height:100vh;font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:{preview_body_weight};font-synthesis-weight:none;font-synthesis-style:none;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;font-optical-sizing:auto;font-variation-settings:{preview_body_variation}}}"
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

    def build_text_table_markup(text_content: str, *, text_ext: str) -> tuple[str, str, int, int]:
        escaped = highlight_text(
            html_escape(text_content),
            text_ext,
            theme_comment="#5c6370",
            theme_keyword="#c678dd",
            theme_string="#98c379",
            theme_number="#d19a66",
            theme_func="#61afef",
            theme_type="#e5c07b",
            theme_prop="#56b6c2",
            theme_tag="#e06c75",
            theme_punct="#7f848e",
            theme_builtin="#56b6c2",
        )
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
                text_ext=".html",
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
                text_ext=".html",
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
            'if(data.type!=="agent-index-file-preview-mode")return;'
            'setMode(data.mode);'
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
            f'.html-preview-gutter-table{{border-collapse:collapse;width:100%;table-layout:fixed;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:{preview_code_weight};font-synthesis-weight:none;font-synthesis-style:none;font-variation-settings:{preview_code_variation}}}'
            '.html-preview-gutter-table td{padding:0;vertical-align:top}'
            f'.html-preview-gutter-table .ln{{padding:0 {gutter_padding_right}px 0 {gutter_padding_left}px;width:{gutter_width}px;min-width:{gutter_width}px;box-sizing:border-box;text-align:right;color:{pane_gutter_text};user-select:none;font-variant-numeric:tabular-nums;line-height:var(--message-text-line-height);font-family:var(--code-font-family);font-size:var(--message-text-size);background:transparent}}'
            '.html-preview-text-scroll{position:relative;z-index:1;flex:1;min-height:0;min-width:0;width:auto;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:auto;padding-top:var(--tpad,0px)}'
            f'.html-preview-text-table{{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:{preview_code_weight};font-synthesis-weight:none;font-synthesis-style:none;font-variation-settings:{preview_code_variation}}}'
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
            text_ext=ext,
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
            f'.code-gutter-table{{border-collapse:collapse;width:100%;table-layout:fixed;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:{preview_code_weight};font-synthesis-weight:none;font-synthesis-style:none;font-variation-settings:{preview_code_variation}}}'
            '.code-gutter-table td{padding:0;vertical-align:top}'
            f'.code-gutter-table .ln{{padding:0 {gutter_padding_right}px 0 {gutter_padding_left}px;width:{gutter_width}px;min-width:{gutter_width}px;box-sizing:border-box;text-align:right;color:{pane_gutter_text};user-select:none;font-variant-numeric:tabular-nums;line-height:var(--message-text-line-height);font-family:var(--code-font-family);font-size:var(--message-text-size);background:transparent}}'
            '.code-scroll{position:relative;z-index:1;flex:1;min-width:0;min-height:0;width:auto;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:auto;padding-top:var(--tpad,0px)}'
            '.code-table{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;'
            f'font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:{preview_code_weight};'
            f'font-synthesis-weight:none;font-synthesis-style:none;font-variation-settings:{preview_code_variation}}}'
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
            f'</div><script>{build_vertical_bias_wheel_js(view_container_id="viewContainer", code_scroll_id="codeScroll")}{build_gutter_scroll_sync_js(code_scroll_id="codeScroll", gutter_id="codeGutter", gutter_inner_id="codeGutterInner")}{build_line_selection_js(table_selector=".code-table", gutter_selector=".code-gutter-table")}{progressive_loader_js}</script></body></html>'
        )
    if is_text_like and ext != ".md":
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        gutter_rows, code_rows, gutter_width, title_offset = build_text_table_markup(
            content,
            text_ext=ext,
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
            f'.code-gutter-table{{border-collapse:collapse;width:100%;table-layout:fixed;font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:{preview_code_weight};font-synthesis-weight:none;font-synthesis-style:none;font-variation-settings:{preview_code_variation}}}'
            '.code-gutter-table td{padding:0;vertical-align:top}'
            f'.code-gutter-table .ln{{padding:0 {gutter_padding_right}px 0 {gutter_padding_left}px;width:{gutter_width}px;min-width:{gutter_width}px;box-sizing:border-box;text-align:right;color:{pane_gutter_text};user-select:none;font-variant-numeric:tabular-nums;line-height:var(--message-text-line-height);font-family:var(--code-font-family);font-size:var(--message-text-size);background:transparent}}'
            '.code-scroll{position:relative;z-index:1;flex:1;min-width:0;min-height:0;width:auto;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:auto;padding-top:var(--tpad,0px)}'
            '.code-table{border-collapse:collapse;min-width:100%;width:max-content;table-layout:auto;'
            f'font-family:var(--code-font-family);font-size:var(--message-text-size);line-height:var(--message-text-line-height);font-weight:{preview_code_weight};'
            f'font-synthesis-weight:none;font-synthesis-style:none;font-variation-settings:{preview_code_variation}}}'
            '.code-table td{padding:0;vertical-align:top}'
            '.code-table .lc{padding-left:12px;padding-right:min(7vw,52px)}'
            '.code-gutter-table tbody tr.is-selected .ln,.code-table tbody tr.is-selected .lc{background:var(--preview-selected-line-bg)}'
            '.code-table .lc pre{margin:0;min-height:var(--message-text-line-height);line-height:var(--message-text-line-height);font:inherit;white-space:pre}'
            '.code-gutter-table tbody tr:last-child .ln,.code-table tbody tr:last-child .lc pre{padding-bottom:24px}'
            '</style></head>'
            f'<body>{header.format(icon="📄")}'
            f'<div class="view-container" id="viewContainer"><div class="code-gutter" id="codeGutter"><div class="code-gutter-inner" id="codeGutterInner"><table class="code-gutter-table" role="presentation"><tbody>{gutter_rows}</tbody></table></div></div><div class="code-scroll" id="codeScroll"><table class="code-table" role="presentation"><tbody>{code_rows}</tbody></table></div></div><script>{build_vertical_bias_wheel_js(view_container_id="viewContainer", code_scroll_id="codeScroll")}{build_gutter_scroll_sync_js(code_scroll_id="codeScroll", gutter_id="codeGutter", gutter_inner_id="codeGutterInner")}{build_line_selection_js(table_selector=".code-table", gutter_selector=".code-gutter-table")}</script></body></html>'
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
        return (
            f'<!DOCTYPE html><html data-preview-theme="dark" data-agent-font-mode="{agent_font_mode}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>{html_escape(filename)}</title>'
            f'{markdown_head_libs}'
            f'<style>{base_css}'
            f':root{{--bg:transparent;--text:{pane_fg};--meta:rgba(252,252,252,0.62);--line:{pane_line};--line-strong:rgba(255,255,255,0.12);--inline-code-fg:rgb(196,201,209);--code-block-bg:rgba(255,255,255,0.02);--code-block-border:rgba(255,255,255,0.08);--code-block-shadow:none;--code-copy-bg:rgba(0,0,0,0.34);--code-copy-hover-bg:rgba(255,255,255,0.06);--message-text-size:{resolved_text_size}px;--message-text-line-height:{resolved_line_height}px;--link:#58a6ff;--agent-font-family:{agent_font_family};}}'
            f':root[data-preview-theme="light"]{{color-scheme:light;--bg:rgb(255,255,255);--text:rgb(20,20,19);--meta:rgba(20,20,19,0.56);--line:rgba(20,20,19,0.10);--line-strong:rgba(20,20,19,0.18);--inline-code-fg:rgb(52,52,52);--code-block-bg:rgba(20,20,19,0.02);--code-block-border:rgba(20,20,19,0.08);--code-copy-bg:rgba(255,255,255,0.88);--code-copy-hover-bg:rgba(20,20,19,0.06);--link:#245bdb;--preview-scrollbar-thumb:{preview_scrollbar_thumb_light};--preview-scrollbar-thumb-hover:{preview_scrollbar_thumb_hover_light}}}'
            'body{background:var(--bg);color:var(--text)}'
            '.md-preview-shell{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;background:var(--bg);scrollbar-gutter:auto;padding-top:var(--tpad,0px)}'
            f'.md-body{{padding:14px 16px 18px;flex:1;min-width:0;overflow-x:hidden;font-family:var(--agent-font-family);font-style:normal;font-size:var(--message-text-size,13px);line-height:var(--message-text-line-height,22px);font-weight:{markdown_body_weight};color:var(--text);font-synthesis-weight:none;font-synthesis-style:none;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;font-optical-sizing:auto;font-variation-settings:{markdown_body_variation}}}'
            f'html[data-agent-font-mode="gothic"] .md-body{{letter-spacing:-0.01em;font-variation-settings:{markdown_gothic_body_variation}}}'
            '.md-body>*:first-child{margin-top:0}.md-body>*:last-child{margin-bottom:0}'
            '.md-body,.md-body p,.md-body li,.md-body li p,.md-body blockquote,.md-body blockquote p{white-space:normal;overflow-wrap:anywhere;word-break:normal}'
            '.md-body p{margin:0 0 .6em}'
            f'.md-body h1,.md-body h2,.md-body h3,.md-body h4{{margin:.8em 0 .3em;font-weight:{markdown_heading_weight};font-variation-settings:{markdown_heading_variation};font-synthesis:weight;line-height:1.2}}'
            'html[data-agent-font-mode="gothic"] .md-body h1,html[data-agent-font-mode="gothic"] .md-body h2,html[data-agent-font-mode="gothic"] .md-body h3,html[data-agent-font-mode="gothic"] .md-body h4{font-weight:700;font-variation-settings:"wght" 700,"opsz" 16}'
            '.md-body h1{font-size:22px}.md-body h2{font-size:18px}.md-body h3{font-size:1.05em}.md-body h4{font-size:1em}'
            '.md-body ul,.md-body ol{margin:.4em 0 .6em;padding-left:1.5em}.md-body li{margin:.15em 0;line-height:calc(var(--message-text-line-height,22px) + 2px)}.md-body li p{margin:0}'
            '.md-body :not(pre)>code{font-family:var(--code-font-family);font-style:normal;font-size:0.92em;font-weight:450;font-synthesis-weight:none;font-variation-settings:normal;letter-spacing:normal;color:var(--inline-code-fg);line-height:inherit;background:transparent;border:none;border-radius:0;padding:0}'
            '.katex{font-family:KaTeX_Main,Times New Roman,serif;font-size:19px;font-weight:400;line-height:23px}'
            '.table-scroll{display:block;width:100%;max-width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;margin:.5em 0}.table-scroll>table{width:100%;margin:0}'
            '.katex-display{display:block;margin:1.2em 0;width:100%;max-width:100%;padding-inline:0;overflow-x:auto;overflow-y:hidden;text-align:left;-webkit-overflow-scrolling:touch}.katex-display>.katex{display:table;width:max-content;max-width:none;margin:0 auto}'
            '.md-body pre{display:block;width:100%;max-width:100%;box-sizing:border-box;position:relative;background:var(--code-block-bg);border:1px solid var(--code-block-border);border-radius:14px;padding:14px 16px;margin:0;overflow-x:auto;overflow-y:hidden;white-space:pre;word-break:normal;box-shadow:var(--code-block-shadow);-webkit-overflow-scrolling:touch}'
            '.md-body .code-block-wrap{position:relative;display:block;margin:14px 0;overflow-x:hidden}'
            '.md-body .code-block-wrap .code-copy-btn{position:absolute;top:8px;right:8px;z-index:1;width:30px;height:30px;padding:0;border:1px solid var(--code-block-border);border-radius:9px;background:var(--code-copy-bg);color:var(--meta);cursor:pointer;display:flex;align-items:center;justify-content:center;opacity:0;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);transition:opacity .15s,background .15s,color .15s,border-color .15s}'
            '.md-body .code-block-wrap:hover .code-copy-btn{opacity:1}@media (pointer:coarse){.md-body .code-block-wrap .code-copy-btn{opacity:.72}}'
            '.md-body .code-block-wrap .code-copy-btn:hover{background:var(--code-copy-hover-bg);color:var(--text);border-color:var(--line-strong)}.md-body .code-block-wrap .code-copy-btn svg{width:15px;height:15px}'
            f'.md-body pre code{{font-family:var(--code-font-family);font-style:normal;font-size:var(--message-text-size);font-weight:{preview_code_weight};font-synthesis-weight:none;font-variation-settings:{preview_code_variation};letter-spacing:normal;line-height:var(--message-text-line-height);color:var(--text);background:none;border:none;padding:0;border-radius:0;white-space:pre;word-break:normal;overflow-wrap:normal}}'
            '.md-body pre code .token.comment,.md-body pre code .token.prolog,.md-body pre code .token.doctype,.md-body pre code .token.cdata{color:rgb(100,110,130)}'
            '.md-body pre code .token.punctuation{color:rgb(150,160,175)}'
            '.md-body pre code .token.property,.md-body pre code .token.tag,.md-body pre code .token.boolean,.md-body pre code .token.number,.md-body pre code .token.constant,.md-body pre code .token.symbol{color:rgb(140,170,210)}'
            '.md-body pre code .token.selector,.md-body pre code .token.attr-name,.md-body pre code .token.string,.md-body pre code .token.char,.md-body pre code .token.builtin{color:rgb(160,190,200)}'
            '.md-body pre code .token.operator,.md-body pre code .token.entity,.md-body pre code .token.url,.md-body pre code .token.variable{color:rgb(170,180,195)}'
            '.md-body pre code .token.atrule,.md-body pre code .token.attr-value,.md-body pre code .token.keyword{color:rgb(130,160,200)}'
            '.md-body pre code .token.function,.md-body pre code .token.class-name{color:rgb(175,195,220)}'
            '.md-body pre code .token.regex,.md-body pre code .token.important{color:rgb(190,170,140)}'
            '.md-body pre code .token.decorator{color:rgb(140,170,210)}'
            ':root[data-preview-theme="light"] .md-body pre code .token.comment,:root[data-preview-theme="light"] .md-body pre code .token.prolog,:root[data-preview-theme="light"] .md-body pre code .token.doctype,:root[data-preview-theme="light"] .md-body pre code .token.cdata{color:rgb(126,132,145)}'
            ':root[data-preview-theme="light"] .md-body pre code .token.punctuation{color:rgb(108,116,128)}'
            ':root[data-preview-theme="light"] .md-body pre code .token.property,:root[data-preview-theme="light"] .md-body pre code .token.tag,:root[data-preview-theme="light"] .md-body pre code .token.boolean,:root[data-preview-theme="light"] .md-body pre code .token.number,:root[data-preview-theme="light"] .md-body pre code .token.constant,:root[data-preview-theme="light"] .md-body pre code .token.symbol{color:rgb(48,92,176)}'
            ':root[data-preview-theme="light"] .md-body pre code .token.selector,:root[data-preview-theme="light"] .md-body pre code .token.attr-name,:root[data-preview-theme="light"] .md-body pre code .token.string,:root[data-preview-theme="light"] .md-body pre code .token.char,:root[data-preview-theme="light"] .md-body pre code .token.builtin{color:rgb(40,122,113)}'
            ':root[data-preview-theme="light"] .md-body pre code .token.operator,:root[data-preview-theme="light"] .md-body pre code .token.entity,:root[data-preview-theme="light"] .md-body pre code .token.url,:root[data-preview-theme="light"] .md-body pre code .token.variable{color:rgb(88,95,104)}'
            ':root[data-preview-theme="light"] .md-body pre code .token.atrule,:root[data-preview-theme="light"] .md-body pre code .token.attr-value,:root[data-preview-theme="light"] .md-body pre code .token.keyword{color:rgb(86,76,176)}'
            ':root[data-preview-theme="light"] .md-body pre code .token.function,:root[data-preview-theme="light"] .md-body pre code .token.class-name{color:rgb(23,87,152)}'
            ':root[data-preview-theme="light"] .md-body pre code .token.regex,:root[data-preview-theme="light"] .md-body pre code .token.important{color:rgb(149,92,35)}'
            ':root[data-preview-theme="light"] .md-body pre code .token.decorator{color:rgb(48,92,176)}'
            '.md-body code.language-diff{display:flex;flex-direction:column;gap:0}'
            '.md-body .diff-add{background:rgb(2,40,2);color:rgb(250,230,100);display:block;margin:0 -16px;padding:0 16px;line-height:20px}.md-body .diff-add .diff-sign{color:rgb(34,197,94)}'
            '.md-body .diff-del{background:rgb(61,1,0);display:block;margin:0 -16px;padding:0 16px;line-height:20px}.md-body .diff-del .diff-sign{color:rgb(239,68,68)}'
            ':root[data-preview-theme="light"] .md-body .diff-add{background:rgb(233,247,233);color:rgb(41,73,41)}:root[data-preview-theme="light"] .md-body .diff-add .diff-sign{color:rgb(38,134,74)}'
            ':root[data-preview-theme="light"] .md-body .diff-del{background:rgb(252,236,236);color:rgb(104,39,39)}:root[data-preview-theme="light"] .md-body .diff-del .diff-sign{color:rgb(186,63,63)}'
            '.md-body blockquote{border-left:3px solid rgba(255,255,255,0.2);margin:.5em 0;padding:.3em .8em;opacity:.85}'
            '.md-body hr{border:none;border-top:1px solid var(--line);margin:.8em 0}'
            '.md-body img{display:block;max-width:100%;max-height:60vh;width:auto;height:auto;margin:12px 0;border-radius:10px}'
            '.md-body table{display:table;table-layout:auto;border-collapse:collapse;width:100%;margin:.5em 0;font-size:var(--message-text-size,13px);line-height:21px}'
            '.md-body th,.md-body td{white-space:nowrap;border-top:1.5px solid rgba(255,255,255,0.12);border-bottom:1.5px solid rgba(255,255,255,0.12);border-left:none;border-right:none;padding:7.5px 12px;text-align:left;font-size:var(--message-text-size,13px);line-height:21px}'
            f'.md-body th{{background:transparent;font-weight:{markdown_strong_weight};border-top:none;border-bottom-color:rgba(255,255,255,0.28)}}.md-body td{{font-weight:{markdown_body_weight}}}'
            ':root[data-preview-theme="light"] .md-body blockquote{border-left-color:rgba(20,20,19,0.18);opacity:1}'
            ':root[data-preview-theme="light"] .md-body th,:root[data-preview-theme="light"] .md-body td{border-top-color:rgba(20,20,19,0.12);border-bottom-color:rgba(20,20,19,0.12)}'
            ':root[data-preview-theme="light"] .md-body th{border-bottom-color:rgba(20,20,19,0.22)}'
            f'.md-body a{{color:var(--link);text-decoration:none}}.md-body a:hover{{text-decoration:underline}}.md-body strong,.md-body b{{font-weight:{markdown_strong_weight};font-synthesis:weight;font-variation-settings:{markdown_strong_variation}}}.md-body em{{font-style:italic}}'
            f'html[data-agent-font-mode="gothic"] .md-body strong,html[data-agent-font-mode="gothic"] .md-body b{{font-variation-settings:{markdown_gothic_strong_variation}}}'
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
const applyPreviewTheme = (theme) => {{
  const nextTheme = theme === "light" ? "light" : "dark";
  __root.setAttribute("data-preview-theme", nextTheme);
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
  applyPreviewTheme(data.theme);
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
