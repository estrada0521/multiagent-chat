use tauri::Manager;
use tauri::menu::{MenuBuilder, NativeIcon, SubmenuBuilder};
use tauri::webview::Color as WebviewColor;
use tauri::webview::WebviewWindowBuilder;
use std::collections::HashMap;
use std::process::{Command, Child};
use std::sync::Mutex;
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};
use std::thread;
use objc2::ClassType;
use objc2_app_kit::{NSScreen, NSWorkspace};
use objc2_foundation::NSURL;
use image::GenericImageView;

const DARK_BG: &str = "rgb(0,0,0)";

#[cfg(target_os = "macos")]
use window_vibrancy::{
    apply_liquid_glass, apply_vibrancy, NSGlassEffectViewStyle, NSVisualEffectMaterial,
    NSVisualEffectState,
};

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct ChatHeaderMenuPayload {
    x: f64,
    y: f64,
    session_active: bool,
    add_agents: Vec<String>,
    remove_agents: Vec<String>,
    /// Raw RGBA bytes (22×22 = 1936 bytes) per agent base name
    #[serde(default)]
    agent_icons: HashMap<String, Vec<u8>>,
}

/// Replicate JS: name.toLowerCase().replace(/-\d+$/, "")
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
}

#[allow(dead_code)]
struct HubProcess(Mutex<Option<Child>>);

const INJECT_JS: &str = include_str!("inject.js");
const BUNDLED_REPO_RESOURCE_DIR: &str = "multiagent-chat-repo";
const NATIVE_MENU_PREFIX: &str = "multiagent-chat:";

#[derive(serde::Serialize, Clone)]
struct AdaptiveTheme {
    mode: String, // "light-fg" or "dark-fg"
    luma: f32,
}

struct WallpaperCache {
    url: String,
    image: image::DynamicImage,
}

static WALLPAPER_CACHE: Mutex<Option<WallpaperCache>> = Mutex::new(None);

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

