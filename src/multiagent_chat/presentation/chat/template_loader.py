from __future__ import annotations

from pathlib import Path
import re

_APPS_ROOT = Path(__file__).resolve().parents[4] / "apps"
_CHAT_TEMPLATE_DIRS = {
    "desktop": _APPS_ROOT / "desktop" / "web" / "chat",
    "mobile": _APPS_ROOT / "mobile" / "chat",
}

_STYLE_MARKER = "__CHAT_MAIN_STYLE_BLOCK__"
_SHELL_STYLE_MARKER = "__CHAT_SHELL_STYLE_BLOCK__"
_COMPOSER_MARKER = "__CHAT_COMPOSER_HTML__"
_SCRIPT_MARKER = "__CHAT_APP_SCRIPT_BLOCK__"
_INCLUDE_RE = re.compile(r"__CHAT_INCLUDE:([A-Za-z0-9_./-]+)__")


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Chat template fragment not found: {path}")
    return path.read_text()


def _style_block(css: str) -> str:
    return f"  <style>\n{css}  </style>\n"


def _script_block(js: str) -> str:
    return f"  <script>\n{js}  </script>\n"


def _expand_includes(text: str, base_dir: Path, stack: tuple[Path, ...] = ()) -> str:
    def _replace(match: re.Match[str]) -> str:
        rel = match.group(1)
        path = (base_dir / rel).resolve()
        apps_root = _APPS_ROOT.resolve()
        if apps_root not in path.parents and path != apps_root:
            raise ValueError(f"Chat template include escapes template directory: {rel}")
        if path in stack:
            chain = " -> ".join(str(item) for item in (*stack, path))
            raise ValueError(f"Chat template include cycle detected: {chain}")
        return _expand_includes(_read_text(path), path.parent, (*stack, path))

    return _INCLUDE_RE.sub(_replace, text)


def load_chat_template(variant: str) -> str:
    normalized = "mobile" if str(variant or "").strip().lower() == "mobile" else "desktop"
    template_dir = _CHAT_TEMPLATE_DIRS[normalized]
    shell = _read_text(template_dir / "shell.html")
    composer = _read_text(template_dir / "composer.html")
    css = _expand_includes(_read_text(template_dir / "main.css"), template_dir)
    shell_css = _read_text(template_dir / "shell.css")
    js = _expand_includes(_read_text(template_dir / "app.js"), template_dir)
    if _STYLE_MARKER not in shell:
        raise ValueError(f"Chat template shell missing {_STYLE_MARKER}: {template_dir / 'shell.html'}")
    if _SHELL_STYLE_MARKER not in shell:
        raise ValueError(f"Chat template shell missing {_SHELL_STYLE_MARKER}: {template_dir / 'shell.html'}")
    if _COMPOSER_MARKER not in shell:
        raise ValueError(f"Chat template shell missing {_COMPOSER_MARKER}: {template_dir / 'shell.html'}")
    if _SCRIPT_MARKER not in shell:
        raise ValueError(f"Chat template shell missing {_SCRIPT_MARKER}: {template_dir / 'shell.html'}")
    return (
        shell
        .replace(_COMPOSER_MARKER, composer, 1)
        .replace(_STYLE_MARKER, _style_block(css), 1)
        .replace(_SHELL_STYLE_MARKER, _style_block(shell_css), 1)
        .replace(_SCRIPT_MARKER, _script_block(js), 1)
    )
