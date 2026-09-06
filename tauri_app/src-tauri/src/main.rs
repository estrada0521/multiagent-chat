use objc2_app_kit::{
    NSBitmapImageFileType, NSBitmapImageRep, NSView, NSWindow, NSWindowButton, NSWorkspace,
};
use objc2_foundation::{NSDictionary, NSString};
use std::collections::HashMap;
use std::io::Read;
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::OnceLock;
use std::thread;
use std::time::{Duration, Instant};
use tauri::menu::{
    CheckMenuItemBuilder, IconMenuItemBuilder, MenuBuilder, MenuItemBuilder, NativeIcon,
    SubmenuBuilder,
};
use tauri::webview::WebviewWindowBuilder;
use tauri::Manager;
use url::Url;

const DEFAULT_WINDOW_SIZE: f64 = 896.0;
const MIN_WINDOW_WIDTH: f64 = 160.0;
const MIN_WINDOW_HEIGHT: f64 = 103.0;
// "Fit Height to Message" mode drops the height floor to zero so a one-line
// message really does get a one-line window.
const FIT_WINDOW_MIN_HEIGHT: f64 = 0.0;
const COMPACT_WINDOW_WIDTH: f64 = 560.0;

use window_vibrancy::{
    apply_liquid_glass, apply_vibrancy, clear_liquid_glass, clear_vibrancy, NSGlassEffectViewStyle,
    NSVisualEffectMaterial, NSVisualEffectState,
};

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct ChatHeaderMenuPayload {
    x: f64,
    y: f64,
    session_active: bool,
    add_agents: Vec<String>,
    remove_agents: Vec<String>,
    #[serde(default)]
    agent_icons: HashMap<String, Vec<u8>>,
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct AppearanceMenuPayload {
    x: f64,
    y: f64,
    theme_desktop: String,
    text_size: i32,
    text_size_default: i32,
    always_on_top: bool,
    auto_window_height: bool,
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct SessionSwitcherMenuPayload {
    x: f64,
    y: f64,
    items: Vec<SessionSwitcherMenuItem>,
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct SessionSwitcherMenuItem {
    label: String,
    #[serde(default)]
    section: bool,
    #[serde(default)]
    current: bool,
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct FileContextMenuPayload {
    x: f64,
    y: f64,
    reveal_enabled: bool,
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct SessionContextMenuPayload {
    x: f64,
    y: f64,
}

#[tauri::command]
fn open_external_url(url: String) -> Result<(), String> {
    let parsed = Url::parse(&url).map_err(|err| format!("invalid external URL: {err}"))?;
    if !matches!(parsed.scheme(), "http" | "https") || parsed.host_str().is_none() {
        return Err("external URL must be an absolute http or https URL".to_string());
    }
    let status = Command::new("/usr/bin/open")
        .arg(parsed.as_str())
        .status()
        .map_err(|err| format!("could not start macOS URL opener: {err}"))?;
    if !status.success() {
        return Err("macOS URL opener failed".to_string());
    }
    Ok(())
}

fn agent_base_name(name: &str) -> String {
    let lower = name.to_lowercase();
    if let Some(pos) = lower.rfind('-') {
        let suffix = &lower[pos + 1..];
        if !suffix.is_empty() && suffix.chars().all(|c| c.is_ascii_digit()) {
            return lower[..pos].to_string();
        }
    }
    lower
}

#[derive(Debug, serde::Serialize)]
struct NativeMenuActionPayload {
    action: String,
    mode: Option<String>,
    agent: Option<String>,
    theme: Option<String>,
}

const INJECT_JS: &str = include_str!("inject.js");
const NATIVE_MENU_PREFIX: &str = "agent-window-chat:";

fn encode_menu_component(value: &str) -> String {
    let mut out = String::new();
    for byte in value.as_bytes() {
        let ch = *byte as char;
        if ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' {
            out.push(ch);
        } else {
            out.push('~');
            out.push_str(&format!("{:02X}", byte));
        }
    }
    out
}

fn decode_menu_component(value: &str) -> String {
    let bytes = value.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'~' && i + 2 < bytes.len() {
            if let Ok(hex) = std::str::from_utf8(&bytes[i + 1..i + 3]) {
                if let Ok(decoded) = u8::from_str_radix(hex, 16) {
                    out.push(decoded);
                    i += 3;
                    continue;
                }
            }
        }
        out.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).to_string()
}

fn system_app_icon(path: &str) -> Result<tauri::image::Image<'static>, String> {
    let path = NSString::from_str(path);
    let image = NSWorkspace::sharedWorkspace().iconForFile(&path);
    let tiff = image
        .TIFFRepresentation()
        .ok_or_else(|| format!("could not render system app icon: {}", path))?;
    let bitmap = NSBitmapImageRep::imageRepWithData(&tiff)
        .ok_or_else(|| format!("could not decode system app icon: {}", path))?;
    let properties = NSDictionary::new();
    let png = unsafe {
        bitmap.representationUsingType_properties(NSBitmapImageFileType::PNG, &properties)
    }
    .ok_or_else(|| format!("could not encode system app icon: {}", path))?;
    let decoded = image::load_from_memory_with_format(&png.to_vec(), image::ImageFormat::Png)
        .map_err(|err| err.to_string())
        .map(image::DynamicImage::into_rgba8)?;
    let (width, height) = decoded.dimensions();
    Ok(tauri::image::Image::new_owned(
        decoded.into_raw(),
        width,
        height,
    ))
}

struct SystemAppIcons {
    terminal: tauri::image::Image<'static>,
    finder: tauri::image::Image<'static>,
}

static SYSTEM_APP_ICONS: OnceLock<Result<SystemAppIcons, String>> = OnceLock::new();

fn system_app_icons() -> Result<&'static SystemAppIcons, String> {
    SYSTEM_APP_ICONS
        .get_or_init(|| {
            Ok(SystemAppIcons {
                terminal: system_app_icon("/System/Applications/Utilities/Terminal.app")?,
                finder: system_app_icon("/System/Library/CoreServices/Finder.app")?,
            })
        })
        .as_ref()
        .map_err(Clone::clone)
}

#[tauri::command]
fn show_chat_header_menu(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
    payload: ChatHeaderMenuPayload,
) -> Result<(), String> {
    let add_enabled = payload.session_active && !payload.add_agents.is_empty();
    let remove_enabled = payload.session_active && payload.remove_agents.len() > 1;

    let mut add_builder = SubmenuBuilder::with_id(
        &app,
        format!("{}submenu:addAgent", NATIVE_MENU_PREFIX),
        "Add Agent",
    )
    .submenu_native_icon(NativeIcon::Add)
    .enabled(add_enabled);
    for agent in &payload.add_agents {
        let id = format!("{}add:{}", NATIVE_MENU_PREFIX, encode_menu_component(agent));
        let base = agent_base_name(agent);
        if let Some(rgba) = payload.agent_icons.get(&base) {
            if rgba.len() == 22 * 22 * 4 {
                let img = tauri::image::Image::new_owned(rgba.clone(), 22, 22);
                add_builder = add_builder.icon(id, agent.as_str(), img);
                continue;
            }
        }
        add_builder = add_builder.native_icon(id, agent.as_str(), NativeIcon::User);
    }
    let add_submenu = add_builder.build().map_err(|err| err.to_string())?;

    let mut remove_builder = SubmenuBuilder::with_id(
        &app,
        format!("{}submenu:removeAgent", NATIVE_MENU_PREFIX),
        "Remove Agent",
    )
    .submenu_native_icon(NativeIcon::Remove)
    .enabled(remove_enabled);
    for agent in &payload.remove_agents {
        let id = format!(
            "{}remove:{}",
            NATIVE_MENU_PREFIX,
            encode_menu_component(agent)
        );
        let base = agent_base_name(agent);
        if let Some(rgba) = payload.agent_icons.get(&base) {
            if rgba.len() == 22 * 22 * 4 {
                let img = tauri::image::Image::new_owned(rgba.clone(), 22, 22);
                remove_builder = remove_builder.icon(id, agent.as_str(), img);
                continue;
            }
        }
        remove_builder = remove_builder.native_icon(id, agent.as_str(), NativeIcon::User);
    }
    let remove_submenu = remove_builder.build().map_err(|err| err.to_string())?;

    let icons = system_app_icons()?;
    let terminal_item = IconMenuItemBuilder::with_id(
        format!("{}action:openTerminal", NATIVE_MENU_PREFIX),
        "Terminal",
    )
    .icon(icons.terminal.clone())
    .accelerator("Alt+Cmd+T")
    .build(&app)
    .map_err(|err| err.to_string())?;
    let finder_item =
        IconMenuItemBuilder::with_id(format!("{}action:openFinder", NATIVE_MENU_PREFIX), "Finder")
            .icon(icons.finder.clone())
            .accelerator("Alt+Cmd+R")
            .build(&app)
            .map_err(|err| err.to_string())?;

    let menu = MenuBuilder::new(&app)
        .item(&terminal_item)
        .item(&finder_item)
        .separator()
        .item(&add_submenu)
        .item(&remove_submenu)
        .build()
        .map_err(|err| err.to_string())?;

    window
        .popup_menu_at(&menu, tauri::LogicalPosition::new(payload.x, payload.y))
        .map_err(|err| err.to_string())
}

#[tauri::command]
fn show_appearance_menu(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
    payload: AppearanceMenuPayload,
) -> Result<(), String> {
    let current = payload.theme_desktop.as_str();
    let theme_item = |value: &str, label: &str| -> Result<tauri::menu::CheckMenuItem<_>, String> {
        CheckMenuItemBuilder::with_id(format!("{}theme:{}", NATIVE_MENU_PREFIX, value), label)
            .checked(current == value)
            .build(&app)
            .map_err(|err| err.to_string())
    };
    let system_item = theme_item("system", "System")?;
    let light_item = theme_item("light", "Light")?;
    let dark_item = theme_item("dark", "Dark")?;

    let theme_submenu = SubmenuBuilder::with_id(
        &app,
        format!("{}submenu:theme", NATIVE_MENU_PREFIX),
        "Theme",
    )
    .item(&system_item)
    .item(&light_item)
    .item(&dark_item)
    .build()
    .map_err(|err| err.to_string())?;

    let actual_size = MenuItemBuilder::with_id(
        format!("{}textSize:actual", NATIVE_MENU_PREFIX),
        "Actual Size",
    )
    .enabled(payload.text_size != payload.text_size_default)
    .accelerator("Cmd+0")
    .build(&app)
    .map_err(|err| err.to_string())?;
    let zoom_in = MenuItemBuilder::with_id(
        format!("{}textSize:increase", NATIVE_MENU_PREFIX),
        "Zoom In",
    )
    .accelerator("Cmd+Equal")
    .build(&app)
    .map_err(|err| err.to_string())?;
    let zoom_out = MenuItemBuilder::with_id(
        format!("{}textSize:decrease", NATIVE_MENU_PREFIX),
        "Zoom Out",
    )
    .accelerator("Cmd+-")
    .build(&app)
    .map_err(|err| err.to_string())?;

    let reset_window = MenuItemBuilder::with_id(
        format!("{}action:resetWindow", NATIVE_MENU_PREFIX),
        "Reset Window",
    )
    .accelerator("Cmd+Alt+0")
    .build(&app)
    .map_err(|err| err.to_string())?;

    let compact_window = MenuItemBuilder::with_id(
        format!("{}action:compactWindow", NATIVE_MENU_PREFIX),
        "Compact Window",
    )
    .accelerator("Cmd+Alt+9")
    .build(&app)
    .map_err(|err| err.to_string())?;

    let move_top = MenuItemBuilder::with_id(
        format!("{}action:moveWindowTop", NATIVE_MENU_PREFIX),
        "Move to Top",
    )
    .accelerator("Cmd+Alt+Up")
    .build(&app)
    .map_err(|err| err.to_string())?;
    let move_left = MenuItemBuilder::with_id(
        format!("{}action:moveWindowTopLeft", NATIVE_MENU_PREFIX),
        "Move to Left",
    )
    .accelerator("Cmd+Alt+Left")
    .build(&app)
    .map_err(|err| err.to_string())?;
    let move_right = MenuItemBuilder::with_id(
        format!("{}action:moveWindowTopRight", NATIVE_MENU_PREFIX),
        "Move to Right",
    )
    .accelerator("Cmd+Alt+Right")
    .build(&app)
    .map_err(|err| err.to_string())?;

    let toggle_sidebar = MenuItemBuilder::with_id(
        format!("{}action:toggleHubSidebar", NATIVE_MENU_PREFIX),
        "Toggle Hub Sidebar",
    )
    .accelerator("Cmd+B")
    .build(&app)
    .map_err(|err| err.to_string())?;
    let toggle_right_pane = MenuItemBuilder::with_id(
        format!("{}action:toggleRightPane", NATIVE_MENU_PREFIX),
        "Toggle Right Pane",
    )
    .accelerator("Cmd+E")
    .build(&app)
    .map_err(|err| err.to_string())?;
    let toggle_sidebar_outward = MenuItemBuilder::with_id(
        format!("{}action:toggleHubSidebarOutward", NATIVE_MENU_PREFIX),
        "Toggle Hub Sidebar Outward",
    )
    .accelerator("Cmd+Alt+B")
    .build(&app)
    .map_err(|err| err.to_string())?;
    let toggle_right_pane_outward = MenuItemBuilder::with_id(
        format!("{}action:toggleRightPaneOutward", NATIVE_MENU_PREFIX),
        "Toggle Right Pane Outward",
    )
    .accelerator("Cmd+Alt+E")
    .build(&app)
    .map_err(|err| err.to_string())?;

    let always_on_top = CheckMenuItemBuilder::with_id(
        format!("{}action:toggleAlwaysOnTop", NATIVE_MENU_PREFIX),
        "Always on Top",
    )
    .checked(payload.always_on_top)
    .accelerator("Cmd+Alt+P")
    .build(&app)
    .map_err(|err| err.to_string())?;

    let auto_window_height = CheckMenuItemBuilder::with_id(
        format!("{}action:toggleAutoWindowHeight", NATIVE_MENU_PREFIX),
        "Fit Height to Message",
    )
    .checked(payload.auto_window_height)
    .accelerator("Cmd+Alt+H")
    .build(&app)
    .map_err(|err| err.to_string())?;

    let open_settings_file = MenuItemBuilder::with_id(
        format!("{}action:openSettingsFile", NATIVE_MENU_PREFIX),
        "Open Settings File",
    )
    .accelerator("Cmd+,")
    .build(&app)
    .map_err(|err| err.to_string())?;

    let menu = MenuBuilder::new(&app)
        .item(&theme_submenu)
        .separator()
        .item(&actual_size)
        .item(&zoom_in)
        .item(&zoom_out)
        .separator()
        .item(&reset_window)
        .item(&compact_window)
        .item(&move_top)
        .item(&move_left)
        .item(&move_right)
        .item(&toggle_sidebar)
        .item(&toggle_right_pane)
        .item(&toggle_sidebar_outward)
        .item(&toggle_right_pane_outward)
        .item(&always_on_top)
        .item(&auto_window_height)
        .separator()
        .item(&open_settings_file)
        .build()
        .map_err(|err| err.to_string())?;

    window
        .popup_menu_at(&menu, tauri::LogicalPosition::new(payload.x, payload.y))
        .map_err(|err| err.to_string())
}

// "Fit Height to Message" shrinks the window below the height the DOM session
// popover needs, and a DOM popover can't paint past the window edge. A native
// menu can, so in that mode the collapsed sidebar switches sessions through it.
#[tauri::command]
fn show_session_switcher_menu(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
    payload: SessionSwitcherMenuPayload,
) -> Result<(), String> {
    let mut builder = MenuBuilder::new(&app);
    for (index, item) in payload.items.iter().enumerate() {
        if item.section {
            let label = MenuItemBuilder::with_id(
                format!("{}session:section:{}", NATIVE_MENU_PREFIX, index),
                &item.label,
            )
            .enabled(false)
            .build(&app)
            .map_err(|err| err.to_string())?;
            builder = builder.item(&label);
        } else {
            let entry = CheckMenuItemBuilder::with_id(
                format!("{}session:{}", NATIVE_MENU_PREFIX, index),
                &item.label,
            )
            .checked(item.current)
            .build(&app)
            .map_err(|err| err.to_string())?;
            builder = builder.item(&entry);
        }
    }
    let menu = builder.build().map_err(|err| err.to_string())?;
    window
        .popup_menu_at(&menu, tauri::LogicalPosition::new(payload.x, payload.y))
        .map_err(|err| err.to_string())
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct GitChangesMenuPayload {
    x: f64,
    y: f64,
    items: Vec<GitChangesMenuItem>,
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct GitChangesMenuItem {
    label: String,
    #[serde(default)]
    section: bool,
}

// Fit Height to Message shrinks the window below what the right panel needs, so
// in that mode the panel toggle pops the uncommitted-file list through a native
// menu instead (the DOM panel can't paint past the tiny window).
#[tauri::command]
fn show_git_changes_menu(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
    payload: GitChangesMenuPayload,
) -> Result<(), String> {
    let mut builder = MenuBuilder::new(&app);
    for (index, item) in payload.items.iter().enumerate() {
        if item.section {
            let label = MenuItemBuilder::with_id(
                format!("{}gitfile:section:{}", NATIVE_MENU_PREFIX, index),
                &item.label,
            )
            .enabled(false)
            .build(&app)
            .map_err(|err| err.to_string())?;
            builder = builder.item(&label);
        } else {
            let entry = MenuItemBuilder::with_id(
                format!("{}gitfile:{}", NATIVE_MENU_PREFIX, index),
                &item.label,
            )
            .build(&app)
            .map_err(|err| err.to_string())?;
            builder = builder.item(&entry);
        }
    }
    let menu = builder.build().map_err(|err| err.to_string())?;
    window
        .popup_menu_at(&menu, tauri::LogicalPosition::new(payload.x, payload.y))
        .map_err(|err| err.to_string())
}

#[tauri::command]
fn show_file_context_menu(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
    payload: FileContextMenuPayload,
) -> Result<(), String> {
    let reveal = MenuItemBuilder::with_id(
        format!("{}action:revealFileInFinder", NATIVE_MENU_PREFIX),
        "Reveal in Finder",
    )
    .enabled(payload.reveal_enabled)
    .build(&app)
    .map_err(|err| err.to_string())?;
    let copy_absolute = MenuItemBuilder::with_id(
        format!("{}action:copyAbsoluteFilePath", NATIVE_MENU_PREFIX),
        "Copy Absolute Path",
    )
    .build(&app)
    .map_err(|err| err.to_string())?;
    let copy_relative = MenuItemBuilder::with_id(
        format!("{}action:copyRelativeFilePath", NATIVE_MENU_PREFIX),
        "Copy Relative Path",
    )
    .build(&app)
    .map_err(|err| err.to_string())?;
    let menu = MenuBuilder::new(&app)
        .item(&reveal)
        .separator()
        .item(&copy_absolute)
        .item(&copy_relative)
        .build()
        .map_err(|err| err.to_string())?;

    window
        .popup_menu_at(&menu, tauri::LogicalPosition::new(payload.x, payload.y))
        .map_err(|err| err.to_string())
}

#[tauri::command]
fn show_session_context_menu(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
    payload: SessionContextMenuPayload,
) -> Result<(), String> {
    let rename = MenuItemBuilder::with_id(
        format!("{}action:renameSession", NATIVE_MENU_PREFIX),
        "Rename",
    )
    .build(&app)
    .map_err(|err| err.to_string())?;
    let menu = MenuBuilder::new(&app)
        .item(&rename)
        .build()
        .map_err(|err| err.to_string())?;

    window
        .popup_menu_at(&menu, tauri::LogicalPosition::new(payload.x, payload.y))
        .map_err(|err| err.to_string())
}

#[tauri::command]
fn reset_window_geometry(window: tauri::WebviewWindow) -> Result<(), String> {
    // .center() reads the window's own current size to compute a centered
    // position; called right after set_size(), that read can still see the
    // pre-resize size, landing off-center. Compute the target position from
    // the monitor instead, independent of the window's (possibly not yet
    // applied) size.
    let scale_factor = window.scale_factor().map_err(|err| err.to_string())?;
    let monitor = window
        .current_monitor()
        .map_err(|err| err.to_string())?
        .ok_or_else(|| "no monitor available".to_string())?;
    let monitor_pos = monitor.position().to_logical::<f64>(scale_factor);
    let monitor_size = monitor.size().to_logical::<f64>(scale_factor);
    let x = monitor_pos.x + ((monitor_size.width - DEFAULT_WINDOW_SIZE) / 2.0).max(0.0);
    let y = monitor_pos.y + ((monitor_size.height - DEFAULT_WINDOW_SIZE) / 2.0).max(0.0);
    window
        .set_size(tauri::LogicalSize::new(
            DEFAULT_WINDOW_SIZE,
            DEFAULT_WINDOW_SIZE,
        ))
        .map_err(|err| err.to_string())?;
    window
        .set_position(tauri::LogicalPosition::new(x, y))
        .map_err(|err| err.to_string())
}

#[tauri::command]
fn set_always_on_top(window: tauri::WebviewWindow, on: bool) -> Result<(), String> {
    window.set_always_on_top(on).map_err(|err| err.to_string())
}

#[tauri::command]
fn set_fit_height_min(window: tauri::WebviewWindow, enabled: bool) -> Result<(), String> {
    // In Fit Height to Message mode the window may need to be far shorter than
    // the normal minimum; drop the floor while it is on, restore it when off.
    let min_h = if enabled {
        FIT_WINDOW_MIN_HEIGHT
    } else {
        MIN_WINDOW_HEIGHT
    };
    window
        .set_min_size(Some(tauri::LogicalSize::new(MIN_WINDOW_WIDTH, min_h)))
        .map_err(|err| err.to_string())?;
    // The window is small in this mode and driven entirely by shortcut, so the
    // macOS traffic lights only loom. Hide them while it is on, restore (and
    // re-centre) them when it is off.
    set_traffic_lights_hidden(&window, enabled);
    if !enabled {
        center_traffic_lights(&window);
    }
    Ok(())
}

fn set_traffic_lights_hidden(window: &tauri::WebviewWindow, hidden: bool) {
    let Ok(handle) = window.ns_window() else { return };
    unsafe {
        let ns_window: &NSWindow = &*(handle as *const NSWindow);
        for kind in [
            NSWindowButton::CloseButton,
            NSWindowButton::MiniaturizeButton,
            NSWindowButton::ZoomButton,
        ] {
            if let Some(button) = ns_window.standardWindowButton(kind) {
                button.setHidden(hidden);
            }
        }
    }
}

#[tauri::command]
fn set_window_height(
    window: tauri::WebviewWindow,
    height: f64,
    snap_compact_width: Option<bool>,
) -> Result<(), String> {
    // Width and x stay; only the height (and, if it would spill off the
    // bottom, y) change. Clamped to a sane floor and the monitor height.
    // snap_compact_width also pulls the width to the compact size and recenters
    // x -- the one-shot the Fit Height toggle fires on entry so the window
    // lands at its final size in a single resize instead of visibly stopping at
    // the compact width first.
    let scale_factor = window.scale_factor().map_err(|err| err.to_string())?;
    let monitor = window
        .current_monitor()
        .map_err(|err| err.to_string())?
        .ok_or_else(|| "no monitor available".to_string())?;
    let monitor_pos = monitor.position().to_logical::<f64>(scale_factor);
    let monitor_size = monitor.size().to_logical::<f64>(scale_factor);
    let cur_size = window
        .inner_size()
        .map_err(|err| err.to_string())?
        .to_logical::<f64>(scale_factor);
    let cur_pos = window
        .outer_position()
        .map_err(|err| err.to_string())?
        .to_logical::<f64>(scale_factor);
    // set_window_height is only used by Fit Height mode, where the floor is
    // deliberately near-zero (set_fit_height_min lowers the window minimum).
    let h = height.max(FIT_WINDOW_MIN_HEIGHT).min(monitor_size.height);
    let (w, x) = if snap_compact_width.unwrap_or(false) {
        let w = COMPACT_WINDOW_WIDTH.min(monitor_size.width);
        (w, monitor_pos.x + ((monitor_size.width - w) / 2.0).max(0.0))
    } else {
        (cur_size.width, cur_pos.x)
    };
    let mut y = cur_pos.y;
    if y + h > monitor_pos.y + monitor_size.height {
        y = monitor_pos.y + monitor_size.height - h;
    }
    if y < monitor_pos.y {
        y = monitor_pos.y;
    }
    window
        .set_size(tauri::LogicalSize::new(w, h))
        .map_err(|err| err.to_string())?;
    window
        .set_position(tauri::LogicalPosition::new(x, y))
        .map_err(|err| err.to_string())
}

#[tauri::command]
fn compact_window_geometry(window: tauri::WebviewWindow) -> Result<(), String> {
    // Same centering approach as reset_window_geometry: compute the target
    // position from the monitor, not the window's (possibly stale) own size.
    let width = COMPACT_WINDOW_WIDTH;
    let height = DEFAULT_WINDOW_SIZE;
    let scale_factor = window.scale_factor().map_err(|err| err.to_string())?;
    let monitor = window
        .current_monitor()
        .map_err(|err| err.to_string())?
        .ok_or_else(|| "no monitor available".to_string())?;
    let monitor_pos = monitor.position().to_logical::<f64>(scale_factor);
    let monitor_size = monitor.size().to_logical::<f64>(scale_factor);
    let x = monitor_pos.x + ((monitor_size.width - width) / 2.0).max(0.0);
    let y = monitor_pos.y + ((monitor_size.height - height) / 2.0).max(0.0);
    window
        .set_size(tauri::LogicalSize::new(width, height))
        .map_err(|err| err.to_string())?;
    window
        .set_position(tauri::LogicalPosition::new(x, y))
        .map_err(|err| err.to_string())
}

#[tauri::command]
fn resize_window_from_edge(
    window: tauri::WebviewWindow,
    edge: String,
    delta: f64,
) -> Result<(), String> {
    if !delta.is_finite() || delta == 0.0 {
        return Err("window width delta must be a non-zero finite number".to_string());
    }
    let handle = window.ns_window().map_err(|err| err.to_string())?;
    unsafe {
        let ns_window: &NSWindow = &*(handle as *const NSWindow);
        let mut frame = ns_window.frame();
        let next_width = frame.size.width + delta;
        if next_width < MIN_WINDOW_WIDTH {
            return Err(format!(
                "window width would fall below the minimum ({MIN_WINDOW_WIDTH})"
            ));
        }
        match edge.as_str() {
            "left" => frame.origin.x -= delta,
            "right" => {}
            _ => return Err(format!("unsupported window edge: {edge}")),
        }
        frame.size.width = next_width;
        ns_window.setFrame_display(frame, true);
    }
    Ok(())
}

// How tall the menu bar (and, on a notched Mac, the extra strip beside it)
// actually is varies by machine and can't be hardcoded -- NSScreen's own
// frame vs visibleFrame is the only reliable source. Cocoa reports both in
// points, the same unit as Tauri's "logical" pixels, so the result needs no
// scale-factor conversion.
fn menu_bar_inset(window: &tauri::WebviewWindow) -> f64 {
    let Ok(handle) = window.ns_window() else {
        return 0.0;
    };
    unsafe {
        let ns_window: &NSWindow = &*(handle as *const NSWindow);
        let Some(screen) = ns_window.screen() else {
            return 0.0;
        };
        let frame = screen.frame();
        let visible = screen.visibleFrame();
        (frame.size.height - (visible.origin.y + visible.size.height)).max(0.0)
    }
}

#[derive(Clone, Copy)]
enum ScreenEdge {
    Top,
    Left,
    Right,
}

// Slides the window to one screen edge along a single axis, leaving the other
// axis (and the size) exactly where they were. Top also tucks it under the
// menu bar.
fn move_window_to_edge(window: &tauri::WebviewWindow, edge: ScreenEdge) -> Result<(), String> {
    let scale_factor = window.scale_factor().map_err(|err| err.to_string())?;
    let monitor = window
        .current_monitor()
        .map_err(|err| err.to_string())?
        .ok_or_else(|| "no monitor available".to_string())?;
    let monitor_pos = monitor.position().to_logical::<f64>(scale_factor);
    let monitor_size = monitor.size().to_logical::<f64>(scale_factor);
    let cur_pos = window
        .outer_position()
        .map_err(|err| err.to_string())?
        .to_logical::<f64>(scale_factor);
    let cur_size = window
        .outer_size()
        .map_err(|err| err.to_string())?
        .to_logical::<f64>(scale_factor);
    let (x, y) = match edge {
        ScreenEdge::Top => (cur_pos.x, monitor_pos.y + menu_bar_inset(window)),
        ScreenEdge::Left => (monitor_pos.x, cur_pos.y),
        ScreenEdge::Right => (
            monitor_pos.x + (monitor_size.width - cur_size.width).max(0.0),
            cur_pos.y,
        ),
    };
    window
        .set_position(tauri::LogicalPosition::new(x, y))
        .map_err(|err| err.to_string())
}

#[tauri::command]
fn move_window_top(window: tauri::WebviewWindow) -> Result<(), String> {
    move_window_to_edge(&window, ScreenEdge::Top)
}

#[tauri::command]
fn move_window_top_left(window: tauri::WebviewWindow) -> Result<(), String> {
    move_window_to_edge(&window, ScreenEdge::Left)
}

#[tauri::command]
fn move_window_top_right(window: tauri::WebviewWindow) -> Result<(), String> {
    move_window_to_edge(&window, ScreenEdge::Right)
}

fn emit_native_menu_action(app: &tauri::AppHandle, id: &str) {
    if !id.starts_with(NATIVE_MENU_PREFIX) {
        return;
    }
    let rest = &id[NATIVE_MENU_PREFIX.len()..];
    let payload = if let Some(action) = rest.strip_prefix("action:") {
        NativeMenuActionPayload {
            action: action.to_string(),
            mode: None,
            agent: None,
            theme: None,
        }
    } else if let Some(agent) = rest.strip_prefix("add:") {
        NativeMenuActionPayload {
            action: "agent".to_string(),
            mode: Some("add".to_string()),
            agent: Some(decode_menu_component(agent)),
            theme: None,
        }
    } else if let Some(agent) = rest.strip_prefix("remove:") {
        NativeMenuActionPayload {
            action: "agent".to_string(),
            mode: Some("remove".to_string()),
            agent: Some(decode_menu_component(agent)),
            theme: None,
        }
    } else if let Some(theme) = rest.strip_prefix("theme:") {
        NativeMenuActionPayload {
            action: "theme".to_string(),
            mode: None,
            agent: None,
            theme: Some(theme.to_string()),
        }
    } else if let Some(mode) = rest.strip_prefix("textSize:") {
        NativeMenuActionPayload {
            action: "textSize".to_string(),
            mode: Some(mode.to_string()),
            agent: None,
            theme: None,
        }
    } else if let Some(session) = rest.strip_prefix("session:") {
        if session.starts_with("section:") {
            return;
        }
        NativeMenuActionPayload {
            action: "switchSession".to_string(),
            mode: Some(session.to_string()),
            agent: None,
            theme: None,
        }
    } else if let Some(gitfile) = rest.strip_prefix("gitfile:") {
        if gitfile.starts_with("section:") {
            return;
        }
        NativeMenuActionPayload {
            action: "gitChange".to_string(),
            mode: Some(gitfile.to_string()),
            agent: None,
            theme: None,
        }
    } else {
        return;
    };

    let Ok(json) = serde_json::to_string(&payload) else {
        return;
    };
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.eval(&format!(
            "window.dispatchEvent(new CustomEvent('native-menu-action', {{ detail: {} }}));",
            json
        ));
    }
}

// CARGO_MANIFEST_DIR is set automatically by Cargo for every build, no script
// or shell needs to export anything. It points at tauri_app/src-tauri; the
// repo root is two directories up. The installed .app is a standalone copy
// launched from the Dock/Finder, with no reliable runtime signal for where
// its source repo lives, so the path is fixed at compile time instead of
// guessed at launch time.
const CARGO_MANIFEST_DIR: &str = env!("CARGO_MANIFEST_DIR");

fn find_repo_root() -> Option<String> {
    let repo_root = Path::new(CARGO_MANIFEST_DIR).parent()?.parent()?;
    if repo_root.join("bin/agent-index").exists() {
        Some(repo_root.to_string_lossy().to_string())
    } else {
        None
    }
}

fn show_hub_error(window: &tauri::WebviewWindow, message: &str) {
    let escaped = message.replace('\\', "\\\\").replace('\'', "\\'");
    // No background: the window is transparent and there is no Python/CSS to
    // pull a page color from at this point anyway. The text-shadow keeps the
    // message legible over whatever shows through (the vibrancy layer, or the
    // desktop on the rare frame it drops out).
    let _ = window.eval(&format!(
        "document.body.style.cssText='background:transparent;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,0.9);padding:60px 40px;font:18px -apple-system,sans-serif';document.body.textContent='{}';",
        escaped
    ));
    let _ = window.show();
}

fn login_shell_path() -> Result<String, String> {
    let mut child = Command::new("/bin/zsh")
        .args(["-lic", "print -r -- $PATH"])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|err| format!("Failed to read shell PATH: {err}"))?;
    if !wait_for_child_success(&mut child, Duration::from_secs(5)) {
        return Err("Failed to read shell PATH.".into());
    }
    let mut stdout = String::new();
    let Some(mut pipe) = child.stdout.take() else {
        return Err("Failed to read shell PATH.".into());
    };
    if pipe.read_to_string(&mut stdout).is_err() {
        return Err("Failed to read shell PATH.".into());
    }
    let path = stdout.trim();
    if path.is_empty() || path.contains('\n') {
        return Err("Failed to read shell PATH.".into());
    }
    Ok(path.to_string())
}

fn configured_hub_port() -> u16 {
    std::env::var("AGENT_INDEX_HUB_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .filter(|port| *port > 0)
        .unwrap_or(8788)
}

fn hub_ready(port: u16, use_https: bool) -> bool {
    let scheme = if use_https { "https" } else { "http" };
    let url = format!("{}://127.0.0.1:{}/hub.webmanifest", scheme, port);
    let mut args = vec!["-s", "--max-time", "1", url.as_str()];
    if use_https {
        args.insert(0, "-k");
    }
    let Ok(output) = Command::new("/usr/bin/curl").args(&args).output() else {
        return false;
    };
    if !output.status.success() {
        return false;
    }
    let body = String::from_utf8_lossy(&output.stdout);
    body.contains("\"name\"") && body.contains("Agent Window")
}

fn wait_for_child_success(child: &mut Child, timeout: Duration) -> bool {
    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return status.success(),
            Ok(None) => {
                if start.elapsed() >= timeout {
                    let _ = child.kill();
                    return false;
                }
                thread::sleep(Duration::from_millis(50));
            }
            Err(_) => return false,
        }
    }
}

