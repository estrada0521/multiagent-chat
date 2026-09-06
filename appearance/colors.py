from __future__ import annotations

# Text-color roles: one value per (client, theme). A role that equals another
# is set to it, not re-typed. Order: Base -> Hub -> Chat -> Fine details.
# The :root `--fg` fallback (light_fg) and icon grays live in
# resolve_theme_palette() instead.

# --- Base ---
TEXT_PRIMARY_DESKTOP_LIGHT_CHANNELS = "11, 11, 11"
TEXT_PRIMARY_DESKTOP_DARK_CHANNELS = "200, 200, 200"
TEXT_PRIMARY_MOBILE_LIGHT_CHANNELS = "19, 19, 19"
TEXT_PRIMARY_MOBILE_DARK_CHANNELS = "232, 232, 232"

# Muted / secondary (timestamps, previews, labels).
TEXT_MUTED_LIGHT_CHANNELS = "120, 120, 120"
TEXT_MUTED_DARK_CHANNELS = "150, 150, 150"

# --- Hub ---
# Session / window title.
TEXT_SESSION_DESKTOP_LIGHT_CHANNELS = TEXT_PRIMARY_DESKTOP_LIGHT_CHANNELS
TEXT_SESSION_DESKTOP_DARK_CHANNELS = TEXT_PRIMARY_DESKTOP_DARK_CHANNELS
TEXT_SESSION_MOBILE_LIGHT_CHANNELS = TEXT_PRIMARY_MOBILE_LIGHT_CHANNELS
TEXT_SESSION_MOBILE_DARK_CHANNELS = TEXT_PRIMARY_MOBILE_DARK_CHANNELS

# Archived / warning session name (dimmer than active).
TEXT_SESSION_DIM_DESKTOP_LIGHT_CHANNELS = TEXT_SESSION_DESKTOP_LIGHT_CHANNELS
TEXT_SESSION_DIM_DESKTOP_DARK_CHANNELS = "180, 180, 180"
TEXT_SESSION_DIM_MOBILE_LIGHT_CHANNELS = "100, 100, 100"
TEXT_SESSION_DIM_MOBILE_DARK_CHANNELS = "180, 180, 180"

# --- Chat (rendered markdown) ---
# Bold. Desktop falls back to text-primary via var(--fg-bold, var(--fg)).
TEXT_STRONG_MOBILE_LIGHT_CHANNELS = TEXT_PRIMARY_MOBILE_LIGHT_CHANNELS
TEXT_STRONG_MOBILE_DARK_CHANNELS = TEXT_PRIMARY_MOBILE_DARK_CHANNELS

# Inline / file link.
TEXT_LINK_LIGHT_CHANNELS = "36, 85, 161"
TEXT_LINK_DARK_CHANNELS = "96, 132, 203"

# External (web) link.
TEXT_EXTERNAL_LINK_LIGHT_CHANNELS = "196, 42, 30"
TEXT_EXTERNAL_LINK_DARK_CHANNELS = "224, 88, 88"

# Diff add / remove.
TEXT_DIFF_INSERT_LIGHT_CHANNELS = "26, 127, 55"
TEXT_DIFF_INSERT_DARK_CHANNELS = "74, 222, 128"
TEXT_DIFF_DELETE_LIGHT_CHANNELS = "207, 34, 46"
TEXT_DIFF_DELETE_DARK_CHANNELS = "248, 113, 113"

# --- Fine details ---
# Error text; matches external-link today but tuned independently.
TEXT_ERROR_LIGHT_CHANNELS = TEXT_EXTERNAL_LINK_LIGHT_CHANNELS
TEXT_ERROR_DARK_CHANNELS = TEXT_EXTERNAL_LINK_DARK_CHANNELS


# Icon-hover is icon scope, not text scope -- left as-is, untouched by the
# text-color-role cleanup above.
DESKTOP_LIGHT_ICON_HOVER = "rgb(35, 35, 35)"
DESKTOP_DARK_ICON_HOVER = "rgb(190, 190, 190)"
MOBILE_LIGHT_ICON_HOVER = "rgb(35, 35, 35)"
MOBILE_DARK_ICON_HOVER = "rgb(190, 190, 190)"


