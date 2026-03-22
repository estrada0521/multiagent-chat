from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from .agent_registry import icon_file_map


class ExportRuntime:
    CDN_FALLBACKS = {
        "https://cdn.jsdelivr.net/npm/marked@12/marked.min.js": r"""
window.marked=window.marked||(function(){
  const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const inl=s=>{let o=esc(s);
    o=o.replace(/`([^`]+)`/g,'<code>$1</code>');
    o=o.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
    o=o.replace(/\*([^*]+)\*/g,'<em>$1</em>');
    o=o.replace(/~~([^~]+)~~/g,'<del>$1</del>');
    o=o.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return o;};
  const parse=src=>{
    const lines=String(src).replace(/\r\n?/g,'\n').split('\n');
    const html=[];let i=0;
    while(i<lines.length){
      const l=lines[i];
      if(!l.trim()){i++;continue;}
      if(l.startsWith('```')){
        const buf=[];i++;
        while(i<lines.length&&!lines[i].startsWith('```'))buf.push(lines[i++]);
        if(i<lines.length)i++;
        html.push('<pre><code>'+esc(buf.join('\n'))+'</code></pre>');continue;}
      const h=l.match(/^(#{1,6})\s+(.*)/);
      if(h){html.push('<h'+h[1].length+'>'+inl(h[2])+'</h'+h[1].length+'>');i++;continue;}
      if(l.startsWith('> ')){
        const buf=[];
        while(i<lines.length&&lines[i].startsWith('> '))buf.push(lines[i++].slice(2));
        html.push('<blockquote>'+buf.map(inl).join('<br>')+'</blockquote>');continue;}
      if(/^\s*[-*]\s+/.test(l)){
        const it=[];
        while(i<lines.length&&/^\s*[-*]\s+/.test(lines[i]))it.push(lines[i++].replace(/^\s*[-*]\s+/,''));
        html.push('<ul>'+it.map(x=>'<li>'+inl(x)+'</li>').join('')+'</ul>');continue;}
      if(/^\s*\d+\.\s+/.test(l)){
        const it=[];
        while(i<lines.length&&/^\s*\d+\.\s+/.test(lines[i]))it.push(lines[i++].replace(/^\s*\d+\.\s+/,''));
        html.push('<ol>'+it.map(x=>'<li>'+inl(x)+'</li>').join('')+'</ol>');continue;}
      const buf=[l];i++;
      while(i<lines.length&&lines[i].trim()&&!lines[i].startsWith('```')&&!lines[i].startsWith('> ')&&!/^#{1,6}\s/.test(lines[i])&&!/^\s*[-*]\s/.test(lines[i])&&!/^\s*\d+\.\s/.test(lines[i]))buf.push(lines[i++]);
      html.push('<p>'+inl(buf.join('<br>'))+'</p>');}
    return html.join('\n');};
  return{parse};
})();
""",
        "https://cdn.jsdelivr.net/npm/ansi_up@5.1.0/ansi_up.min.js": r"""
window.AnsiUp=window.AnsiUp||class{ansi_to_html(t){
  const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  return esc(String(t)).replace(/\n/g,'<br>');
}};
""",
    }
    CDN_SCRIPTS = [
        "https://cdn.jsdelivr.net/npm/marked@12/marked.min.js",
        "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js",
        "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js",
        "https://cdn.jsdelivr.net/npm/ansi_up@5.1.0/ansi_up.min.js",
    ]
    CDN_CSS = [
        "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css",
    ]

    def __init__(self, *, repo_root: Path | str, html_template: str, payload_fn, server_instance: str, render_html_fn=None):
        self.repo_root = Path(repo_root).resolve()
        self.html_template = html_template
        self.payload_fn = payload_fn
        self.server_instance = server_instance
        self.render_html_fn = render_html_fn
        self._cdn_cache = {}
        self.icon_files = icon_file_map(self.repo_root)
        self.font_files = {
            "anthropic-serif-roman.ttf": [
                Path.home() / "Library/Fonts/AnthropicSerif-Romans-Variable-25x258.ttf",
                Path("/Applications/Claude.app/Contents/Resources/fonts/AnthropicSerif-Romans-Variable-25x258.ttf"),
            ],
            "anthropic-serif-italic.ttf": [
                Path.home() / "Library/Fonts/AnthropicSerif-Italics-Variable-25x258.ttf",
                Path("/Applications/Claude.app/Contents/Resources/fonts/AnthropicSerif-Italics-Variable-25x258.ttf"),
            ],
            "anthropic-sans-roman.ttf": [
                Path("/Applications/Claude.app/Contents/Resources/fonts/AnthropicSans-Romans-Variable-25x258.ttf"),
            ],
            "anthropic-sans-italic.ttf": [
                Path("/Applications/Claude.app/Contents/Resources/fonts/AnthropicSans-Italics-Variable-25x258.ttf"),
            ],
            "jetbrains-mono.ttf": [
                Path.home() / "Library/Fonts/JetBrainsMono-Variable.ttf",
                Path("/System/Library/Fonts/Supplemental/JetBrainsMono-Variable.ttf"),
            ],
        }
        self.icon_data_uris = {name: self._icon_data_uri(name) for name in self.icon_files}

    def _icon_data_uri(self, name: str) -> str:
        icon_path = self.icon_files.get(name)
        if not icon_path or not icon_path.exists():
            return ""
        try:
            raw = icon_path.read_bytes()
        except Exception:
            return ""
        return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")

    def resolve_font_file(self, name: str):
        for candidate in self.font_files.get(name, []):
            if candidate.exists():
                return candidate
        return None

    def icon_bytes(self, name: str):
        path = self.icon_files.get(name)
        if not path or not path.exists():
            return None
        try:
            return path.read_bytes()
        except Exception:
            return None

    def font_bytes(self, name: str):
        path = self.resolve_font_file(name)
        if not path:
            return None
        try:
            return path.read_bytes()
        except Exception:
            return None

    def _fetch_cdn(self, url: str):
        if url in self._cdn_cache:
            return self._cdn_cache[url]
        try:
            import ssl
            import urllib.request

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                content = response.read().decode("utf-8", errors="replace")
            self._cdn_cache[url] = content
            return content
        except Exception:
            self._cdn_cache[url] = None
            return None

    def build_export_html(self, limit: int = 100) -> str:
        payload = json.loads(self.payload_fn(limit_override=limit))
        payload["follow"] = False

        html = self.render_html_fn() if self.render_html_fn else self.html_template
        html = (
            html
            .replace("__ICON_DATA_URIS__", json.dumps(self.icon_data_uris, ensure_ascii=True))
            .replace("__CHAT_HEADER_HTML__", "")
            .replace("__CHAT_BASE_PATH__", "")
            .replace("__CHAT_THEME__", "black-hole")
            .replace("__STARFIELD_ATTR__", ' data-starfield="off"')
            .replace("__AGENT_FONT_MODE__", "serif")
            .replace("__AGENT_FONT_MODE_INLINE_STYLE__", "")
            .replace("__HUB_HEADER_CSS__", "")
            .replace("__HUB_LOGO_DATA_URI__", "")
            .replace("__HUB_PORT__", "0")
            .replace("__SERVER_INSTANCE__", self.server_instance)
        )

        for url in self.CDN_SCRIPTS:
            tag = f'<script src="{url}"></script>'
            if tag not in html:
                continue
            content = self._fetch_cdn(url) or self.CDN_FALLBACKS.get(url, "")
            html = html.replace(tag, f"<script>{content}</script>" if content else "", 1)

        for url in self.CDN_CSS:
            tag = f'<link rel="stylesheet" href="{url}">'
            if tag not in html:
                continue
            content = self._fetch_cdn(url)
            if content:
                content = re.sub(r"@font-face\s*\{[^}]*\}", "", content)
                html = html.replace(tag, f"<style>{content}</style>", 1)
            else:
                html = html.replace(tag, "", 1)

        for font_name in self.font_files:
            path = self.resolve_font_file(font_name)
            if not path:
                continue
            try:
                b64 = base64.b64encode(path.read_bytes()).decode("ascii")
                uri = f"data:font/truetype;base64,{b64}"
                html = html.replace(f'url("/font/{font_name}")', f'url("{uri}")', 1)
            except Exception:
                pass

        html = html.replace('  <link rel="manifest" href="/app.webmanifest">\n', "", 1)

        payload_json = re.sub(r"</(?=script)", r"<\\/", json.dumps(payload, ensure_ascii=True), flags=re.IGNORECASE)
        payload_json = payload_json.replace("</", r"<\\/")
        bootstrap = f"""  <script>
    window.__EXPORT_PAYLOAD__ = {payload_json};
    (function(){{
      const _jr = (obj, st) => new Response(JSON.stringify(obj), {{status: st||200, headers:{{"Content-Type":"application/json; charset=utf-8"}}}});
      const _orig = window.fetch ? window.fetch.bind(window) : null;
      window.fetch = async function(input, init){{
        const url = typeof input==="string"?input:(input&&input.url)||"";
        const path = new URL(url||window.location.href,window.location.href).pathname;
        const method = ((init&&init.method)||"GET").toUpperCase();
        if(path==="/messages") return _jr(window.__EXPORT_PAYLOAD__);
        if(path==="/agents"){{const s={{}};for(const t of(window.__EXPORT_PAYLOAD__.targets||[]))s[t]="idle";return _jr(s);}}
        if(path==="/auto-mode"){{if(method==="GET")return _jr({{active:false,last_approval:0,last_approval_agent:""}});return _jr({{ok:false}},400);}}
        if(path==="/trace")return _jr({{content:""}});
        if(path==="/files")return _jr([]);
        if(path==="/auto-approved")return _jr({{changed:false}});
        if(path==="/caffeinate")return _jr({{active:false}});
        if(_orig)return _orig(input,init);
        return _jr({{ok:false}},404);
      }};
    }})();
  </script>
"""
        html = html.replace('<title>agent-index chat</title>', '<title>agent-index chat</title>\n  <script>window.__STATIC_EXPORT__ = true;</script>', 1)
        html = html.replace("<head>", "<head>\n" + bootstrap, 1)
        return html
