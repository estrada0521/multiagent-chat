fn main() {
    tauri_build::try_build(
        tauri_build::Attributes::new().app_manifest(
            tauri_build::AppManifest::new().commands(&["show_chat_header_menu"]),
        ),
    )
    .expect("failed to run Tauri build script")
}