// A soft dark veil over the vibrancy in dark mode so the window reads as
// tinted glass; in light mode the glass stays fully clear (no tint). Follows
// the effective macOS appearance -- window.theme() tracks the OS, since the
// app never calls set_theme().
fn glass_tint(window: &tauri::WebviewWindow) -> Option<(u8, u8, u8, u8)> {
    match window.theme() {
        Ok(tauri::Theme::Light) => None,
        _ => Some((0, 0, 0, 97)),
    }
}

fn apply_app_vibrancy(window: &tauri::WebviewWindow) {
    // apply_liquid_glass()/apply_vibrancy() both unconditionally add a new
    // effect view on every call rather than replacing an existing one, so a
    // repeated call (e.g. on refocus) stacks another translucent layer on
    // top instead of refreshing the material in place. Clearing first makes
    // reapplication idempotent; without this the window visibly whitens out
    // a little more each time it regains focus.
    let _ = clear_liquid_glass(window);
    let _ = clear_vibrancy(window);
    if let Err(err) = apply_liquid_glass(
        window,
        NSGlassEffectViewStyle::Clear,
        glass_tint(window),
        Some(26.0),
    ) {
        eprintln!("[app] liquid glass apply failed: {}", err);
        if let Err(err) = apply_vibrancy(
            window,
            NSVisualEffectMaterial::HudWindow,
            Some(NSVisualEffectState::Active),
            Some(18.0),
        ) {
            eprintln!("[app] vibrancy apply failed: {}", err);
        }
    }
}

