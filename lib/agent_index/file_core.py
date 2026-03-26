from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from html import escape as html_escape
from pathlib import Path
from urllib.parse import quote as url_quote

from .file_preview_3d import render_3d_preview


class FileRuntime:
    MIME_TYPES = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".ico": "image/x-icon",
        ".pdf": "application/pdf",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".obj": "text/plain; charset=utf-8",
        ".stl": "model/stl",
        ".step": "application/step",
        ".stp": "application/step",
    }
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}
    TEXT_EXTS = {".py", ".js", ".json", ".yaml", ".yml", ".sh", ".sql", ".html", ".css", ".tex", ".txt", ".csv", ".log"}
    EDITABLE_TEXT_EXTS = TEXT_EXTS | {".md", ".ts", ".tsx", ".jsx", ".toml", ".ini", ".cfg", ".conf", ".rst", ".env"}
    PDF_EXTS = {".pdf"}
    VIDEO_EXTS = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
    }
    AUDIO_EXTS = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
    }
    MODEL_3D_EXTS = {".obj", ".stl", ".step", ".stp"}
    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache"}

    def __init__(self, *, workspace: str | Path):
        self.workspace = os.path.normpath(str(workspace))

    def _resolve_path(self, rel: str, *, allow_workspace_root: bool = False) -> str:
        rel = rel or ""
        if os.path.isabs(rel):
            full = os.path.normpath(rel)
        else:
            full = os.path.normpath(os.path.join(self.workspace, rel.lstrip("/")))
        if allow_workspace_root:
            if full != self.workspace and not full.startswith(self.workspace + os.sep):
                raise PermissionError("outside workspace")
        elif not full.startswith(self.workspace + os.sep):
            raise PermissionError("outside workspace")
        return full

    def files_exist(self, paths: list[str]) -> dict[str, bool]:
        """Check which paths exist within the workspace."""
        result = {}
        for rel in paths:
            try:
                full = self._resolve_path(rel, allow_workspace_root=True)
                result[rel] = os.path.exists(full)
            except (PermissionError, Exception):
                result[rel] = False
        return result

    def file_raw(self, rel: str):
        full = self._resolve_path(rel)
        ext = os.path.splitext(rel)[1].lower()
        with open(full, "rb") as f:
            raw = f.read()
        return self.MIME_TYPES.get(ext, "application/octet-stream"), raw

    def file_content(self, rel: str):
        full = self._resolve_path(rel, allow_workspace_root=True)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        ext = os.path.splitext(rel)[1].lstrip(".")
        return {"content": content, "ext": ext}

    @staticmethod
    def _is_probably_text_file(full: str) -> bool:
        try:
            with open(full, "rb") as f:
                sample = f.read(4096)
        except OSError:
            return False
        if not sample:
            return True
        if b"\x00" in sample:
            return False
        return True

    def can_open_in_editor(self, rel: str) -> bool:
        full = self._resolve_path(rel, allow_workspace_root=True)
        if not os.path.isfile(full):
            return False
        ext = os.path.splitext(full)[1].lower()
        if ext in {".html", ".htm", ".pdf"}:
            return self._pdf_browser_command(full) is not None
        return ext in self.EDITABLE_TEXT_EXTS or self._is_probably_text_file(full)

    @staticmethod
    def _pdf_browser_command(full: str) -> list[str] | None:
        uri = Path(full).resolve().as_uri()
        if sys.platform == "darwin":
            if FileRuntime._macos_app_exists("Safari"):
                return ["open", "-a", "Safari", uri]
            return None
        if shutil.which("xdg-open"):
            return ["xdg-open", full]
        return None

    @staticmethod
    def _macos_app_exists(app_name: str) -> bool:
        if sys.platform != "darwin" or not shutil.which("osascript"):
            return False
        try:
            result = subprocess.run(
                ["osascript", "-e", f'id of application "{app_name}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            return False
        return result.returncode == 0

    @staticmethod
    def _editor_command(full: str, line: int = 0) -> tuple[list[str], str]:
        configured = (os.environ.get("MULTIAGENT_EXTERNAL_EDITOR") or "").strip()
        if configured:
            if "{path}" in configured:
                return shlex.split(configured.format(path=full)), "custom"
            return shlex.split(configured) + [full], "custom"
        browser_cmd = FileRuntime._pdf_browser_command(full) if full.lower().endswith((".html", ".htm", ".pdf")) else None
        if browser_cmd:
            return browser_cmd, "system"
        line_arg = f":{line}" if line > 0 else ""
        if sys.platform == "darwin":
            if FileRuntime._macos_app_exists("CotEditor"):
                if line > 0:
                    # Use AppleScript to open at specific line
                    script = (
                        f'tell application "CotEditor"\n'
                        f'  activate\n'
                        f'  open POSIX file "{full}"\n'
                        f'  tell front document\n'
                        f'    jump to line {line}\n'
                        f'  end tell\n'
                        f'end tell'
                    )
                    return ["osascript", "-e", script], "lightweight"
                return ["open", "-na", "CotEditor", full], "lightweight"
            if FileRuntime._macos_app_exists("Sublime Text"):
                return ["open", "-na", "Sublime Text", f"{full}{line_arg}"], "lightweight"
            if FileRuntime._macos_app_exists("TextMate"):
                return ["open", "-na", "TextMate", full], "lightweight"
            if FileRuntime._macos_app_exists("BBEdit"):
                return ["open", "-na", "BBEdit", full], "lightweight"
        if shutil.which("code"):
            return ["code", "--new-window", "-g", f"{full}{line_arg}"], "vscode"
        if sys.platform == "darwin":
            return ["open", "-na", "Visual Studio Code", "--args", "--new-window", "--goto", f"{full}{line_arg}"], "vscode"
        return ["xdg-open", full], "system"

    @staticmethod
    def _shrink_vscode_window():
        if sys.platform != "darwin" or not shutil.which("osascript"):
            return
        script = '''
delay 0.35
tell application "Visual Studio Code" to activate
delay 0.2
        tell application "System Events"
            tell process "Code"
                if (count of windows) > 0 then
                    set position of front window to {108, 96}
                    set size of front window to {760, 560}
                end if
            end tell
        end tell
'''
        deadline = time.time() + 4.0
        while time.time() < deadline:
            try:
                subprocess.Popen(
                    ["osascript", "-e", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return
            except Exception:
                time.sleep(0.15)

    @staticmethod
    def _shrink_browser_window(app_name: str, process_name: str):
        if sys.platform != "darwin" or not shutil.which("osascript"):
            return
        script = f'''
delay 0.35
tell application "{app_name}" to activate
delay 0.2
tell application "System Events"
    tell process "{process_name}"
        if (count of windows) > 0 then
            set position of front window to {{120, 88}}
            set size of front window to {{720, 1440}}
        end if
    end tell
end tell
'''
        deadline = time.time() + 4.0
        while time.time() < deadline:
            try:
                subprocess.Popen(
                    ["osascript", "-e", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return
            except Exception:
                time.sleep(0.15)

    def open_in_editor(self, rel: str, line: int = 0):
        full = self._resolve_path(rel, allow_workspace_root=True)
        if not os.path.isfile(full):
            raise FileNotFoundError(full)
        ext = os.path.splitext(full)[1].lower()
        if ext not in self.EDITABLE_TEXT_EXTS and ext not in {".html", ".htm", ".pdf"} and not self._is_probably_text_file(full):
            raise ValueError("Only text files can be opened in an external editor.")
        cmd, mode = self._editor_command(full, line=line)
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if mode == "vscode":
            self._shrink_vscode_window()
        elif mode == "browser":
            app_name = "Google Chrome"
            process_name = "Google Chrome"
            if any(part == "Chromium" for part in cmd):
                app_name = "Chromium"
                process_name = "Chromium"
            self._shrink_browser_window(app_name, process_name)
        return {"ok": True, "path": rel}

    def list_files(self):
        files = []
        for root, dirs, filenames in os.walk(self.workspace):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in self.SKIP_DIRS)
            depth = root[len(self.workspace):].count(os.sep)
            if depth >= 3:
                dirs.clear()
            for filename in sorted(filenames):
                if filename.startswith("."):
                    continue
                rel = os.path.join(root, filename)[len(self.workspace):].lstrip(os.sep)
                files.append(rel)
        return files

    @staticmethod
    def _highlight_text(escaped_text: str, ext: str, *, theme_comment: str, theme_keyword: str, theme_string: str,
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

    def file_view(self, rel: str, *, embed: bool = False, base_path: str = "") -> str:
        full = self._resolve_path(rel)
        if not os.path.exists(full):
            raise FileNotFoundError(full)

        ext = os.path.splitext(rel)[1].lower()
        filename = os.path.basename(rel)
        prefix = (base_path or "").rstrip("/")
        raw_url = f"{prefix}/file-raw?path={url_quote(rel)}"
        pane_bg = "rgb(20, 20, 19)"
        embed_bg = "transparent" if embed else pane_bg
        pane_fg = "rgb(252, 252, 252)"
        pane_muted = "rgb(252, 252, 252)"
        pane_line = "rgba(255,255,255,0.08)"
        base_css = (
            f":root{{color-scheme: dark;}}*{{box-sizing:border-box}}"
            f"html,body{{margin:0;background:{embed_bg};color:{pane_fg};font-family:sans-serif;display:flex;flex-direction:column;height:100vh}}"
            f".hdr{{padding:10px 16px;background:{embed_bg};border-bottom:0.5px solid {pane_line};display:flex;align-items:center;gap:8px;flex-shrink:0}}"
            f".fn{{font-weight:700;font-size:14px;color:{pane_fg}}}.fp{{color:{pane_muted};font-size:12px}}"
        )
        header = "" if embed else (
            f'<div class="hdr"><span>{{icon}}</span><span class="fn">{html_escape(filename)}</span>'
            f'<span class="fp">{html_escape(rel)}</span></div>'
        )

        if ext in self.IMAGE_EXTS:
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}.wrap{{flex:1;overflow:auto;display:flex;align-items:center;justify-content:center;padding:16px;background:{embed_bg}}}'
                f'img{{max-width:100%;max-height:100%;object-fit:contain}}</style></head>'
                f'<body>{header.format(icon="🖼️")}<div class="wrap"><img src="{raw_url}" alt="{html_escape(filename)}"></div></body></html>'
            )
        if ext in self.PDF_EXTS:
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}.wrap{{flex:1;min-height:0;background:{embed_bg}}}iframe{{width:100%;height:100%;border:0;background:{embed_bg}}}</style></head>'
                f'<body>{header.format(icon="📕")}<div class="wrap"><iframe src="{raw_url}" title="{html_escape(filename)}"></iframe></div></body></html>'
            )
        if ext in self.VIDEO_EXTS:
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}.wrap{{flex:1;display:flex;align-items:center;justify-content:center;background:{embed_bg}}}'
                f'video{{max-width:100%;max-height:100%}}</style></head>'
                f'<body>{header.format(icon="🎬")}<div class="wrap"><video controls src="{raw_url}"></video></div></body></html>'
            )
        if ext in self.AUDIO_EXTS:
            audio_js = (
                'const audio=document.getElementById("audioPreview");'
                'const cv=document.getElementById("blobCanvas");'
                'const ctx=cv?cv.getContext("2d"):null;'
                'let frame=0,analyser=null,aCtx=null,freqData=null,bands=[0,0,0,0];'
                # DPR-aware sizing
                'const fit=()=>{'
                '  if(!cv)return;const dpr=Math.max(1,devicePixelRatio||1);'
                '  const s=Math.min(cv.clientWidth,cv.clientHeight)||200;'
                '  cv.width=Math.round(s*dpr);cv.height=Math.round(s*dpr);'
                '  if(ctx)ctx.setTransform(dpr,0,0,dpr,0,0);'
                '};'
                # AnalyserNode
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
                # Get 4 frequency bands
                'const getBands=()=>{'
                '  if(!analyser||!freqData){bands=[0,0,0,0];return;}'
                '  analyser.getByteFrequencyData(freqData);'
                '  const n=freqData.length;const q=Math.floor(n/4);'
                '  for(let b=0;b<4;b++){'
                '    let sum=0;for(let i=b*q;i<(b+1)*q&&i<n;i++)sum+=freqData[i];'
                '    bands[b]=bands[b]*0.6+(sum/(q*255))*0.4;'
                '  }'
                '};'
                # Draw blob
                'const draw=()=>{'
                '  if(!ctx||!cv)return;fit();'
                '  const s=Math.min(cv.clientWidth,cv.clientHeight)||200;'
                '  const cx=s/2,cy=s/2;'
                '  const playing=!audio.paused&&!audio.ended;'
                '  const progress=audio.duration?audio.currentTime/audio.duration:0;'
                '  const t=performance.now()*0.001;'
                '  if(playing)getBands();'
                '  ctx.clearRect(0,0,s,s);'
                # Base radius
                '  const baseR=s*0.28;'
                '  const energyBoost=playing?(bands[0]*0.3+bands[1]*0.2)*baseR:0;'
                '  const breathe=Math.sin(t*0.8)*baseR*0.015;'
                '  const R=baseR+energyBoost+breathe;'
                # Control points
                '  const N=24;'
                '  const pts=[];'
                '  for(let i=0;i<N;i++){'
                '    const angle=(i/N)*Math.PI*2;'
                # Idle deformation: very subtle, nearly circular
                '    let deform=0;'
                '    deform+=Math.sin(angle*2+t*1.2)*0.02;'
                '    deform+=Math.sin(angle*3-t*0.9)*0.012;'
                '    deform+=Math.sin(angle*5+t*2.1)*0.006;'
                # Audio-reactive: strong deformation only when playing
                '    if(playing){'
                '      deform+=Math.sin(angle*2+t*3)*bands[0]*0.25;'
                '      deform+=Math.sin(angle*4-t*2.5)*bands[1]*0.18;'
                '      deform+=Math.sin(angle*6+t*4)*bands[2]*0.12;'
                '      deform+=Math.sin(angle*10-t*5)*bands[3]*0.08;'
                '    }'
                '    const r=R*(1+deform);'
                '    pts.push([cx+Math.cos(angle)*r, cy+Math.sin(angle)*r]);'
                '  }'
                # Smooth closed curve
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
                # Gradient fill
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
                # Stroke
                '  ctx.strokeStyle="rgba(252,252,252,"+(playing?0.25+bands[1]*0.3:0.1).toFixed(3)+")";'
                '  ctx.lineWidth=1;'
                '  ctx.stroke();'
                # Inner glow
                '  if(playing&&(bands[0]>0.1||bands[1]>0.1)){'
                '    ctx.save();ctx.globalAlpha=Math.min(0.15,bands[0]*0.2);'
                '    ctx.filter="blur("+Math.round(8+bands[0]*12)+"px)";'
                '    ctx.fillStyle="rgba(252,252,252,1)";ctx.fill();'
                '    ctx.restore();'
                '  }'
                '};'
                # Animation loop
                'const tick=()=>{draw();frame=requestAnimationFrame(tick);};'
                # Events
                'audio.addEventListener("play",async()=>{'
                '  await ensureAudio();if(aCtx&&aCtx.state==="suspended")await aCtx.resume();'
                '});'
                # Start immediately
                'fit();tick();'
            )
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}.wrap{{flex:1;display:flex;align-items:center;justify-content:center;padding:32px;background:{embed_bg}}}'
                f'.audio-shell{{width:100%;max-width:500px;display:flex;flex-direction:column;align-items:center;gap:14px}}'
                f'#blobCanvas{{width:200px;height:200px;display:block}}'
                f'audio{{width:100%;max-width:500px;min-width:0}}'
                f'</style></head>'
                f'<body>{header.format(icon="🎵")}<div class="wrap"><div class="audio-shell">'
                f'<canvas id="blobCanvas" width="200" height="200"></canvas>'
                f'<audio id="audioPreview" controls src="{raw_url}"></audio></div></div>'
                f'<script>{audio_js}</script></body></html>'
            )
        if ext in self.MODEL_3D_EXTS:
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
        if ext in self.TEXT_EXTS:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            escaped = self._highlight_text(
                html_escape(content),
                ext,
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
            height = "100vh" if embed else "calc(100vh - 43px)"
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                f'<style>{base_css}body{{background:{embed_bg};color:{pane_fg}}}.hdr{{background:{embed_bg};border-bottom-color:{pane_line}}}'
                f'.fn{{color:{pane_fg}}}.fp{{color:{pane_muted}}}pre{{margin:0;padding:16px;white-space:pre;overflow:auto;height:{height};'
                f'font-family:"SF Mono","Fira Code",monospace;font-size:13px;line-height:1.5;background:{embed_bg};color:{pane_fg}}}</style></head>'
                f'<body>{header.format(icon="📄")}<pre>{escaped}</pre></body></html>'
            )
        if ext == ".md":
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            escaped_js = content.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
            md_height = "100vh" if embed else "calc(100vh - 43px)"
            rel_js = rel.replace("\\", "/").replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
            prefix_js = prefix.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
            return (
                f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
                '<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>'
                f'<style>'
                f'{base_css}'
                '@font-face{font-family:"anthropicSerif";src:url("/font/anthropic-serif-roman.ttf") format("truetype");font-style:normal;font-weight:300 800;font-display:swap}'
                '@font-face{font-family:"anthropicSerif";src:url("/font/anthropic-serif-italic.ttf") format("truetype");font-style:italic;font-weight:300 800;font-display:swap}'
                '@font-face{font-family:"jetbrainsMono";src:url("/font/jetbrains-mono.ttf") format("truetype");font-style:normal;font-weight:100 800;font-display:swap}'
                f'.md{{padding:24px 32px;max-width:860px;overflow:auto;height:{md_height};'
                'font-family:"anthropicSerif","anthropicSerif Fallback","Anthropic Serif","Hiragino Mincho ProN","Yu Mincho","YuMincho","Noto Serif JP",Georgia,"Times New Roman",Times,serif;'
                'font-size:13px;line-height:22px;font-style:normal;font-weight:360;'
                'font-synthesis-weight:none;font-synthesis-style:none;'
                '-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;'
                'font-optical-sizing:auto;font-variation-settings:"wght" 360;'
                f'background:{embed_bg};color:{pane_fg}}}'
                '.md>*:first-child{margin-top:0}.md>*:last-child{margin-bottom:0}'
                '.md,.md p,.md li,.md li p,.md blockquote,.md blockquote p{font-size:13px;line-height:22px}'
                '.md p{margin:0 0 .6em}'
                '.md h1,.md h2,.md h3,.md h4{margin:.8em 0 .3em;font-weight:600;font-variation-settings:"wght" 530;font-synthesis:weight;line-height:1.2}'
                '.md h1{font-size:22px}.md h2{font-size:18px}.md h3{font-size:1.05em}.md h4{font-size:1em}'
                '.md ul,.md ol{margin:.4em 0 .6em;padding-left:1.5em}.md li{margin:.15em 0;line-height:24px}.md li p{margin:0}'
                f'.md h1,.md h2{{border-bottom:1px solid {pane_line};padding-bottom:.3em}}'
                '.md :not(pre)>code{font-family:"jetbrainsMono","JetBrains Mono","SF Mono",monospace;font-size:13px;line-height:21px;'
                'font-style:normal;font-weight:210;font-synthesis-weight:none;font-stretch:normal;font-variation-settings:"wght" 210;'
                'background:rgba(255,255,255,.09);border-radius:4px;padding:1px 5px}'
                '.md pre{margin:0;padding:16px;background:rgba(0,0,0,0.18);border:1px solid rgba(255,255,255,0.06);border-radius:8px;overflow-x:auto}'
                '.md pre code{font-family:"jetbrainsMono","JetBrains Mono","SF Mono",monospace;font-size:13px;line-height:20px;'
                'font-style:normal;font-weight:210;font-synthesis-weight:none;font-variation-settings:"wght" 210;background:none;padding:0}'
                '.md blockquote{border-left:3px solid rgba(255,255,255,0.2);margin:.5em 0;padding:.3em .8em;opacity:.85}'
                '.md hr{border:none;border-top:1px solid rgba(255,255,255,0.12);margin:.8em 0}'
                '.md img{display:block;max-width:100%;max-height:60vh;width:auto;height:auto;margin:12px 0;border-radius:10px}'
                '.md table{border-collapse:collapse;width:100%;font-size:13px;line-height:21px}'
                f'.md th,.md td{{border-top:1.5px solid {pane_line};border-bottom:1.5px solid {pane_line};border-left:none;border-right:none;padding:7.5px 4px;font-size:13px;line-height:21px;text-align:left}}'
                '.md th{background:transparent;font-weight:530;border-top:none;border-bottom-color:rgba(255,255,255,0.28)}'
                '.md td{font-weight:360;font-variation-settings:"wght" 360}'
                '.md a{color:#58a6ff;text-decoration:none}.md a:hover{text-decoration:underline}'
                '.md strong{font-weight:530;font-variation-settings:"wght" 530}.md em{font-style:italic}'
                '</style></head>'
                f'<body>{header.format(icon="📝")}<div class="md" id="out"></div>'
                f'''<script>
const __mdRel = `{rel_js}`;
const __fileBase = `{prefix_js}`;
const __rawBase = `${{__fileBase}}/file-raw?path=`;
const __isExternalSrc = (src) => /^(https?:|data:|blob:|file:|\/\/)/i.test(src || "");
const __normalizeMdPath = (baseRel, src) => {{
  const cleanSrc = String(src || "").trim();
  if (!cleanSrc || __isExternalSrc(cleanSrc) || cleanSrc.startsWith("#")) return cleanSrc;
  const withoutQuery = cleanSrc.split(/[?#]/, 1)[0];
  const baseParts = String(baseRel || "").split("/").slice(0, -1);
  const rawParts = withoutQuery.startsWith("/")
    ? withoutQuery.replace(/^\/+/, "").split("/")
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
  return out.join("/");
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
const out = document.getElementById("out");
out.innerHTML = marked.parse(`{escaped_js}`, {{breaks:true,gfm:true}});
__rewriteMarkdownImages(out);
</script></body></html>'''
            )

        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        escaped = html_escape(content)
        pre_height = "100vh" if embed else "calc(100vh - 43px)"
        return (
            f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
            f'<style>{base_css}body{{background:{embed_bg};color:{pane_fg};font-family:"SF Mono","Fira Code",monospace;font-size:13px}}'
            f'.hdr{{padding:10px 16px;background:{embed_bg};border-bottom:1px solid {pane_line};display:flex;align-items:center;gap:8px}}'
            f'.fn{{font-weight:700;font-size:14px;color:{pane_fg}}}.fp{{color:{pane_muted};font-size:12px}}'
            f'pre{{margin:0;padding:16px;white-space:pre;overflow:auto;height:{pre_height};background:{embed_bg}}}</style></head>'
            f'<body>{header.format(icon="📄")}<pre>{escaped}</pre></body></html>'
        )
