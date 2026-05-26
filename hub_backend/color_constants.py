from __future__ import annotations

from collections.abc import Mapping


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
    theme = str((settings or {}).get("theme", "dark") or "dark").strip().lower()
    if theme == "light":
        return 255, 0
    return 0, 255


def resolve_theme_palette(settings: Mapping[str, object] | None = None) -> dict[str, object]:
    theme = str((settings or {}).get("theme", "dark") or "dark").strip().lower()
    theme = "light" if theme == "light" else "dark"
    bg_level, fg_level = resolve_theme_levels(settings)
    if theme == "light":
        color_scheme = "light"
        fg_soft_level = 18
        fg_bright_level = 0
        panel_strong_level = 250
        surface_level = 250
        surface_alt_level = 245
        hover_level = 235
        inline_border_level = 202
        muted_level = 120
        icon_fg_level = 0
        icon_muted_level = 120
        icon_hover_level = 35
        chip_color_level = 180
        line = "rgba(0, 0, 0, 0.10)"
        line_strong = "rgba(0, 0, 0, 0.18)"
        table_line = "rgba(0, 0, 0, 0.18)"
        table_header_line = "rgba(0, 0, 0, 0.28)"
        code_copy_hover_bg = "rgba(0, 0, 0, 0.08)"
        fab_hover_bg = "rgba(235, 235, 235, 0.92)"
        session_hover_bg = "rgba(0, 0, 0, 0.04)"
        session_selected_bg = "rgba(0, 0, 0, 0.07)"
        panel_row_bg = "rgba(0, 0, 0, 0.06)"
        panel_row_border = "rgba(0, 0, 0, 0.08)"
        panel_row_hover_bg = "rgba(0, 0, 0, 0.08)"
        panel_row_active_bg = "rgba(0, 0, 0, 0.10)"
    else:
        color_scheme = "dark"
        fg_soft_level = max(0, fg_level - 7)
        fg_bright_level = min(255, fg_level + 3)
        panel_strong_level = 5
        surface_level = 10
        surface_alt_level = 15
        hover_level = 20
        inline_border_level = 54
        muted_level = max(0, min(255, fg_level - 97))
        icon_fg_level = 255
        icon_muted_level = 158
        icon_hover_level = 220
        chip_color_level = 70
        line = "rgba(255, 255, 255, 0.07)"
        line_strong = "rgba(255, 255, 255, 0.12)"
        table_line = "rgba(255, 255, 255, 0.12)"
        table_header_line = "rgba(255, 255, 255, 0.28)"
        code_copy_hover_bg = "rgba(255, 255, 255, 0.09)"
        fab_hover_bg = "rgba(40, 40, 40, 0.88)"
        session_hover_bg = "rgba(255, 255, 255, 0.05)"
        session_selected_bg = "rgba(255, 255, 255, 0.08)"
        panel_row_bg = "rgba(255, 255, 255, 0.10)"
        panel_row_border = "rgba(255, 255, 255, 0.14)"
        panel_row_hover_bg = "rgba(255, 255, 255, 0.13)"
        panel_row_active_bg = "rgba(255, 255, 255, 0.16)"
    bg_rgb = (bg_level, bg_level, bg_level)
    fg_rgb = (fg_level, fg_level, fg_level)
    fg_soft_rgb = (fg_soft_level, fg_soft_level, fg_soft_level)
    fg_bright_rgb = (fg_bright_level, fg_bright_level, fg_bright_level)
    icon_fg_rgb = _gray_rgb(icon_fg_level)
    icon_muted_rgb = _gray_rgb(icon_muted_level)
    icon_hover_rgb = _gray_rgb(icon_hover_level)
    return {
        "theme": theme,
        "color_scheme": color_scheme,
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
        "icon_fg_rgb": icon_fg_rgb,
        "icon_fg_channels": _gray_channels(icon_fg_level),
        "icon_fg": _gray_rgb_string(icon_fg_level),
        "icon_muted_rgb": icon_muted_rgb,
        "icon_muted_channels": _gray_channels(icon_muted_level),
        "icon_muted": _gray_rgb_string(icon_muted_level),
        "icon_hover_rgb": icon_hover_rgb,
        "icon_hover_channels": _gray_channels(icon_hover_level),
        "icon_hover": _gray_rgb_string(icon_hover_level),
        "chip_color": _gray_rgb_string(chip_color_level),
        "line": line,
        "line_strong": line_strong,
        "table_line": table_line,
        "table_header_line": table_header_line,
        "code_copy_hover_bg": code_copy_hover_bg,
        "fab_hover_bg": fab_hover_bg,
        "session_hover_bg": session_hover_bg,
        "session_selected_bg": session_selected_bg,
        "panel_row_bg": panel_row_bg,
        "panel_row_border": panel_row_border,
        "panel_row_hover_bg": panel_row_hover_bg,
        "panel_row_active_bg": panel_row_active_bg,
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
    icon_fg = str(palette["icon_fg"])
    icon_muted = str(palette["icon_muted"])
    icon_hover = str(palette["icon_hover"])
    chip_color = str(palette["chip_color"])

    replacements: tuple[tuple[str, str], ...] = (
        ("__THEME__", str(palette["theme"])),
        ("__COLOR_SCHEME__", str(palette["color_scheme"])),
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
        ("__ICON_FG__", icon_fg),
        ("__ICON_MUTED__", icon_muted),
        ("__ICON_HOVER__", icon_hover),
        ("__CHIP_COLOR__", chip_color),
        ("__LINE__", str(palette["line"])),
        ("__LINE_STRONG__", str(palette["line_strong"])),
        ("__TABLE_LINE__", str(palette["table_line"])),
        ("__TABLE_HEADER_LINE__", str(palette["table_header_line"])),
        ("__CODE_COPY_HOVER_BG__", str(palette["code_copy_hover_bg"])),
        ("__FAB_HOVER_BG__", str(palette["fab_hover_bg"])),
        ("__SESSION_HOVER_BG__", str(palette["session_hover_bg"])),
        ("__SESSION_SELECTED_BG__", str(palette["session_selected_bg"])),
        ("__PANEL_ROW_BG__", str(palette["panel_row_bg"])),
        ("__PANEL_ROW_BORDER__", str(palette["panel_row_border"])),
        ("__PANEL_ROW_HOVER_BG__", str(palette["panel_row_hover_bg"])),
        ("__PANEL_ROW_ACTIVE_BG__", str(palette["panel_row_active_bg"])),
        ("__DESK_SIDEBAR_OPACITY__", "0.90"),
    )
    resolved = text
    for old, new in replacements:
        resolved = resolved.replace(old, new)
    return resolved
