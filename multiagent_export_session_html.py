#!/usr/bin/env python3
import argparse
import json
import os
import re
import urllib.parse
from pathlib import Path

KNOWN_AGENTS = ["claude", "codex", "gemini", "copilot"]
ICON_FILES = {
    "claude": "claude-color.svg",
    "codex": "codex-color.svg",
    "gemini": "gemini-color.svg",
    "copilot": "github.svg",
}


def parse_args():
    p = argparse.ArgumentParser(description="Export a multiagent session log to a standalone chat-style HTML file")
    p.add_argument("session", help="Session name to export")
    p.add_argument("-o", "--output", help="Output HTML path")
    p.add_argument("--repo-root", default=os.getcwd(), help="Repository root to search from")
    p.add_argument("--limit", type=int, default=0, help="Keep only the newest N messages (0 = all)")
    return p.parse_args()


def candidate_index_files(repo_root: Path, session: str):
    candidates = []
    env_workspace = os.environ.get("MULTIAGENT_WORKSPACE")
    for root in [env_workspace, str(repo_root), str(repo_root / "logs")]:
        if not root:
            continue
        p = Path(root)
        if p.name != "logs":
            p = p / "logs"
        candidates.append(p)
    seen = set()
    found = []
    for root in candidates:
        root = root.resolve()
        if root in seen or not root.exists():
            continue
        seen.add(root)
        exact = root / session / ".agent-index.jsonl"
        if exact.exists():
            found.append(exact)
        found.extend(root.glob(f"{session}_*/.agent-index.jsonl"))
    for path in sorted({path.resolve() for path in found}, key=lambda p: (p.stat().st_mtime, str(p))):
        yield path


def load_entries(index_path: Path):
    entries = []
    bad_lines = 0
    with index_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                bad_lines += 1
    return entries, bad_lines


def infer_targets(entries):
    targets = []
    seen = set()
    for entry in entries:
        for name in [entry.get("sender", ""), *(entry.get("targets") or [])]:
            n = (name or "").strip().lower()
            if n in KNOWN_AGENTS and n not in seen:
                seen.add(n)
                targets.append(n)
    return targets or KNOWN_AGENTS[:]


def read_trace_map(session_dir: Path):
    traces = {}
    for agent in KNOWN_AGENTS:
        path = session_dir / f"{agent}.log"
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            traces[agent] = "\n".join(text.splitlines()[-20:])
        else:
            traces[agent] = "Offline"
    return traces


def load_icon_map(repo_root: Path):
    data = {}
    for name, rel in ICON_FILES.items():
        path = repo_root / rel
        if not path.exists():
            data[name] = ""
            continue
        svg = path.read_text(encoding="utf-8")
        data[name] = "data:image/svg+xml;utf8," + urllib.parse.quote(svg)
    return data


def extract_html_template(agent_index_path: Path):
    text = agent_index_path.read_text(encoding="utf-8")
    marker = '\nHTML = """<!doctype html>'
    start = text.index(marker) + len('\nHTML = """')
    end = text.index('</html>\n"""', start) + len('</html>')
    return text[start:end]


def js_literal(value):
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def compat_script():
    return r"""
<script>
(function(){
  const esc = (s) => String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
  const inline = (s) => {
    let out = esc(s);
    out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    out = out.replace(/~~([^~]+)~~/g, '<del>$1</del>');
    out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return out;
  };
  const parseBlocks = (src) => {
    const lines = String(src).replace(/\r\n?/g, '\n').split('\n');
    const html = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) { i++; continue; }
      if (line.startsWith('```')) {
        const buf = [];
        i++;
        while (i < lines.length && !lines[i].startsWith('```')) { buf.push(lines[i]); i++; }
        if (i < lines.length) i++;
        html.push('<pre><code>' + esc(buf.join('\n')) + '</code></pre>');
        continue;
      }
      const h = line.match(/^(#{1,6})\s+(.*)$/);
      if (h) {
        html.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`);
        i++;
        continue;
      }
      if (line.startsWith('> ')) {
        const buf = [];
        while (i < lines.length && lines[i].startsWith('> ')) { buf.push(lines[i].slice(2)); i++; }
        html.push('<blockquote>' + buf.map(inline).join('<br>') + '</blockquote>');
        continue;
      }
      if (/^\s*[-*]\s+/.test(line)) {
        const items = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
          items.push(lines[i].replace(/^\s*[-*]\s+/, ''));
          i++;
        }
        html.push('<ul>' + items.map(x => '<li>' + inline(x) + '</li>').join('') + '</ul>');
        continue;
      }
      if (/^\s*\d+\.\s+/.test(line)) {
        const items = [];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          items.push(lines[i].replace(/^\s*\d+\.\s+/, ''));
          i++;
        }
        html.push('<ol>' + items.map(x => '<li>' + inline(x) + '</li>').join('') + '</ol>');
        continue;
      }
      const buf = [line];
      i++;
      while (
        i < lines.length &&
        lines[i].trim() &&
        !lines[i].startsWith('```') &&
        !lines[i].startsWith('> ') &&
        !/^(#{1,6})\s+/.test(lines[i]) &&
        !/^\s*[-*]\s+/.test(lines[i]) &&
        !/^\s*\d+\.\s+/.test(lines[i])
      ) {
        buf.push(lines[i]);
        i++;
      }
      html.push('<p>' + inline(buf.join('<br>')) + '</p>');
    }
    return html.join('\n');
  };
  window.marked = { parse: (src) => parseBlocks(src) };
  window.renderMathInElement = window.renderMathInElement || function(){};
  window.AnsiUp = class {
    ansi_to_html(text) { return esc(String(text)).replace(/\n/g, '<br>'); }
  };
})();
</script>
"""


