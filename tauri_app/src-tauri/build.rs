fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "open_external_url",
            "show_chat_header_menu",
            "show_appearance_menu",
            "reset_window_geometry",
            "compact_window_geometry",
            "resize_window_from_edge",
            "move_window_top",
            "move_window_top_left",
            "move_window_top_right",
            "move_window_center",
            "set_always_on_top",
            "set_window_height",
            "set_fit_height_min",
            "show_session_switcher_menu",
            "show_git_changes_menu",
            "show_file_context_menu",
            "show_session_context_menu",
        ]),
    ))
    .expect("failed to run Tauri build script")
}
