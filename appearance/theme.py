from __future__ import annotations


THEME_CHOICES = frozenset({"system", "light", "dark"})
DESKTOP_THEME_DEFAULT = "system"
MOBILE_THEME_SETTING = "system"
SERVER_THEME_FALLBACK = "dark"


def resolve_server_theme(value: object) -> str:
    """Resolve a request choice where the server cannot inspect the OS theme."""
    theme = str(value or "").strip().lower()
    if not theme or theme == "system":
        return SERVER_THEME_FALLBACK
    if theme not in THEME_CHOICES:
        raise ValueError(f"invalid theme: {value!r}")
    return theme