# Every TEXT_*_CHANNELS constant defined above is a role; nothing else has
# to re-list their names. Adding a role is declaring one constant, not also
# registering it somewhere.
#
# Only the bare channels are emitted -- CSS already has a way to build a
# full color from channels (`rgb(__X_CHANNELS__)`, or `rgb(var(--x-channels))`
# where a var needs to be shared), so there's nothing for Python to convert;
# emitting a second, pre-wrapped "__X__" token would just be the same fact
# spelled two ways.
def _text_color_token_replacements() -> tuple[tuple[str, str], ...]:
    return tuple(
        (f"__{name}__", value)
        for name, value in globals().items()
        if name.startswith("TEXT_") and name.endswith("_CHANNELS")
    )


def _gray_rgb(level: int) -> tuple[int, int, int]:
    value = max(0, min(255, int(level)))
    return (value, value, value)


def _gray_channels(level: int) -> str:
    value = max(0, min(255, int(level)))
    return f"{value}, {value}, {value}"


def _gray_rgb_string(level: int) -> str:
    value = max(0, min(255, int(level)))
    return f"rgb({value},{value},{value})"


MOBILE_HUB_LIGHT_BG_RGB = (243, 243, 241)
MOBILE_HUB_DARK_BG_RGB = (12, 12, 12)
MOBILE_CHAT_LIGHT_BG_RGB = (249, 249, 247)
MOBILE_CHAT_DARK_BG_RGB = (11, 11, 11)
# Desktop page background, one value per (surface, theme). Theme-independent
# constants so the runtime [data-theme] toggle blocks can reference them
# without picking up whatever theme the page first rendered under. Hub and
# chat are separate decisions, free to diverge.
DESKTOP_HUB_LIGHT_BG_RGB = (249, 249, 247)
DESKTOP_HUB_DARK_BG_RGB = (13, 13, 13)
DESKTOP_CHAT_LIGHT_BG_RGB = (249, 249, 247)
DESKTOP_CHAT_DARK_BG_RGB = (13, 13, 13)
# How translucent each surface reads over the window. Color + alpha are one
# decision about how the pane looks, kept adjacent so tuning is one edit.
# Hub alpha drives --hub-glass (the sidebar glass etc.); chat alpha drives
# --chat-pane-bg (the .desk-main backdrop behind the transparent iframe).
DESKTOP_HUB_LIGHT_BG_ALPHA = 0.88
DESKTOP_HUB_DARK_BG_ALPHA = 0.90
DESKTOP_CHAT_LIGHT_BG_ALPHA = 0.94
DESKTOP_CHAT_DARK_BG_ALPHA = 0.95


def resolve_theme_fg_level(theme: str = "dark") -> int:
    theme = str(theme or "dark").strip().lower()
    return 0 if theme == "light" else 180


