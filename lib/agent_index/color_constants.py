"""Centralized color constants and token expansion helpers."""

from __future__ import annotations

from collections.abc import Mapping

THEME_BG_LEVEL_MIN = 0
THEME_BG_LEVEL_MAX = 40
THEME_BG_LEVEL_DEFAULT = 0

THEME_FG_LEVEL_MIN = 220
THEME_FG_LEVEL_MAX = 255
THEME_FG_LEVEL_DEFAULT = 252


def _clamp_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    return max(minimum, min(maximum, parsed))


def resolve_theme_levels(settings: Mapping[str, object] | None = None) -> tuple[int, int]:
    src = settings if isinstance(settings, Mapping) else {}
    bg_level = _clamp_int(
        src.get("theme_bg_level", THEME_BG_LEVEL_DEFAULT),
        default=THEME_BG_LEVEL_DEFAULT,
        minimum=THEME_BG_LEVEL_MIN,
        maximum=THEME_BG_LEVEL_MAX,
    )
    fg_level = _clamp_int(
        src.get("theme_fg_level", THEME_FG_LEVEL_DEFAULT),
        default=THEME_FG_LEVEL_DEFAULT,
        minimum=THEME_FG_LEVEL_MIN,
        maximum=THEME_FG_LEVEL_MAX,
    )
    return bg_level, fg_level


def resolve_theme_palette(settings: Mapping[str, object] | None = None) -> dict[str, object]:
    bg_level, fg_level = resolve_theme_levels(settings)
    fg_soft_level = max(0, fg_level - 7)
    fg_bright_level = min(255, fg_level + 3)
    bg_rgb = (bg_level, bg_level, bg_level)
    fg_rgb = (fg_level, fg_level, fg_level)
    fg_soft_rgb = (fg_soft_level, fg_soft_level, fg_soft_level)
    fg_bright_rgb = (fg_bright_level, fg_bright_level, fg_bright_level)
    return {
        "bg_level": bg_level,
        "fg_level": fg_level,
        "fg_soft_level": fg_soft_level,
        "fg_bright_level": fg_bright_level,
        "dark_bg_rgb": bg_rgb,
        "dark_bg_channels": ", ".join(str(v) for v in bg_rgb),
        "dark_bg": f"rgb({','.join(str(v) for v in bg_rgb)})",
        "light_fg_rgb": fg_rgb,
        "light_fg_channels": ", ".join(str(v) for v in fg_rgb),
        "light_fg": f"rgb({','.join(str(v) for v in fg_rgb)})",
        "light_fg_soft_rgb": fg_soft_rgb,
        "light_fg_soft_channels": ", ".join(str(v) for v in fg_soft_rgb),
        "light_fg_soft": f"rgb({','.join(str(v) for v in fg_soft_rgb)})",
        "light_fg_bright_rgb": fg_bright_rgb,
        "light_fg_bright_channels": ", ".join(str(v) for v in fg_bright_rgb),
        "light_fg_bright": f"rgb({','.join(str(v) for v in fg_bright_rgb)})",
    }


_DEFAULT_THEME = resolve_theme_palette()
DARK_BG_RGB = _DEFAULT_THEME["dark_bg_rgb"]
DARK_BG_CHANNELS = _DEFAULT_THEME["dark_bg_channels"]
DARK_BG = _DEFAULT_THEME["dark_bg"]
LIGHT_FG_RGB = _DEFAULT_THEME["light_fg_rgb"]
LIGHT_FG_CHANNELS = _DEFAULT_THEME["light_fg_channels"]
LIGHT_FG = _DEFAULT_THEME["light_fg"]
LIGHT_FG_SOFT_RGB = _DEFAULT_THEME["light_fg_soft_rgb"]
LIGHT_FG_SOFT_CHANNELS = _DEFAULT_THEME["light_fg_soft_channels"]
LIGHT_FG_SOFT = _DEFAULT_THEME["light_fg_soft"]
LIGHT_FG_BRIGHT_RGB = _DEFAULT_THEME["light_fg_bright_rgb"]
LIGHT_FG_BRIGHT_CHANNELS = _DEFAULT_THEME["light_fg_bright_channels"]
LIGHT_FG_BRIGHT = _DEFAULT_THEME["light_fg_bright"]


def apply_color_tokens(text: str, settings: Mapping[str, object] | None = None) -> str:
    palette = resolve_theme_palette(settings)
    dark_bg = str(palette["dark_bg"])
    dark_bg_channels = str(palette["dark_bg_channels"])
    light_fg = str(palette["light_fg"])
    light_fg_channels = str(palette["light_fg_channels"])
    light_fg_soft = str(palette["light_fg_soft"])
    light_fg_soft_channels = str(palette["light_fg_soft_channels"])
    light_fg_bright = str(palette["light_fg_bright"])
    light_fg_bright_channels = str(palette["light_fg_bright_channels"])

    replacements: tuple[tuple[str, str], ...] = (
        ("__DARK_BG__", dark_bg),
        ("__DARK_BG_CHANNELS__", dark_bg_channels),
        ("__LIGHT_FG__", light_fg),
        ("__LIGHT_FG_CHANNELS__", light_fg_channels),
        ("__LIGHT_FG_SOFT__", light_fg_soft),
        ("__LIGHT_FG_SOFT_CHANNELS__", light_fg_soft_channels),
        ("__LIGHT_FG_BRIGHT__", light_fg_bright),
        ("__LIGHT_FG_BRIGHT_CHANNELS__", light_fg_bright_channels),
        # Legacy dark literals
        ("rgb(10,10,10)", dark_bg),
        ("rgb(10, 10, 10)", dark_bg),
        ("rgb(0,0,0)", dark_bg),
        ("rgb(0, 0, 0)", dark_bg),
        # Legacy near-white literals
        ("rgb(252,252,252)", light_fg),
        ("rgb(252, 252, 252)", light_fg),
        ("rgb(245,245,245)", light_fg_soft),
        ("rgb(245, 245, 245)", light_fg_soft),
        ("rgb(255,255,255)", light_fg_bright),
        ("rgb(255, 255, 255)", light_fg_bright),
        # Legacy near-white rgba channels
        ("rgba(252,252,252,", f"rgba({light_fg_channels},"),
        ("rgba(252, 252, 252,", f"rgba({light_fg_channels},"),
        ("rgba(245,245,245,", f"rgba({light_fg_soft_channels},"),
        ("rgba(245, 245, 245,", f"rgba({light_fg_soft_channels},"),
        ("rgba(255,255,255,", f"rgba({light_fg_bright_channels},"),
        ("rgba(255, 255, 255,", f"rgba({light_fg_bright_channels},"),
    )
    resolved = text
    for old, new in replacements:
        resolved = resolved.replace(old, new)
    return resolved