fn center_traffic_lights(window: &tauri::WebviewWindow) {
    unsafe {
        let ns_window = match window.ns_window() {
            Ok(handle) => handle as *const objc2::runtime::AnyObject,
            Err(err) => {
                eprintln!("[app] traffic lights unavailable: {}", err);
                return;
            }
        };
        let ns_window_obj: &NSWindow = &*(ns_window as *const _);
        let Some(close) = ns_window_obj.standardWindowButton(NSWindowButton::CloseButton) else {
            return;
        };
        let Some(miniaturize) =
            ns_window_obj.standardWindowButton(NSWindowButton::MiniaturizeButton)
        else {
            return;
        };
        let zoom = ns_window_obj.standardWindowButton(NSWindowButton::ZoomButton);

        let Some(title_bar_view) = close.superview().and_then(|view| view.superview()) else {
            return;
        };

        let close_rect = NSView::frame(&close);
        let spacing = NSView::frame(&miniaturize).origin.x - close_rect.origin.x;
        let button_count = if zoom.is_some() { 3.0 } else { 2.0 };
        let cluster_width = close_rect.size.width + (spacing * (button_count - 1.0));
        let target_x = ((ns_window_obj.frame().size.width - cluster_width) / 2.0).round();
        let title_bar_height = 26.0;

        let mut title_bar_rect = NSView::frame(&title_bar_view);
        title_bar_rect.size.height = title_bar_height;
        title_bar_rect.origin.y = ns_window_obj.frame().size.height - title_bar_height;
        title_bar_view.setFrame(title_bar_rect);

        let mut buttons = vec![close, miniaturize];
        if let Some(zoom) = zoom {
            buttons.push(zoom);
        }
        for (index, button) in buttons.into_iter().enumerate() {
            let mut rect = NSView::frame(&button);
            rect.origin.x = target_x + (index as f64 * spacing);
            rect.origin.y = ((title_bar_height - rect.size.height) / 2.0).round();
            button.setFrameOrigin(rect.origin);
        }
    }
}

