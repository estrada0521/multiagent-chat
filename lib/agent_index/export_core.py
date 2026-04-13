from __future__ import annotations
import logging

import base64
import html as html_lib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from .agent_name_core import agent_base_name
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
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return ""
        return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")

    def resolve_font_file(self, name: str) -> Path | None:
        for candidate in self.font_files.get(name, []):
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def resolve_icon_map_key(raw_name: str, icon_files: dict[str, Path]) -> str | None:
        """Map URL segment (e.g. claude-2) to a registry key with an icon file."""
        n = unquote((raw_name or "").strip()).lower()
        if not n:
            return None
        if n in icon_files:
            return n
        base = agent_base_name(n)
        if base in icon_files:
            return base
        return None

    def icon_bytes(self, name: str) -> bytes | None:
        key = self.resolve_icon_map_key(name, self.icon_files)
        if not key:
            return None
        path = self.icon_files.get(key)
        if not path or not path.exists():
            return None
        try:
            return path.read_bytes()
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return None

    def font_bytes(self, name: str) -> bytes | None:
        path = self.resolve_font_file(name)
        if not path:
            return None
        try:
            return path.read_bytes()
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            return None

    def _fetch_cdn(self, url: str) -> str | None:
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
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            self._cdn_cache[url] = None
            return None

    @staticmethod
    def _escape(value: object) -> str:
        return html_lib.escape(str(value or ""), quote=True)

    @staticmethod
    def _agent_base_name(raw_name: str) -> str:
        return agent_base_name(raw_name)

    def _icon_data_uri_for_name(self, raw_name: str) -> str:
        key = self.resolve_icon_map_key(raw_name, self.icon_files)
        return self.icon_data_uris.get(key or "", "")

    @staticmethod
    def _strip_sender_prefix(value: str) -> str:
        return re.sub(r"^\[From:\s*[^\]]+\]\s*", "", str(value or ""), flags=re.IGNORECASE)

    @staticmethod
    def _display_attachment_filename(path: str) -> str:
        raw = str(path or "")
        filename = raw.split("/")[-1] or raw
        if "/uploads/" not in raw:
            return filename
        match = re.match(r"^\d{8}_\d{6}_(.+)$", filename)
        return match.group(1) if match else filename

    @staticmethod
    def _agent_instance_digits(raw_name: str) -> str:
        match = re.search(r"-(\d+)$", str(raw_name or "").strip())
        return match.group(1) if match else ""

    def _agent_icon_instance_sub_html(self, raw_name: str) -> str:
        digits = self._agent_instance_digits(raw_name)
        if not digits:
            return ""
        return f'<sub class="agent-icon-instance-sub">{self._escape(digits)}</sub>'

    def _role_class(self, sender: str) -> str:
        base = self._agent_base_name(sender)
        if base == "user" or base in self.icon_files:
            return base
        return "system"

    def _meta_agent_label(
        self,
        raw_name: str,
        text_class: str,
        icon_side: str = "right",
        *,
        icon_only: bool = False,
    ) -> str:
        raw = str(raw_name or "").strip() or "unknown"
        base = self._agent_base_name(raw)
        icon_uri = self._icon_data_uri_for_name(raw)
        has_icon = bool(icon_uri)
        icon_html = ""
        if has_icon:
            icon_html = (
                '<span class="agent-icon-slot agent-icon-slot--meta">'
                f'<span class="meta-agent-icon" aria-hidden="true" style="--agent-icon-mask:url(\'{self._escape(icon_uri)}\')"></span>'
                f"{self._agent_icon_instance_sub_html(raw)}"
                "</span>"
            )
        elif icon_only:
            icon_html = '<span class="agent-icon-slot agent-icon-slot--meta meta-agent-fallback" aria-hidden="true">—</span>'
        side_class = " icon-right" if icon_side == "right" else ""
        title_attr = self._escape(raw)
        aria_attr = f' aria-label="{title_attr}"' if icon_only else ""
        if icon_only:
            return f'<span class="meta-agent meta-agent--icon-only{side_class}" title="{title_attr}"{aria_attr}>{icon_html}</span>'
        return (
            f'<span class="meta-agent{side_class}">{icon_html}'
            f'<span class="{self._escape(text_class)}">{self._escape(raw)}</span>'
            "</span>"
        )

    @staticmethod
    def _copy_icon_svg() -> str:
        return (
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="9" y="9" width="13" height="13" rx="2"/>'
            '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
            "</svg>"
        )

    @staticmethod
    def _reply_icon_svg() -> str:
        return (
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="9 17 4 12 9 7"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/>'
            "</svg>"
        )

    @staticmethod
    def _reply_up_icon_svg() -> str:
        return (
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M12 19V5"/><polyline points="7 10 12 5 17 10"/>'
            "</svg>"
        )

    @staticmethod
    def _reply_down_icon_svg() -> str:
        return (
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M12 5v14"/><polyline points="7 14 12 19 17 14"/>'
            "</svg>"
        )

    @staticmethod
    def _wrap_file_icon(path: str) -> str:
        return (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
        )

    def _file_icon_svg(self, ext: str) -> str:
        icons = {
            "image": self._wrap_file_icon('<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>'),
            "video": self._wrap_file_icon('<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>'),
            "audio": self._wrap_file_icon('<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>'),
            "file": self._wrap_file_icon('<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/>'),
            "code": self._wrap_file_icon('<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>'),
            "archive": self._wrap_file_icon('<path d="M21 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v3"/><path d="m3 8 9 6 9-6"/><path d="M3 18v-8"/><path d="M21 18v-8"/><path d="M3 18a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2"/>'),
            "web": self._wrap_file_icon('<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'),
        }
        mapping = {
            "png": "image", "jpg": "image", "jpeg": "image", "gif": "image", "webp": "image", "svg": "image", "ico": "image",
            "pdf": "file",
            "mp4": "video", "mov": "video", "webm": "video", "avi": "video", "mkv": "video",
            "mp3": "audio", "wav": "audio", "ogg": "audio", "m4a": "audio", "flac": "audio",
            "zip": "archive", "tar": "archive", "gz": "archive", "bz2": "archive", "rar": "archive",
            "md": "file", "txt": "file",
            "py": "code", "js": "code", "ts": "code", "sh": "code", "json": "code", "yaml": "code", "yml": "code",
            "html": "web", "css": "web",
        }
        return icons.get(mapping.get(str(ext or "").lower(), "file"), icons["file"])

    def _build_file_card_markup(self, raw_path: str) -> str:
        path = str(raw_path or "").strip()
        filename = self._display_attachment_filename(path)
        ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
        icon = self._file_icon_svg(ext)
        return (
            f'<button type="button" class="file-card" data-filepath="{self._escape(path)}" data-ext="{self._escape(ext)}">'
            f'<span class="file-card-icon">{icon}</span>'
            f'<span class="file-card-name">{self._escape(filename)}</span>'
            '<span class="file-card-open">↗</span>'
            "</button>"
        )

    def _render_static_attachment_pill(self, raw_path: str) -> str:
        return self._build_file_card_markup(raw_path)

    def _render_static_inline_markdown(self, text: str, attachment_html: list[str]) -> str:
        escaped = self._escape(text)
        for idx, pill in enumerate(attachment_html):
            escaped = escaped.replace(f"ATTACHMENT_PLACEHOLDER_{idx}", pill)
        escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
        escaped = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", escaped)
        escaped = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
            escaped,
        )
        return escaped

    def _render_static_markdown(self, raw_text: str) -> str:
        source = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
        attachments: list[str] = []

        def _stash_attachment(match: re.Match[str]) -> str:
            attachments.append(self._render_static_attachment_pill(match.group(1).strip()))
            return f"ATTACHMENT_PLACEHOLDER_{len(attachments) - 1}"

        source = re.sub(r"\[Attached:\s*([^\]]+)\]", _stash_attachment, source)
        lines = source.split("\n")
        html_parts: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            if line.startswith("```"):
                lang = self._escape(line[3:].strip())
                buf: list[str] = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    buf.append(lines[i])
                    i += 1
                if i < len(lines):
                    i += 1
                class_attr = f' class="language-{lang}"' if lang else ""
                html_parts.append(
                    f'<pre class="static-export-pre"><code{class_attr}>'
                    f"{self._escape(chr(10).join(buf))}</code></pre>"
                )
                continue
            heading = re.match(r"^(#{1,6})\s+(.*)$", line)
            if heading:
                level = len(heading.group(1))
                html_parts.append(
                    f"<h{level}>"
                    f"{self._render_static_inline_markdown(heading.group(2), attachments)}"
                    f"</h{level}>"
                )
                i += 1
                continue
            if line.startswith("> "):
                buf = []
                while i < len(lines) and lines[i].startswith("> "):
                    buf.append(self._render_static_inline_markdown(lines[i][2:], attachments))
                    i += 1
                html_parts.append(f"<blockquote>{'<br>'.join(buf)}</blockquote>")
                continue
            if re.match(r"^\s*[-*]\s+", line):
                items = []
                while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                    item = re.sub(r"^\s*[-*]\s+", "", lines[i])
                    items.append(f"<li>{self._render_static_inline_markdown(item, attachments)}</li>")
                    i += 1
                html_parts.append(f"<ul>{''.join(items)}</ul>")
                continue
            if re.match(r"^\s*\d+\.\s+", line):
                items = []
                while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                    item = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                    items.append(f"<li>{self._render_static_inline_markdown(item, attachments)}</li>")
                    i += 1
                html_parts.append(f"<ol>{''.join(items)}</ol>")
                continue
            buf = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i]
                if not next_line.strip():
                    break
                if next_line.startswith("```") or next_line.startswith("> "):
                    break
                if re.match(r"^(#{1,6})\s+", next_line):
                    break
                if re.match(r"^\s*[-*]\s+", next_line):
                    break
                if re.match(r"^\s*\d+\.\s+", next_line):
                    break
                buf.append(next_line)
                i += 1
            html_parts.append(
                "<p>"
                + self._render_static_inline_markdown("<br>".join(buf), attachments)
                + "</p>"
            )
        return "".join(html_parts) or f"<pre>{self._escape(source)}</pre>"

    @staticmethod
    def _format_day_label(timestamp: str) -> str:
        raw = str(timestamp or "").strip()
        if not raw:
            return "Conversation"
        try:
            dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return "Conversation"
        return dt.strftime("%b %d").replace(" 0", " ")

    @staticmethod
    def _build_reply_children_map(entries: list[dict]) -> dict[str, str]:
        children: dict[str, str] = {}
        for entry in entries:
            parent = str(entry.get("reply_to") or "").strip()
            msg_id = str(entry.get("msg_id") or "").strip()
            if parent and msg_id and parent not in children:
                children[parent] = msg_id
        return children

    def _entry_has_structured_block(self, body_html: str) -> bool:
        return any(token in body_html for token in ("<ul", "<ol", "<blockquote", "<pre", "<table", "table-scroll", "katex-display"))

    def _build_static_message_html(self, entry: dict, reply_children_map: dict[str, str]) -> str:
        sender_raw = str(entry.get("sender") or "").strip()
        if sender_raw.lower() == "system":
            system_message = self._escape(entry.get("message") or "")
            system_title = system_message
            msg_id = self._escape(entry.get("msg_id") or "")
            kind = self._escape(entry.get("kind") or "")
            return (
                f'<div class="sysmsg-row" data-msgid="{msg_id}" data-sender="system" data-kind="{kind}">'
                f'<span class="sysmsg-text" title="{system_title}">{system_message}</span>'
                "</div>"
            )

        cls = self._role_class(sender_raw)
        body = self._strip_sender_prefix(entry.get("message") or "")
        raw_attr = self._escape(body)
        preview_attr = self._escape(body[:80])
        msg_id = self._escape(entry.get("msg_id") or "")
        reply_to = self._escape(entry.get("reply_to") or "")
        target_list = entry.get("targets") or []
        target_spans = (
            "".join(
                (
                    ("" if idx == 0 else '<span class="meta-agent-sep">,</span>')
                    + self._meta_agent_label(target, "target-name", "right", icon_only=(self._agent_base_name(target) != "user"))
                )
                for idx, target in enumerate(target_list)
            )
            if target_list
            else self._meta_agent_label("no target", "target-name", "right", icon_only=True)
        )
        target_meta = f'<span class="targets">{target_spans}</span>'
        reply_source_jump_html = (
            f'<button class="reply-jump-inline reply-target-jump-btn" type="button" title="返信元へ移動" data-replyto="{reply_to}">{self._reply_up_icon_svg()}</button>'
            if reply_to
            else ""
        )
        first_reply_id = reply_children_map.get(str(entry.get("msg_id") or "").strip(), "")
        reply_target_jump_html = (
            f'<button class="reply-target-jump-btn" type="button" title="返信先へ移動" data-replytarget="{self._escape(first_reply_id)}">{self._reply_down_icon_svg()}</button>'
            if first_reply_id
            else ""
        )
        sender_html = self._meta_agent_label(sender_raw or "unknown", "sender-label", "right", icon_only=True)
        copy_button_html = (
            f'<button class="copy-btn" type="button" title="コピー">{self._copy_icon_svg()}</button>'
        )
        reply_button_html = (
            f'<button class="reply-btn" type="button" title="返信" data-msgid="{msg_id}" '
            f'data-sender="{self._escape(sender_raw)}" data-preview="{preview_attr}">{self._reply_icon_svg()}</button>'
            if msg_id
            else ""
        )
        deferred_body_html = (
            f'<div class="message-deferred-actions"><button class="message-deferred-btn" type="button" data-load-full-message="{msg_id}">Load full message</button></div>'
            if entry.get("deferred_body") and msg_id
            else ""
        )
        body_html = self._render_static_markdown(body)
        structured_class = " has-structured-block" if cls == "user" and self._entry_has_structured_block(body_html) else ""
        if cls == "user":
            meta_html = (
                f'<div class="message-meta-below user-message-meta"><span class="arrow">to</span>{target_meta}'
                f"{reply_target_jump_html}{copy_button_html}</div>"
            )
            divider_html = '<div class="user-message-divider" aria-hidden="true"></div>'
        else:
            meta_html = (
                f'<div class="message-meta-below">{sender_html}<span class="arrow">to</span>{target_meta}'
                f"{reply_source_jump_html}{reply_button_html}{copy_button_html}{reply_target_jump_html}</div>"
            )
            divider_html = ""
        return (
            f'<article class="message-row {cls}" data-msgid="{msg_id}" data-sender="{self._escape(sender_raw)}">'
            f'<div class="message {cls}" data-raw="{raw_attr}" data-preview="{preview_attr}">'
            f"{meta_html}"
            f'<div class="message-body-row{structured_class}"><div class="md-body">{body_html}</div></div>'
            f"{deferred_body_html}{divider_html}"
            "</div></article>"
        )

    def _render_static_export_messages_html(self, payload: dict) -> str:
        entries = payload.get("entries") or []
        if not entries:
            return (
                '<div class="conversation-empty">'
                '<div class="daybreak">Conversation</div>'
                '<section class="conversation-empty-card" aria-label="Empty conversation">'
                '<h2 class="conversation-empty-title">New session</h2>'
                '<p class="conversation-empty-copy">This session has no messages yet. Send the first message when you are ready.</p>'
                "</section></div>"
            )
        reply_children_map = self._build_reply_children_map(entries)
        daybreak_label = self._format_day_label(str(entries[0].get("timestamp") or ""))
        rows: list[str] = [f'<div class="daybreak">{self._escape(daybreak_label)}</div>']
        for entry in entries:
            rows.append(self._build_static_message_html(entry, reply_children_map))
        return "".join(rows)

    @staticmethod
    def _static_export_fallback_style() -> str:
        return """
  <style id="static-export-fallback-style">
    body[data-static-export="1"] #messages .copy-btn,
    body[data-static-export="1"] #messages .reply-btn,
    body[data-static-export="1"] #messages .reply-target-jump-btn,
    body[data-static-export="1"] #messages .reply-jump-inline,
    body[data-static-export="1"] #messages .file-card,
    body[data-static-export="1"] #messages .message-deferred-btn {
      pointer-events: none;
      cursor: default;
      -webkit-tap-highlight-color: transparent;
    }
  </style>
"""

    @staticmethod
    def _static_export_compat_script() -> str:
        return r"""
  <script>
    (() => {
      const esc = (s) => String(s)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
      const inline = (s) => {
        let out = esc(s);
        out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
        out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        out = out.replace(/\*([^*]+)\*/g, "<em>$1</em>");
        out = out.replace(/~~([^~]+)~~/g, "<del>$1</del>");
        out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        return out;
      };
      const parseBlocks = (src) => {
        const lines = String(src).replace(/\r\n?/g, "\n").split("\n");
        const html = [];
        let i = 0;
        while (i < lines.length) {
          const line = lines[i];
          if (!line.trim()) { i++; continue; }
          if (line.startsWith("```")) {
            const buf = [];
            i++;
            while (i < lines.length && !lines[i].startsWith("```")) { buf.push(lines[i]); i++; }
            if (i < lines.length) i++;
            html.push("<pre><code>" + esc(buf.join("\n")) + "</code></pre>");
            continue;
          }
          const h = line.match(/^(#{1,6})\s+(.*)$/);
          if (h) {
            html.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`);
            i++;
            continue;
          }
          if (line.startsWith("> ")) {
            const buf = [];
            while (i < lines.length && lines[i].startsWith("> ")) { buf.push(lines[i].slice(2)); i++; }
            html.push("<blockquote>" + buf.map(inline).join("<br>") + "</blockquote>");
            continue;
          }
          if (/^\s*[-*]\s+/.test(line)) {
            const items = [];
            while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
              items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
              i++;
            }
            html.push("<ul>" + items.map((item) => "<li>" + inline(item) + "</li>").join("") + "</ul>");
            continue;
          }
          if (/^\s*\d+\.\s+/.test(line)) {
            const items = [];
            while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
              items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
              i++;
            }
            html.push("<ol>" + items.map((item) => "<li>" + inline(item) + "</li>").join("") + "</ol>");
            continue;
          }
          const buf = [line];
          i++;
          while (
            i < lines.length &&
            lines[i].trim() &&
            !lines[i].startsWith("```") &&
            !lines[i].startsWith("> ") &&
            !/^(#{1,6})\s+/.test(lines[i]) &&
            !/^\s*[-*]\s+/.test(lines[i]) &&
            !/^\s*\d+\.\s+/.test(lines[i])
          ) {
            buf.push(lines[i]);
            i++;
          }
          html.push("<p>" + inline(buf.join("<br>")) + "</p>");
        }
        return html.join("\n");
      };
      if (typeof window.marked === "undefined") {
        window.marked = { parse: (src) => parseBlocks(src) };
      }
      if (typeof window.renderMathInElement !== "function") {
        window.renderMathInElement = () => {};
      }
      if (typeof window.AnsiUp === "undefined") {
        window.AnsiUp = class {
          ansi_to_html(text) { return esc(String(text)).replace(/\n/g, "<br>"); }
        };
      }
      if (typeof window.Prism === "undefined") {
        window.Prism = {
          languages: {},
          highlightElement() {},
        };
      }
    })();
  </script>
"""

    def build_export_html(self, limit: int = 100) -> str:
        payload = json.loads(self.payload_fn(limit_override=limit))
        payload["follow"] = False

        html = self.render_html_fn() if self.render_html_fn else self.html_template
        html = (
            html
            .replace("__ICON_DATA_URIS__", json.dumps(self.icon_data_uris, ensure_ascii=True))
            .replace("__CHAT_HEADER_HTML__", "")
            .replace("__CHAT_BASE_PATH__", "")
            .replace("__AGENT_FONT_MODE__", "serif")
            .replace("__AGENT_FONT_MODE_INLINE_STYLE__", "")
            .replace("__HUB_HEADER_CSS__", "")
            .replace("__HUB_PORT__", "0")
            .replace("__SERVER_INSTANCE__", self.server_instance)
        )

        for url in self.CDN_SCRIPTS:
            tag = f'<script src="{url}"></script>'
            if tag not in html:
                continue
            content = self.CDN_FALLBACKS.get(url, "")
            html = html.replace(tag, f"<script>{content}</script>" if content else "", 1)

        for url in self.CDN_CSS:
            tag = f'<link rel="stylesheet" href="{url}">'
            if tag in html:
                html = html.replace(tag, "", 1)

        for font_name in self.font_files:
            path = self.resolve_font_file(font_name)
            if not path:
                continue
            try:
                b64 = base64.b64encode(path.read_bytes()).decode("ascii")
                uri = f"data:font/truetype;base64,{b64}"
                html = html.replace(f'url("/font/{font_name}")', f'url("{uri}")', 1)
            except Exception as exc:
                logging.error(f"Unexpected error: {exc}", exc_info=True)
                pass

        html = re.sub(r'\s*<script src="https://cdn\.jsdelivr\.net/npm/[^"]+"></script>\n?', "", html)
        html = re.sub(r'\s*<link rel="stylesheet" href="https://cdn\.jsdelivr\.net/npm/[^"]+">\n?', "", html)
        html = re.sub(r'\s*<link rel="manifest"[^>]*>\n?', "", html)
        html = re.sub(r'\s*<link rel="icon"[^>]*>\n?', "", html)
        html = re.sub(r'\s*<link rel="apple-touch-icon"[^>]*>\n?', "", html)

        static_messages_html = self._render_static_export_messages_html(payload)
        html = html.replace('<body>', '<body data-static-export="1">', 1)
        html = html.replace('<main id="messages"></main>', f'<main id="messages">{static_messages_html}</main>', 1)
        html = html.replace('<div class="statusline" id="statusline"></div>', '<div class="statusline" id="statusline">Static export</div>', 1)
        html = html.replace(
            '<textarea id="message" placeholder="Write a message"></textarea>',
            '<textarea id="message" placeholder="Static export preview" readonly></textarea>',
            1,
        )

        payload_json = json.dumps(payload, ensure_ascii=True).replace("</", r"<\\/")
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
        html = html.replace("</title>", "</title>\n" + self._static_export_fallback_style() + self._static_export_compat_script(), 1)
        html = html.replace("<head>", "<head>\n" + bootstrap, 1)
        return html
