//! Owns the worker process and embedded portable payload.
use std::{
    io::{self, BufRead, BufReader},
    path::Path,
    process::{Child, Command, Stdio},
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};
use tauri::Url;
use crate::security_policy::{invalid, ready_url};

pub(crate) struct Worker {
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

#[cfg(not(feature = "portable"))]
fn worker_path() -> io::Result<std::path::PathBuf> {
    let exe = std::env::current_exe()?;
    let dir = exe.parent().ok_or_else(|| invalid("Missing executable directory"))?;
    let name = if cfg!(windows) { "CrawlvoraWorker.exe" } else { "CrawlvoraWorker" };
    Ok(dir.join("worker").join(name))
}

pub(crate) fn spawn_worker(data: &Path, primary: bool, smoke: bool) -> Result<(Worker, Url, mpsc::Receiver<String>), io::Error> {
    #[cfg(not(feature = "portable"))]
    let binary = worker_path()?;
    #[cfg(all(feature = "portable", windows))]
    let (binary, extraction) = crate::portable_payload::extract()?;
    if !binary.is_file() { return Err(invalid("Crawlvora worker is missing. Reinstall the application.")); }
    std::fs::create_dir_all(data)?;
    let mut command = Command::new(binary);
    command.args(["--worker", "--port", "0", "--data-dir"]).arg(data)
        .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
    if primary { command.arg("--primary-workspace"); }
    if smoke {
        command.env("CRAWLVORA_NATIVE_SMOKE", "1");
        for key in ["CRAWLVORA_REGISTRY_PROVISION", "SUDREG_CLIENT_ID", "SUDREG_CLIENT_SECRET"] {
            command.env_remove(key);
        }
    }
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
    let (tx, rx) = mpsc::sync_channel(2);
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            if line.starts_with("CRAWLVORA_READY ") || line == "CRAWLVORA_UI_READY" {
                let _ = tx.try_send(line);
            }
        }
    });
    let line = rx.recv_timeout(Duration::from_secs(900)).map_err(|_| invalid("Worker startup timed out"))?;
    let url = ready_url(&line)?;
    Ok((worker, url, rx))
}
