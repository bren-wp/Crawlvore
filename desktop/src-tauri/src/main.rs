#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    io::{self, BufRead, BufReader},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{Mutex, mpsc},
    thread,
    time::{Duration, Instant},
};
use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, Url};
use tauri::webview::{NewWindowResponse, PageLoadEvent};

#[cfg(all(feature = "portable", not(windows)))]
compile_error!("The embedded portable worker is built for Windows only.");

struct Worker {
    child: Child,
    #[cfg(all(feature = "portable", windows))]
    _extraction: tempfile::TempDir,
}

impl Drop for Worker {
    fn drop(&mut self) {
        // EOF on the inherited pipe requests orderly shutdown, including the job queue.
        drop(self.child.stdin.take());
        let deadline = Instant::now() + Duration::from_secs(10);
        while Instant::now() < deadline {
            if matches!(self.child.try_wait(), Ok(Some(_))) { return; }
            thread::sleep(Duration::from_millis(100));
        }
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn invalid(message: &str) -> io::Error { io::Error::other(message) }

fn ready_url(line: &str) -> Result<Url, io::Error> {
    let raw = line.trim().strip_prefix("CRAWLVORA_READY ").ok_or_else(|| invalid("Invalid worker handshake"))?;
    let url = Url::parse(raw).map_err(|_| invalid("Invalid worker address"))?;
    let secret = url.path().strip_prefix("/session/").unwrap_or("");
    if url.scheme() != "http" || url.host_str() != Some("127.0.0.1") || url.port().is_none()
        || !url.username().is_empty() || url.password().is_some()
        || url.query().is_some() || url.fragment().is_some()
        || secret.len() != 64 || !secret.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(invalid("Rejected worker address"));
    }
    Ok(url)
}

#[cfg(not(feature = "portable"))]
fn worker_path() -> io::Result<PathBuf> {
    let exe = std::env::current_exe()?;
    let dir = exe.parent().ok_or_else(|| invalid("Missing executable directory"))?;
    let name = if cfg!(windows) { "CrawlvoraWorker.exe" } else { "CrawlvoraWorker" };
    Ok(dir.join("worker").join(name))
}

fn spawn_worker(data: &Path) -> Result<(Worker, Url), io::Error> {
    #[cfg(not(feature = "portable"))]
    let binary = worker_path()?;
    #[cfg(all(feature = "portable", windows))]
    let (binary, extraction) = {
        use std::io::Write;
        // A unique, exclusively created directory: never execute a reused extracted binary.
        let directory = tempfile::Builder::new().prefix("crawlvora-worker-").tempdir()?;
        let path = directory.path().join("CrawlvoraWorker.exe");
        let mut file = std::fs::OpenOptions::new().create_new(true).write(true).open(&path)?;
        file.write_all(include_bytes!(env!("CRAWLVORA_EMBEDDED_WORKER")))?;
        file.sync_all()?;
        drop(file);
        (path, directory)
    };
    if !binary.is_file() { return Err(invalid("Crawlvora worker is missing. Reinstall the application.")); }
    std::fs::create_dir_all(data)?;
    let mut command = Command::new(binary);
    command.args(["--worker", "--port", "0", "--data-dir"]).arg(data)
        .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    let mut worker = Worker {
        child: command.spawn()?,
        #[cfg(all(feature = "portable", windows))]
        _extraction: extraction,
    };
    let stdout = worker.child.stdout.take().ok_or_else(|| invalid("Missing worker pipe"))?;
    let (tx, rx) = mpsc::sync_channel(1);
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            if line.starts_with("CRAWLVORA_READY ") {
                let _ = tx.try_send(line);
            }
        }
    });
    let line = rx.recv_timeout(Duration::from_secs(120)).map_err(|_| invalid("Worker startup timed out"))?;
    let url = ready_url(&line)?;
    Ok((worker, url))
}

fn main() {
    let smoke = std::env::args().any(|arg| arg == "--native-smoke");
    let application = tauri::Builder::default()
        .manage(Mutex::new(None::<Worker>))
        .setup(move |app| {
            let data = if smoke {
                std::env::temp_dir().join(format!("crawlvora-native-smoke-{}", std::process::id()))
            } else {
                app.path().local_data_dir()?.join("Crawlvora")
            };
            let (worker, url) = spawn_worker(&data)?;
            let port = url.port();
            *app.state::<Mutex<Option<Worker>>>().lock().map_err(|_| invalid("Worker state unavailable"))? = Some(worker);
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .title("Crawlvora")
                .inner_size(1440.0, 900.0)
                .min_inner_size(900.0, 620.0)
                .on_navigation(move |url| url.scheme() == "http" && url.host_str() == Some("127.0.0.1") && url.port() == port)
                .on_new_window(|_, _| NewWindowResponse::Deny)
                .on_page_load(move |window, payload| {
                    if smoke && payload.event() == PageLoadEvent::Finished && payload.url().path() == "/" {
                        window.app_handle().exit(0);
                    }
                })
                .build()?;
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

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_accepts_loopback_session() {
        let token = "a".repeat(64);
        assert!(ready_url(&format!("CRAWLVORA_READY http://127.0.0.1:49152/session/{token}")).is_ok());
        for host in ["https://127.0.0.1:49152", "http://localhost:49152", "http://example.com:49152", "http://127.0.0.1"] {
            assert!(ready_url(&format!("CRAWLVORA_READY {host}/session/{token}")).is_err());
        }
        assert!(ready_url("CRAWLVORA_READY http://127.0.0.1:49152/session/bad").is_err());
    }
}
