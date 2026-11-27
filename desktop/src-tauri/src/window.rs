//! Desktop window composition and navigation boundary.
use tauri::{App, Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder};
use tauri::webview::NewWindowResponse;
use crate::security_policy::{allowed_external_url, allowed_worker_navigation};

pub(crate) fn build(app: &App, url: Url, smoke: bool) -> tauri::Result<WebviewWindow> {
    let port = url.port();
    WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
        .title("Crawlvora")
        .inner_size(1120.0, 720.0)
        .min_inner_size(360.0, 300.0)
        .resizable(true)
        .maximized(false)
        .fullscreen(false)
        .decorations(true)
        .prevent_overflow_with_margin(tauri::LogicalSize::new(96.0, 96.0))
        .center()
        .on_navigation(move |url| allowed_worker_navigation(url, port))
        .on_new_window(move |url, _| {
            if !smoke && allowed_external_url(&url) {
                // Same desktop launcher used by the former opener plugin, without its IPC or D-Bus dependencies.
                if open::that_detached(url.as_str()).is_err() {
                    eprintln!("Unable to open external link");
                }
            }
            NewWindowResponse::Deny
        })
        .build()
}