def resolve_theme_palette(theme: str = "dark") -> dict[str, object]:
    theme = str(theme or "dark").strip().lower()
    theme = "light" if theme == "light" else "dark"
    fg_level = resolve_theme_fg_level(theme)
    if theme == "light":
        color_scheme = "light"
        surface_level = 250
        inline_border_level = 202
        muted_level = 120
        icon_fg_level = 0
        icon_muted_level = 120
        icon_hover_level = 35
        chip_color_level = 180
        line = "rgba(0, 0, 0, 0.10)"
        line_strong = "rgba(0, 0, 0, 0.18)"
        code_copy_hover_bg = "rgba(0, 0, 0, 0.08)"
        session_hover_bg = "rgba(0, 0, 0, 0.04)"
        session_selected_bg = "rgba(0, 0, 0, 0.07)"
        panel_row_bg = "rgba(0, 0, 0, 0.06)"
        panel_row_border = "rgba(0, 0, 0, 0.08)"
        panel_row_hover_bg = "rgba(0, 0, 0, 0.08)"
        panel_row_active_bg = "rgba(0, 0, 0, 0.10)"
    else:
        color_scheme = "dark"
        surface_level = 10
        inline_border_level = 54
        icon_fg_level = 180
        icon_muted_level = 128
        icon_hover_level = 190
        muted_level = icon_muted_level
        chip_color_level = 70
        line = f"rgba({fg_level}, {fg_level}, {fg_level}, 0.07)"
        line_strong = f"rgba({fg_level}, {fg_level}, {fg_level}, 0.12)"
        code_copy_hover_bg = f"rgba({fg_level}, {fg_level}, {fg_level}, 0.09)"
        session_hover_bg = f"rgba({fg_level}, {fg_level}, {fg_level}, 0.05)"
        session_selected_bg = f"rgba({fg_level}, {fg_level}, {fg_level}, 0.08)"
        panel_row_bg = f"rgba({fg_level}, {fg_level}, {fg_level}, 0.10)"
        panel_row_border = f"rgba({fg_level}, {fg_level}, {fg_level}, 0.14)"
        panel_row_hover_bg = f"rgba({fg_level}, {fg_level}, {fg_level}, 0.13)"
        panel_row_active_bg = f"rgba({fg_level}, {fg_level}, {fg_level}, 0.16)"
    # __DARK_BG__/__DARK_BG_CHANNELS__ feed the :root pre-toggle fallback, the
    # launch shell, the meta theme-color and the error page -- shell contexts,
    # not the chat surface -- so they track the hub value.
    bg_rgb = DESKTOP_HUB_LIGHT_BG_RGB if theme == "light" else DESKTOP_HUB_DARK_BG_RGB
    # The mobile chat :root pre-toggle fallback tracks the resolved theme's
    # own chat bg (not the hub value), so hand-tuning MOBILE_CHAT_*_BG_RGB
    # can't leave it out of sync.
    mobile_chat_bg_rgb = MOBILE_CHAT_LIGHT_BG_RGB if theme == "light" else MOBILE_CHAT_DARK_BG_RGB
    fg_rgb = (fg_level, fg_level, fg_level)
    return {
        "theme": theme,
        "color_scheme": color_scheme,
        "dark_bg_channels": ", ".join(str(v) for v in bg_rgb),
        "dark_bg": f"rgb({','.join(str(v) for v in bg_rgb)})",
        "desktop_hub_light_bg": f"rgb({','.join(str(v) for v in DESKTOP_HUB_LIGHT_BG_RGB)})",
        "desktop_hub_light_bg_fill": f"rgba({', '.join(str(v) for v in DESKTOP_HUB_LIGHT_BG_RGB)}, {DESKTOP_HUB_LIGHT_BG_ALPHA})",
        "desktop_hub_dark_bg": f"rgb({','.join(str(v) for v in DESKTOP_HUB_DARK_BG_RGB)})",
        "desktop_hub_dark_bg_fill": f"rgba({', '.join(str(v) for v in DESKTOP_HUB_DARK_BG_RGB)}, {DESKTOP_HUB_DARK_BG_ALPHA})",
        "desktop_chat_light_bg_channels": ", ".join(str(v) for v in DESKTOP_CHAT_LIGHT_BG_RGB),
        "desktop_chat_light_bg_fill": f"rgba({', '.join(str(v) for v in DESKTOP_CHAT_LIGHT_BG_RGB)}, {DESKTOP_CHAT_LIGHT_BG_ALPHA})",
        "desktop_chat_dark_bg_channels": ", ".join(str(v) for v in DESKTOP_CHAT_DARK_BG_RGB),
        "desktop_chat_dark_bg_fill": f"rgba({', '.join(str(v) for v in DESKTOP_CHAT_DARK_BG_RGB)}, {DESKTOP_CHAT_DARK_BG_ALPHA})",
        "mobile_hub_light_bg_channels": ", ".join(str(v) for v in MOBILE_HUB_LIGHT_BG_RGB),
        "mobile_hub_light_bg": f"rgb({','.join(str(v) for v in MOBILE_HUB_LIGHT_BG_RGB)})",
        "mobile_hub_dark_bg_channels": ", ".join(str(v) for v in MOBILE_HUB_DARK_BG_RGB),
        "mobile_hub_dark_bg": f"rgb({','.join(str(v) for v in MOBILE_HUB_DARK_BG_RGB)})",
        "mobile_chat_light_bg_channels": ", ".join(str(v) for v in MOBILE_CHAT_LIGHT_BG_RGB),
        "mobile_chat_dark_bg_channels": ", ".join(str(v) for v in MOBILE_CHAT_DARK_BG_RGB),
        "mobile_chat_bg_channels": ", ".join(str(v) for v in mobile_chat_bg_rgb),
        "light_fg": f"rgb({','.join(str(v) for v in fg_rgb)})",
        "light_fg_channels": ", ".join(str(v) for v in fg_rgb),
        "gray_surface": _gray_rgb_string(surface_level),
        "gray_inline_border": _gray_rgb_string(inline_border_level),
        "gray_muted": _gray_rgb_string(muted_level),
        "icon_fg": _gray_rgb_string(icon_fg_level),
        "icon_muted": _gray_rgb_string(icon_muted_level),
        "icon_hover": _gray_rgb_string(icon_hover_level),
        "chip_color": _gray_rgb_string(chip_color_level),
        "line": line,
        "line_strong": line_strong,
        "code_copy_hover_bg": code_copy_hover_bg,
        "session_hover_bg": session_hover_bg,
        "session_selected_bg": session_selected_bg,
        "panel_row_bg": panel_row_bg,
        "panel_row_border": panel_row_border,
        "panel_row_hover_bg": panel_row_hover_bg,
        "panel_row_active_bg": panel_row_active_bg,
    }