#[tauri::command]
fn show_chat_header_menu(
    window: tauri::WebviewWindow,
    app: tauri::AppHandle,
    payload: ChatHeaderMenuPayload,
) -> Result<(), String> {
    let add_enabled = payload.session_active && !payload.add_agents.is_empty();
    let remove_enabled = payload.session_active && payload.remove_agents.len() > 1;

    // Build Add Agent submenu with per-agent icons when available
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

    // Build Remove Agent submenu with per-agent icons when available
    let mut remove_builder = SubmenuBuilder::with_id(
        &app,
        format!("{}submenu:removeAgent", NATIVE_MENU_PREFIX),
        "Remove Agent",
    )
    .submenu_native_icon(NativeIcon::Remove)
    .enabled(remove_enabled);
    for agent in &payload.remove_agents {
        let id = format!("{}remove:{}", NATIVE_MENU_PREFIX, encode_menu_component(agent));
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

    // Main menu — use Template (monochrome) NativeIcons throughout
    let menu = MenuBuilder::new(&app)
        .native_icon(
            format!("{}action:reloadChat", NATIVE_MENU_PREFIX),
            "Reload",
            NativeIcon::Refresh,      // RefreshTemplate ✓
        )
        .native_icon(
            format!("{}action:openTerminal", NATIVE_MENU_PREFIX),
            "Terminal",
            NativeIcon::Path,         // PathTemplate "/" ✓ (was Computer — colored)
        )
        .native_icon(
            format!("{}action:openFinder", NATIVE_MENU_PREFIX),
            "Finder",
            NativeIcon::Home,         // HomeTemplate ✓ (was Folder — colored)
        )
        .native_icon(
            format!("{}action:openCameraMode", NATIVE_MENU_PREFIX),
            "Camera",
            NativeIcon::QuickLook,    // QuickLookTemplate ✓
        )
        .native_icon(
            format!("{}action:syncStatus", NATIVE_MENU_PREFIX),
            "Sync Status",
            NativeIcon::Bookmarks,    // BookmarksTemplate ✓ (was Info — colored)
        )
        .separator()
        .item(&add_submenu)
        .item(&remove_submenu)
        .build()
        .map_err(|err| err.to_string())?;

    window
        .popup_menu_at(&menu, tauri::LogicalPosition::new(payload.x, payload.y))
        .map_err(|err| err.to_string())
}

fn relative_luma(r: f32, g: f32, b: f32) -> f32 {
    let lin = |c: f32| -> f32 {
        if c <= 0.04045 { c / 12.92 } else { ((c + 0.055) / 1.055).powf(2.4) }
    };
    0.2126 * lin(r / 255.0) + 0.7152 * lin(g / 255.0) + 0.0722 * lin(b / 255.0)
}

#[tauri::command]
fn get_adaptive_theme(
    window: tauri::WebviewWindow,
    prev_mode: String,
) -> Result<AdaptiveTheme, String> {
    println!("[AdaptiveTheme] Command called with prev_mode: '{}'", prev_mode);
    #[cfg(target_os = "macos")]
    {
        let screen = unsafe {
            let ns_window = window.ns_window().map_err(|e| e.to_string())? as *const objc2::runtime::AnyObject;
            let ns_window_obj: &objc2_app_kit::NSWindow = &*(ns_window as *const _);
            ns_window_obj.screen()
        };

        if screen.is_none() {
            return Err("Cannot find screen for window".into());
        }
        let screen = screen.unwrap();
        
        let ws = NSWorkspace::sharedWorkspace();
        let url_ptr = ws.desktopImageURLForScreen(&screen);
        if url_ptr.is_none() {
            println!("[AdaptiveTheme] Error: Cannot get desktop wallpaper URL");
            return Err("Cannot get desktop wallpaper URL".into());
        }
        let url = url_ptr.unwrap();
        let path_str = url.path().ok_or("Invalid path")?.to_string();

        let mut cache = WALLPAPER_CACHE.lock().map_err(|e| e.to_string())?;
        if cache.as_ref().map(|c| c.url != path_str).unwrap_or(true) {
            println!("[AdaptiveTheme] Loading new wallpaper: {}", path_str);
            let img = image::open(&path_str).map_err(|e| format!("Failed to open wallpaper: {}", e))?;
            *cache = Some(WallpaperCache { url: path_str, image: img });
        }
        let cache_ref = cache.as_ref().unwrap();
        let img = &cache_ref.image;

        // Window coordinates in screen space
        let pos = window.outer_position().map_err(|e| e.to_string())?;
        let size = window.inner_size().map_err(|e| e.to_string())?;
        let screen_frame = screen.frame(); // Y is from bottom in Cocoa

        // Sample area: Sidebar (left 260px)
        let sidebar_width = 260.0;
        
        // Convert screen-global coordinates (Tauri, Y-down from primary top)
        // to screen-local coordinates.
        let local_x = pos.x as f64 - screen_frame.origin.x;
        // In Cocoa, Y grows UP from bottom. In Tauri, Y grows DOWN from top.
        // For the primary screen, 0 is the top. 
        // We'll use absolute mapping based on the screen's frame size.
        let local_y = pos.y as f64 - screen_frame.origin.y; // Correct relative Y

        let sample_x = local_x;
        let sample_y = local_y; 
        let sample_w = sidebar_width;
        let sample_h = size.height as f64;

        // Map screen coordinates to image pixels (Assuming "Fill" mode)
        let (img_w, img_h) = img.dimensions();
        let scale_w = img_w as f64 / screen_frame.size.width;
        let scale_h = img_h as f64 / screen_frame.size.height;
        let scale = scale_w.max(scale_h);

        let offset_x = (img_w as f64 - screen_frame.size.width * scale) / 2.0;
        let offset_y = (img_h as f64 - screen_frame.size.height * scale) / 2.0;

        let img_sample_x = (sample_x * scale + offset_x).clamp(0.0, img_w as f64 - 1.0) as u32;
        let img_sample_y = (sample_y * scale + offset_y).clamp(0.0, img_h as f64 - 1.0) as u32;
        
        println!("[AdaptiveTheme] WinPos:({:?}), WinSize:({:?}), ScreenOrigin:({},{}), ImgSample:({},{})", 
            pos, size, screen_frame.origin.x, screen_frame.origin.y, img_sample_x, img_sample_y);
        let img_sample_w = (sample_w * scale).clamp(1.0, img_w as f64 - img_sample_x as f64) as u32;
        let img_sample_h = (sample_h * scale).clamp(1.0, img_h as f64 - img_sample_y as f64) as u32;

        // Calculate average Luma
        let mut sum_luma = 0.0;
        let mut count = 0;
        let step = (img_sample_w / 16).max(1); // Sample a grid to be fast
        for x in (img_sample_x..img_sample_x + img_sample_w).step_by(step as usize) {
            for y in (img_sample_y..img_sample_y + img_sample_h).step_by(step as usize) {
                let p = img.get_pixel(x, y);
                sum_luma += relative_luma(p[0] as f32, p[1] as f32, p[2] as f32);
                count += 1;
            }
        }
        let avg_luma = if count > 0 { sum_luma / count as f32 } else { 0.5 };

        let mode = match prev_mode.as_str() {
            "dark-fg" if avg_luma < 0.45 => "light-fg".to_string(),
            "light-fg" if avg_luma > 0.60 => "dark-fg".to_string(), // Slightly lowered threshold
            "" if avg_luma > 0.53 => "dark-fg".to_string(),
            "" => "light-fg".to_string(),
            _ => prev_mode,
        };

        println!("[AdaptiveTheme] Luma: {:.3}, Mode: {}, Screen Origin: ({}, {})", avg_luma, mode, screen_frame.origin.x, screen_frame.origin.y);

        Ok(AdaptiveTheme { mode, luma: avg_luma })
    }
    #[cfg(not(target_os = "macos"))]
    {
        Ok(AdaptiveTheme { mode: "light-fg".into(), luma: 0.0 })
    }
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
        }
    } else if let Some(agent) = rest.strip_prefix("add:") {
        NativeMenuActionPayload {
            action: "agent".to_string(),
            mode: Some("add".to_string()),
            agent: Some(decode_menu_component(agent)),
        }
    } else if let Some(agent) = rest.strip_prefix("remove:") {
        NativeMenuActionPayload {
            action: "agent".to_string(),
            mode: Some("remove".to_string()),
            agent: Some(decode_menu_component(agent)),
        }
    } else {
        return;
    };

    let Ok(json) = serde_json::to_string(&payload) else {
        return;
    };
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.eval(&format!(
            "window.dispatchEvent(new CustomEvent('multiagent-native-menu-action', {{ detail: {} }}));",
            json
        ));
    }
}