def patch_html(html_text: str, payload: dict, traces: dict, icons: dict):
    old_icon = 'return { cls: "avatar-icon", html: `<img src="/icon/${s}" alt="${escapeHtml(s)}" width="28" height="28">` };'
    new_icon = 'return { cls: "avatar-icon", html: `<img src="${window.__ICON_MAP__[s] || ""}" alt="${escapeHtml(s)}" width="28" height="28">` };'
    if old_icon in html_text:
        html_text = html_text.replace(old_icon, new_icon)

    html_text = re.sub(r'\s*<script src="https://cdn\.jsdelivr\.net/[^"]+"></script>\n?', '', html_text)
    html_text = re.sub(r'\s*<link rel="stylesheet" href="https://cdn\.jsdelivr\.net/[^"]+">\n?', '', html_text)
    html_text = html_text.replace("</title>", "</title>\n" + compat_script(), 1)

    bootstrap = f'''
  <script>
    window.__STATIC_EXPORT__ = true;
    window.__EXPORT_PAYLOAD__ = {js_literal(payload)};
    window.__TRACE_MAP__ = {js_literal(traces)};
    window.__ICON_MAP__ = {js_literal(icons)};
    (() => {{
      const jsonResponse = (obj, status = 200) => new Response(JSON.stringify(obj), {{
        status,
        headers: {{ "Content-Type": "application/json; charset=utf-8" }}
      }});
      const originalFetch = window.fetch ? window.fetch.bind(window) : null;
      window.fetch = async (input, init = {{}}) => {{
        const url = typeof input === "string" ? input : (input && input.url) || "";
        const method = ((init && init.method) || (typeof input !== "string" && input && input.method) || "GET").toUpperCase();
        const parsed = new URL(url || window.location.href, window.location.href);
        if (parsed.pathname === "/messages") return jsonResponse(window.__EXPORT_PAYLOAD__);
        if (parsed.pathname === "/agents") {{
          const statuses = {{}};
          for (const target of window.__EXPORT_PAYLOAD__.targets || []) statuses[target] = "idle";
          return jsonResponse(statuses);
        }}
        if (parsed.pathname === "/trace") {{
          const agent = (parsed.searchParams.get("agent") || "").toLowerCase();
          return jsonResponse({{ content: window.__TRACE_MAP__[agent] || "Offline" }});
        }}
        if (parsed.pathname === "/auto-mode") {{
          if (method === "GET") return jsonResponse({{ active: false, last_approval: 0, last_approval_agent: "" }});
          return jsonResponse({{ ok: false, error: "static export is read-only" }}, 400);
        }}
        if (parsed.pathname === "/memory-path") return jsonResponse({{ path: "", content: "" }});
        if (parsed.pathname === "/files") return jsonResponse([]);
        if (parsed.pathname === "/send" || parsed.pathname === "/log-system") {{
          return jsonResponse({{ ok: false, error: "static export is read-only" }}, 400);
        }}
        if (originalFetch) return originalFetch(input, init);
        return jsonResponse({{ ok: false, error: "unsupported" }}, 404);
      }};
      document.addEventListener("DOMContentLoaded", () => {{
      }});
    }})();
  </script>
'''
    html_text = html_text.replace('  <script>\n    const renderMarkdown = (text) => {', bootstrap + '  <script>\n    const renderMarkdown = (text) => {', 1)
    html_text = html_text.replace(
        '    const refresh = async (options = {}) => {\n'
        '      try {\n'
        '        const res = await fetch(`/messages?ts=${Date.now()}`, { cache: "no-store" });\n'
        '        if (!res.ok) return;\n'
        '        render(await res.json(), options);\n'
        '      } catch (_) {}\n'
        '    };',
        '    const refresh = async (options = {}) => {\n'
        '      if (window.__STATIC_EXPORT__) {\n'
        '        render(window.__EXPORT_PAYLOAD__, options);\n'
        '        return;\n'
        '      }\n'
        '      try {\n'
        '        const res = await fetch(`/messages?ts=${Date.now()}`, { cache: "no-store" });\n'
        '        if (!res.ok) return;\n'
        '        render(await res.json(), options);\n'
        '      } catch (_) {}\n'
        '    };'
    )
    html_text = html_text.replace('    if (followMode) {\n      setInterval(refresh, 1000);\n    }', '    if (followMode && !window.__STATIC_EXPORT__) {\n      setInterval(refresh, 1000);\n    }')
    return html_text


def main():
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    index_files = list(candidate_index_files(repo_root, args.session))
    if not index_files:
        raise SystemExit(f"No .agent-index.jsonl found for session: {args.session}")
    index_path = index_files[-1]
    entries, bad_lines = load_entries(index_path)
    if args.limit and args.limit > 0:
        entries = entries[-args.limit:]
    payload = {
        "session": args.session,
        "filter": "all",
        "follow": False,
        "active": True,
        "source": str(index_path),
        "targets": infer_targets(entries),
        "entries": entries,
    }
    html_template = extract_html_template(repo_root / "bin" / "agent-index")
    final_html = patch_html(
        html_template,
        payload,
        read_trace_map(index_path.parent),
        load_icon_map(repo_root),
    )
    output = Path(args.output) if args.output else repo_root / f"{args.session}-chat-snapshot.html"
    output.write_text(final_html, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
