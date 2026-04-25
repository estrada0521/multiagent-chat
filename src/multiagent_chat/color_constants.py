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


def _level_from_legacy_bg(bg_level: int, legacy_level: int) -> int:
    # Legacy dark palette was centered around rgb(10,10,10). Keep relative spacing.
    return max(0, min(255, int(bg_level) + (int(legacy_level) - 10)))


def _gray_rgb(level: int) -> tuple[int, int, int]:
    value = max(0, min(255, int(level)))
    return (value, value, value)


def _gray_channels(level: int) -> str:
    value = max(0, min(255, int(level)))
    return f"{value}, {value}, {value}"


def _gray_rgb_string(level: int) -> str:
    value = max(0, min(255, int(level)))
    return f"rgb({value},{value},{value})"


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
    panel_strong_level = _level_from_legacy_bg(bg_level, 15)
    surface_level = _level_from_legacy_bg(bg_level, 20)
    surface_alt_level = _level_from_legacy_bg(bg_level, 25)
    hover_level = _level_from_legacy_bg(bg_level, 30)
    inline_border_level = _level_from_legacy_bg(bg_level, 64)
    muted_level = max(0, min(255, fg_level - 94))
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
        "gray_panel_strong_level": panel_strong_level,
        "gray_panel_strong_rgb": _gray_rgb(panel_strong_level),
        "gray_panel_strong_channels": _gray_channels(panel_strong_level),
        "gray_panel_strong": _gray_rgb_string(panel_strong_level),
        "gray_surface_level": surface_level,
        "gray_surface_rgb": _gray_rgb(surface_level),
        "gray_surface_channels": _gray_channels(surface_level),
        "gray_surface": _gray_rgb_string(surface_level),
        "gray_surface_alt_level": surface_alt_level,
        "gray_surface_alt_rgb": _gray_rgb(surface_alt_level),
        "gray_surface_alt_channels": _gray_channels(surface_alt_level),
        "gray_surface_alt": _gray_rgb_string(surface_alt_level),
        "gray_hover_level": hover_level,
        "gray_hover_rgb": _gray_rgb(hover_level),
        "gray_hover_channels": _gray_channels(hover_level),
        "gray_hover": _gray_rgb_string(hover_level),
        "gray_inline_border_level": inline_border_level,
        "gray_inline_border_rgb": _gray_rgb(inline_border_level),
        "gray_inline_border_channels": _gray_channels(inline_border_level),
        "gray_inline_border": _gray_rgb_string(inline_border_level),
        "gray_muted_level": muted_level,
        "gray_muted_rgb": _gray_rgb(muted_level),
        "gray_muted_channels": _gray_channels(muted_level),
        "gray_muted": _gray_rgb_string(muted_level),
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
GRAY_PANEL_STRONG = _DEFAULT_THEME["gray_panel_strong"]
GRAY_SURFACE = _DEFAULT_THEME["gray_surface"]
GRAY_SURFACE_ALT = _DEFAULT_THEME["gray_surface_alt"]
GRAY_HOVER = _DEFAULT_THEME["gray_hover"]
GRAY_INLINE_BORDER = _DEFAULT_THEME["gray_inline_border"]
GRAY_MUTED = _DEFAULT_THEME["gray_muted"]


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
    gray_panel_strong = str(palette["gray_panel_strong"])
    gray_panel_strong_channels = str(palette["gray_panel_strong_channels"])
    gray_surface = str(palette["gray_surface"])
    gray_surface_channels = str(palette["gray_surface_channels"])
    gray_surface_alt = str(palette["gray_surface_alt"])
    gray_surface_alt_channels = str(palette["gray_surface_alt_channels"])
    gray_hover = str(palette["gray_hover"])
    gray_hover_channels = str(palette["gray_hover_channels"])
    gray_inline_border = str(palette["gray_inline_border"])
    gray_inline_border_channels = str(palette["gray_inline_border_channels"])
    gray_muted = str(palette["gray_muted"])
    gray_muted_channels = str(palette["gray_muted_channels"])

    replacements: tuple[tuple[str, str], ...] = (
        ("__DARK_BG__", dark_bg),
        ("__DARK_BG_CHANNELS__", dark_bg_channels),
        ("__LIGHT_FG__", light_fg),
        ("__LIGHT_FG_CHANNELS__", light_fg_channels),
        ("__LIGHT_FG_SOFT__", light_fg_soft),
        ("__LIGHT_FG_SOFT_CHANNELS__", light_fg_soft_channels),
        ("__LIGHT_FG_BRIGHT__", light_fg_bright),
        ("__LIGHT_FG_BRIGHT_CHANNELS__", light_fg_bright_channels),
        ("__GRAY_PANEL_STRONG__", gray_panel_strong),
        ("__GRAY_PANEL_STRONG_CHANNELS__", gray_panel_strong_channels),
        ("__GRAY_SURFACE__", gray_surface),
        ("__GRAY_SURFACE_CHANNELS__", gray_surface_channels),
        ("__GRAY_SURFACE_ALT__", gray_surface_alt),
        ("__GRAY_SURFACE_ALT_CHANNELS__", gray_surface_alt_channels),
        ("__GRAY_HOVER__", gray_hover),
        ("__GRAY_HOVER_CHANNELS__", gray_hover_channels),
        ("__GRAY_INLINE_BORDER__", gray_inline_border),
        ("__GRAY_INLINE_BORDER_CHANNELS__", gray_inline_border_channels),
        ("__GRAY_MUTED__", gray_muted),
        ("__GRAY_MUTED_CHANNELS__", gray_muted_channels),
    )
    resolved = text
    for old, new in replacements:
        resolved = resolved.replace(old, new)
    return resolved