fn copy_dir_contents(source: &Path, target: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(target)?;
    for entry in std::fs::read_dir(source)? {
        let entry = entry?;
        let source_path = entry.path();
        let file_name = entry.file_name();
        if file_name.to_string_lossy() == ".DS_Store" {
            continue;
        }
        let target_path = target.join(file_name);
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            copy_dir_contents(&source_path, &target_path)?;
        } else if file_type.is_file() {
            if let Some(parent) = target_path.parent() {
                std::fs::create_dir_all(parent)?;
            }
            std::fs::copy(&source_path, &target_path)?;
            if let Ok(permissions) = std::fs::metadata(&source_path).map(|m| m.permissions()) {
                let _ = std::fs::set_permissions(&target_path, permissions);
            }
        }
    }
    Ok(())
}

#[cfg(unix)]
fn make_bin_scripts_executable(repo_root: &Path) {
    use std::os::unix::fs::PermissionsExt;

    let bin_dir = repo_root.join("bin");
    let Ok(entries) = std::fs::read_dir(bin_dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_file() {
            if let Ok(metadata) = std::fs::metadata(&path) {
                let mut permissions = metadata.permissions();
                permissions.set_mode(0o755);
                let _ = std::fs::set_permissions(&path, permissions);
            }
        }
    }
}

#[cfg(not(unix))]
fn make_bin_scripts_executable(_repo_root: &Path) {}

fn sync_bundled_repo(app: &tauri::App) -> Option<PathBuf> {
    let resource_root = app.path().resource_dir().ok()?;
    let source = resource_root.join(BUNDLED_REPO_RESOURCE_DIR);
    if !source.join("bin/agent-index").exists() {
        return None;
    }

    let app_data_dir = app.path().app_data_dir().ok()?;
    let target = app_data_dir.join("multiagent-chat");
    if let Err(err) = copy_dir_contents(&source, &target) {
        eprintln!("[app] bundled repo sync failed: {}", err);
        return None;
    }
    make_bin_scripts_executable(&target);
    if target.join("bin/agent-index").exists() {
        Some(target)
    } else {
        None
    }
}

fn find_repo_root(app: &tauri::App) -> Option<String> {
    for env_key in ["MULTIAGENT_REPO_ROOT", "MULTIAGENT_WORKSPACE"] {
        if let Ok(candidate) = std::env::var(env_key) {
            let path = PathBuf::from(candidate);
            if path.join("bin/agent-index").exists() {
                return Some(path.to_string_lossy().to_string());
            }
        }
    }

    if let Ok(exe) = std::env::current_exe() {
        let mut dir = exe.parent().map(|p| p.to_path_buf());
        for _ in 0..6 {
            if let Some(ref d) = dir {
                if d.join("bin/agent-index").exists() {
                    return Some(d.to_string_lossy().to_string());
                }
                dir = d.parent().map(|p| p.to_path_buf());
            }
        }
    }
    let home = std::env::var("HOME").unwrap_or_default();
    for candidate in &[
        format!("{}/workspace/multiagent-local", home),
        format!("{}/multiagent-chat", home),
    ] {
        if std::path::Path::new(candidate).join("bin/agent-index").exists() {
            return Some(candidate.clone());
        }
    }
    sync_bundled_repo(app).map(|repo| repo.to_string_lossy().to_string())
}