fn reveal_main_window(app: &tauri::AppHandle) {
    let _ = app.show();
    let Some(window) = app.get_webview_window("main") else {
        return;
    };
    if matches!(window.is_minimized(), Ok(true)) {
        let _ = window.unminimize();
    }
    let _ = window.show();
    let _ = window.set_focus();
}

fn main() {
    if let Err(err) = system_app_icons() {
        panic!("could not load required macOS app icons: {}", err);
    }
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            open_external_url,
            show_chat_header_menu,
            show_appearance_menu,
            reset_window_geometry,
            compact_window_geometry,
            resize_window_from_edge,
            move_window_top,
            move_window_top_left,
            move_window_top_right,
            set_always_on_top,
            set_window_height,
            set_fit_height_min,
            show_session_switcher_menu,
            show_git_changes_menu,
            show_file_context_menu,
            show_session_context_menu
        ])
        .on_menu_event(|app, event| {
            emit_native_menu_action(app, event.id().as_ref());
        })
        .setup(move |app| {
            let window = WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title("Agent Window")
            .inner_size(DEFAULT_WINDOW_SIZE, DEFAULT_WINDOW_SIZE)
            .min_inner_size(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
            .decorations(true)
            .hidden_title(true)
            .title_bar_style(tauri::TitleBarStyle::Overlay)
            .transparent(true)
            .visible(false)
            .devtools(true)
            .initialization_script(INJECT_JS)
            .initialization_script_for_all_frames(INJECT_JS)
            .disable_drag_drop_handler()
            .build()?;

            apply_app_vibrancy(&window);
            center_traffic_lights(&window);
            let traffic_window = window.clone();
            window.on_window_event(move |event| {
                if let tauri::WindowEvent::Focused(true) = event {
                    // The NSVisualEffectView backing occasionally drops out from
                    // under the transparent window during a heavy WebView
                    // repaint (large attachment thumbnails have triggered it),
                    // leaving the desktop showing through. Reapplying on focus
                    // self-heals it without requiring a full app restart.
                    //
                    // Deliberately NOT reapplying on WindowEvent::ThemeChanged:
                    // tried that once as a fix for a glass-turns-white bug on
                    // OS theme change, and it did not fix it -- the bug was
                    // already present in the build before this branch existed,
                    // so the real cause is elsewhere. Left as a known-tried,
                    // ineffective idea rather than silently dropped.
                    apply_app_vibrancy(&traffic_window);
                }
                if matches!(
                    event,
                    tauri::WindowEvent::Resized(_)
                        | tauri::WindowEvent::Moved(_)
                        | tauri::WindowEvent::Focused(_)
                        | tauri::WindowEvent::ScaleFactorChanged { .. }
                ) {
                    center_traffic_lights(&traffic_window);
                } else if let tauri::WindowEvent::ThemeChanged(_) = event {
                    // The glass tint follows the OS appearance, so rebuild it.
                    apply_app_vibrancy(&traffic_window);
                    let w = traffic_window.clone();
                    std::thread::spawn(move || {
                        // FIXME: This 500ms delay is unoptimized.
                        // It is a workaround to wait for macOS theme transition animations
                        // and layout passes to complete before overriding button positions.
                        std::thread::sleep(std::time::Duration::from_millis(500));
                        let value = w.clone();
                        let _ = w.app_handle().run_on_main_thread(move || {
                            center_traffic_lights(&value);
                        });
                    });
                } else if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = traffic_window.hide();
                    let _ = traffic_window.app_handle().hide();
                }
            });

            let repo_root = find_repo_root().unwrap_or_default();
            if repo_root.is_empty() {
                show_hub_error(&window, "Could not find the Agent Window repo.");
                return Ok(());
            }
            eprintln!("[app] repo = {}", repo_root);

            let hub_port = configured_hub_port();
            let path = match login_shell_path() {
                Ok(value) => value,
                Err(message) => {
                    show_hub_error(&window, &message);
                    return Ok(());
                }
            };
            let home = std::env::var("HOME").unwrap_or_default();
            let cert_dir = std::env::var("AGENT_WINDOW_CERTS_DIR")
                .unwrap_or_else(|_| format!("{}/.agent-window/state/certs", home));
            let cert_file = format!("{}/cert.pem", cert_dir);
            let key_file = format!("{}/key.pem", cert_dir);
            let has_certs = Path::new(&cert_file).exists() && Path::new(&key_file).exists();
            let state_dir = std::env::var("AGENT_WINDOW_STATE_DIR")
                .unwrap_or_else(|_| format!("{}/.agent-window/state", home));
            let pwa_enabled_file = format!("{}/pwa/enabled", state_dir);
            let use_https = Path::new(&pwa_enabled_file).exists();
            if use_https && !has_certs {
                show_hub_error(
                    &window,
                    "Local HTTPS certificates are missing. Start the HTTP app first, then run ./setup/pwa/enable.",
                );
                return Ok(());
            }

            let hub_already_up = hub_ready(hub_port, use_https);
            let mut spawned_hub: Option<Child> = None;
            if !hub_already_up {
                let mut cmd = Command::new(format!("{}/bin/agent-index", repo_root));
                cmd.args(["--hub-port", &hub_port.to_string()])
                    .current_dir(&repo_root)
                    .env("PATH", &path)
                    .env("AGENT_INDEX_HUB_PORT", hub_port.to_string())
                    .env("PYTHONPATH", repo_root.clone());
                if use_https {
                    cmd.env("AGENT_WINDOW_CERT_FILE", &cert_file)
                        .env("AGENT_WINDOW_KEY_FILE", &key_file);
                }
                match cmd.spawn() {
                    Ok(c) => {
                        eprintln!("[app] Hub spawned pid={}", c.id());
                        spawned_hub = Some(c);
                    }
                    Err(e) => {
                        eprintln!("[app] Hub spawn failed: {}", e);
                        show_hub_error(&window, &format!("Failed to start Hub: {}", e));
                        return Ok(());
                    }
                }
            } else {
                eprintln!("[app] Hub already up");
            }

            let app_handle = app.handle().clone();
            thread::spawn(move || {
                let show_error = |message: String| {
                    if let Some(w) = app_handle.get_webview_window("main") {
                        show_hub_error(&w, &message);
                    }
                };
                if let Some(mut child) = spawned_hub {
                    if !wait_for_child_success(&mut child, Duration::from_secs(8)) {
                        eprintln!("[app] Hub failed to start");
                        show_error(format!("Hub failed to start on port {}", hub_port));
                        return;
                    }
                }
                let scheme = if use_https { "https" } else { "http" };
                let hub_url = format!("{}://127.0.0.1:{}/?tauri=1", scheme, hub_port);
                eprintln!("[app] Navigating to {}", hub_url);
                if let Some(w) = app_handle.get_webview_window("main") {
                    let url: tauri::Url = hub_url.parse().unwrap();
                    let _ = w.navigate(url);
                    let _ = w.show();
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Agent Window")
        .run(|app, event| {
            if let tauri::RunEvent::Reopen {
                has_visible_windows: false,
                ..
            } = event
            {
                reveal_main_window(app);
            }
        });
}
