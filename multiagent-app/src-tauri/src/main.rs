use tauri::Manager;
use tauri::webview::WebviewWindowBuilder;
use std::process::{Command, Child};
use std::sync::Mutex;
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};
use std::thread;

#[allow(dead_code)]
struct HubProcess(Mutex<Option<Child>>);

const INJECT_JS: &str = include_str!("inject.js");
const BUNDLED_REPO_RESOURCE_DIR: &str = "multiagent-chat-repo";

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
    if let Some(repo) = sync_bundled_repo(app) {
        return Some(repo.to_string_lossy().to_string());
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
    None
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

/// Keep injecting the settings script into the webview.
/// Re-checks every few seconds to handle page navigations.
fn start_inject_loop(app_handle: tauri::AppHandle) {
    let js = INJECT_JS.to_string();
    thread::spawn(move || {
        // Wait for initial page to load
        thread::sleep(Duration::from_millis(2000));
        loop {
            if let Some(w) = app_handle.get_webview_window("main") {
                let _ = w.eval(&js);
            } else {
                break; // Window closed
            }
            thread::sleep(Duration::from_millis(3000));
        }
    });
}

fn main() {
    let hub_port: u16 = 8788;

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
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
            .traffic_light_position(tauri::LogicalPosition::new(18.0, 18.0))
            .transparent(false)
            .build()?;

            let repo_root = find_repo_root(app).unwrap_or_default();
            if repo_root.is_empty() {
                let _ = window.eval("document.body.style.cssText='background:#111;color:#fff;padding:60px 40px;font:18px -apple-system,sans-serif';document.body.textContent='Could not find multiagent-chat repo.';");
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
                start_inject_loop(app_handle);
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Multiagent Chat");
}