_DEFAULT_THEME = resolve_theme_palette()
DARK_BG = _DEFAULT_THEME["dark_bg"]


def apply_color_tokens(
    text: str,
    *,
    theme: str = "dark",
    mobile_theme_setting: str = "system",
) -> str:
    palette = resolve_theme_palette(theme)
    dark_bg = str(palette["dark_bg"])
    dark_bg_channels = str(palette["dark_bg_channels"])
    desktop_hub_light_bg = str(palette["desktop_hub_light_bg"])
    desktop_hub_light_bg_fill = str(palette["desktop_hub_light_bg_fill"])
    desktop_hub_dark_bg = str(palette["desktop_hub_dark_bg"])
    desktop_hub_dark_bg_fill = str(palette["desktop_hub_dark_bg_fill"])
    desktop_chat_light_bg_channels = str(palette["desktop_chat_light_bg_channels"])
    desktop_chat_light_bg_fill = str(palette["desktop_chat_light_bg_fill"])
    desktop_chat_dark_bg_channels = str(palette["desktop_chat_dark_bg_channels"])
    desktop_chat_dark_bg_fill = str(palette["desktop_chat_dark_bg_fill"])
    mobile_hub_light_bg = str(palette["mobile_hub_light_bg"])
    mobile_hub_light_bg_channels = str(palette["mobile_hub_light_bg_channels"])
    mobile_hub_dark_bg = str(palette["mobile_hub_dark_bg"])
    mobile_hub_dark_bg_channels = str(palette["mobile_hub_dark_bg_channels"])
    mobile_chat_light_bg_channels = str(palette["mobile_chat_light_bg_channels"])
    mobile_chat_dark_bg_channels = str(palette["mobile_chat_dark_bg_channels"])
    mobile_chat_bg_channels = str(palette["mobile_chat_bg_channels"])
    light_fg = str(palette["light_fg"])
    gray_surface = str(palette["gray_surface"])
    gray_inline_border = str(palette["gray_inline_border"])
    gray_muted = str(palette["gray_muted"])
    icon_fg = str(palette["icon_fg"])
    icon_muted = str(palette["icon_muted"])
    icon_hover = str(palette["icon_hover"])
    chip_color = str(palette["chip_color"])

    replacements: tuple[tuple[str, str], ...] = (
        ("__THEME__", str(palette["theme"])),
        ("__THEME_MOBILE_SETTING__", mobile_theme_setting),
        ("__COLOR_SCHEME__", str(palette["color_scheme"])),
        ("__DARK_BG__", dark_bg),
        ("__DARK_BG_CHANNELS__", dark_bg_channels),
        ("__DESKTOP_HUB_LIGHT_BG__", desktop_hub_light_bg),
        ("__DESKTOP_HUB_LIGHT_BG_FILL__", desktop_hub_light_bg_fill),
        ("__DESKTOP_HUB_DARK_BG__", desktop_hub_dark_bg),
        ("__DESKTOP_HUB_DARK_BG_FILL__", desktop_hub_dark_bg_fill),
        ("__DESKTOP_CHAT_LIGHT_BG_CHANNELS__", desktop_chat_light_bg_channels),
        ("__DESKTOP_CHAT_LIGHT_BG_FILL__", desktop_chat_light_bg_fill),
        ("__DESKTOP_CHAT_DARK_BG_CHANNELS__", desktop_chat_dark_bg_channels),
        ("__DESKTOP_CHAT_DARK_BG_FILL__", desktop_chat_dark_bg_fill),
        ("__MOBILE_HUB_LIGHT_BG__", mobile_hub_light_bg),
        ("__MOBILE_HUB_LIGHT_BG_CHANNELS__", mobile_hub_light_bg_channels),
        ("__MOBILE_HUB_DARK_BG__", mobile_hub_dark_bg),
        ("__MOBILE_HUB_DARK_BG_CHANNELS__", mobile_hub_dark_bg_channels),
        ("__MOBILE_CHAT_LIGHT_BG_CHANNELS__", mobile_chat_light_bg_channels),
        ("__MOBILE_CHAT_DARK_BG_CHANNELS__", mobile_chat_dark_bg_channels),
        ("__MOBILE_CHAT_BG_CHANNELS__", mobile_chat_bg_channels),
        ("__LIGHT_FG__", light_fg),
        ("__GRAY_SURFACE__", gray_surface),
        ("__GRAY_INLINE_BORDER__", gray_inline_border),
        ("__GRAY_MUTED__", gray_muted),
        ("__ICON_FG__", icon_fg),
        ("__ICON_MUTED__", icon_muted),
        ("__ICON_HOVER__", icon_hover),
        ("__CHIP_COLOR__", chip_color),
        ("__DESKTOP_LIGHT_ICON_HOVER__", DESKTOP_LIGHT_ICON_HOVER),
        ("__DESKTOP_DARK_ICON_HOVER__", DESKTOP_DARK_ICON_HOVER),
        ("__MOBILE_LIGHT_ICON_HOVER__", MOBILE_LIGHT_ICON_HOVER),
        ("__MOBILE_DARK_ICON_HOVER__", MOBILE_DARK_ICON_HOVER),
        *_text_color_token_replacements(),
        ("__LINE__", str(palette["line"])),
        ("__LINE_STRONG__", str(palette["line_strong"])),
        ("__CODE_COPY_HOVER_BG__", str(palette["code_copy_hover_bg"])),
        ("__SESSION_HOVER_BG__", str(palette["session_hover_bg"])),
        ("__SESSION_SELECTED_BG__", str(palette["session_selected_bg"])),
        ("__PANEL_ROW_BG__", str(palette["panel_row_bg"])),
        ("__PANEL_ROW_BORDER__", str(palette["panel_row_border"])),
        ("__PANEL_ROW_HOVER_BG__", str(palette["panel_row_hover_bg"])),
        ("__PANEL_ROW_ACTIVE_BG__", str(palette["panel_row_active_bg"])),
    )
    resolved = text
    for old, new in replacements:
        resolved = resolved.replace(old, new)
    return resolved