fn wait_for_port(port: u16, timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if TcpStream::connect_timeout(
            &format!("127.0.0.1:{}", port).parse().unwrap(),
            Duration::from_millis(200),
        ).is_ok() {
            return true;
        }
        thread::sleep(Duration::from_millis(300));
    }
    false
}

#[cfg(target_os = "macos")]
fn apply_app_vibrancy(window: &tauri::WebviewWindow) {
    if let Err(err) = apply_liquid_glass(window, NSGlassEffectViewStyle::Clear, None, Some(26.0))
    {
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

#[cfg(not(target_os = "macos"))]
fn apply_app_vibrancy(_window: &tauri::WebviewWindow) {}

fn main() {
    let hub_port: u16 = 8788;

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            show_chat_header_menu,
            get_adaptive_theme,
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
            .title("Multiagent Chat")
            .inner_size(1200.0, 800.0)
            .min_inner_size(400.0, 500.0)
            .decorations(true)
            .hidden_title(true)
            .title_bar_style(tauri::TitleBarStyle::Overlay)
            .traffic_light_position(tauri::LogicalPosition::new(96.0, 18.0))
            .transparent(true)
            .devtools(true)
            .initialization_script(INJECT_JS)
            .initialization_script_for_all_frames(INJECT_JS)
            .build()?;

            apply_app_vibrancy(&window);

            let repo_root = find_repo_root(app).unwrap_or_default();
            if repo_root.is_empty() {
                let _ = window.eval(&format!("document.body.style.cssText='background:{};color:#fff;padding:60px 40px;font:18px -apple-system,sans-serif';document.body.textContent='Could not find multiagent-chat repo.';", DARK_BG));
                return Ok(());
            }
            eprintln!("[app] repo = {}", repo_root);

            let home = std::env::var("HOME").unwrap_or_default();
            let path = format!(
                "/opt/homebrew/bin:/opt/homebrew/sbin:{}/.cargo/bin:{}/.nvm/versions/node/v24.14.0/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                home, home,
            );
            let cert_file = format!("{}/certs/cert.pem", repo_root);
            let key_file = format!("{}/certs/key.pem", repo_root);
            let has_certs = Path::new(&cert_file).exists() && Path::new(&key_file).exists();

            let hub_already_up = TcpStream::connect_timeout(
                &format!("127.0.0.1:{}", hub_port).parse().unwrap(),
                Duration::from_millis(500),
            ).is_ok();

            if !hub_already_up {
                let mut cmd = Command::new(format!("{}/bin/agent-index", repo_root));
                cmd.args(["--hub", "--hub-port", &hub_port.to_string(), "--no-open", "--https"])
                    .current_dir(&repo_root)
                    .env("PATH", &path)
                    .env("PYTHONPATH", format!("{}/lib", repo_root));
                if has_certs {
                    cmd.env("MULTIAGENT_CERT_FILE", &cert_file)
                        .env("MULTIAGENT_KEY_FILE", &key_file);
                }
                match cmd.spawn() {
                    Ok(c) => {
                        eprintln!("[app] Hub spawned pid={}", c.id());
                        app.manage(HubProcess(Mutex::new(Some(c))));
                    }
                    Err(e) => {
                        eprintln!("[app] Hub spawn failed: {}", e);
                        app.manage(HubProcess(Mutex::new(None)));
                    }
                }
            } else {
                eprintln!("[app] Hub already up");
                app.manage(HubProcess(Mutex::new(None)));
            }

            let app_handle = app.handle().clone();
            let hub_url = format!("https://127.0.0.1:{}/?tauri=1", hub_port);
            thread::spawn(move || {
                if !hub_already_up && !wait_for_port(hub_port, Duration::from_secs(15)) {
                    eprintln!("[app] Hub timeout");
                    return;
                }
                if hub_already_up {
                    thread::sleep(Duration::from_millis(600));
                }
                eprintln!("[app] Navigating to {}", hub_url);
                if let Some(w) = app_handle.get_webview_window("main") {
                    let url: tauri::Url = hub_url.parse().unwrap();
                    let _ = w.navigate(url);
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Multiagent Chat");
}
