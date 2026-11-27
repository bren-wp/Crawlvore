#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod security_policy;
mod worker;

use std::{sync::Mutex, thread, time::Duration};
use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri::webview::NewWindowResponse;
use security_policy::{invalid, allowed_external_url};
use worker::{Worker, spawn_worker};

#[cfg(all(feature = "portable", not(windows)))]
compile_error!("The embedded portable worker is built for Windows only.");

fn main() {
    let smoke = std::env::args().any(|arg| arg == "--native-smoke");
    let primary = std::env::args().any(|arg| arg == "--primary-workspace");
    let application = tauri::Builder::default()
        .manage(Mutex::new(None::<Worker>))
        .setup(move |app| {
            let data = if smoke {
                std::env::temp_dir().join(format!("crawlvora-native-smoke-{}", std::process::id()))
            } else {
                app.path().local_data_dir()?.join("Crawlvora")
            };
            let (worker, url, ui_ready) = spawn_worker(&data, primary, smoke)?;
            let port = url.port();
            *app.state::<Mutex<Option<Worker>>>().lock().map_err(|_| invalid("Worker state unavailable"))? = Some(worker);
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .title("Crawlvora")
                .inner_size(1120.0, 720.0)
                .min_inner_size(360.0, 300.0)
                .resizable(true)
                .maximized(false)
                .fullscreen(false)
                .decorations(true)
                .prevent_overflow_with_margin(tauri::LogicalSize::new(96.0, 96.0))
                .center()
                .on_navigation(move |url| url.scheme() == "http" && url.host_str() == Some("127.0.0.1") && url.port() == port)
                .on_new_window(move |url, _| {
                    if !smoke && allowed_external_url(&url) {
                        // Rust-only opener; no JavaScript plugin permissions are exposed.
                        if tauri_plugin_opener::open_url(url.as_str(), None::<&str>).is_err() {
                            eprintln!("Unable to open external link");
                        }
                    }
                    NewWindowResponse::Deny
                })
                .build()?;
            if smoke {
                if window.is_fullscreen()? || window.is_maximized()? {
                    return Err(invalid("Desktop must launch in a normal window").into());
                }
                let handle = app.handle().clone();
                thread::spawn(move || {
                    let result = ui_ready.recv_timeout(Duration::from_secs(90));
                    let ok = matches!(result.as_deref(), Ok("CRAWLVORA_UI_READY"));
                    handle.exit(if ok { 0 } else { 1 });
                });
            }
            Ok(())
        })
        .build(tauri::generate_context!());
    match application {
        Ok(app) => app.run(move |handle, event| {
            if matches!(event, RunEvent::Exit) {
                if let Ok(mut worker) = handle.state::<Mutex<Option<Worker>>>().lock() {
                    drop(worker.take());
                }
                if smoke {
                    let _ = std::fs::remove_dir_all(std::env::temp_dir().join(format!("crawlvora-native-smoke-{}", std::process::id())));
                }
            }
        }),
        Err(err) => { eprintln!("Crawlvora could not start: {err}"); std::process::exit(1); }
    }
}
