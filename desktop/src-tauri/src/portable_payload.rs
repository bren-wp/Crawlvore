//! Verified extraction of the Windows portable worker.
use std::{io, path::PathBuf};
use crate::security_policy::invalid;

pub(crate) fn extract() -> io::Result<(PathBuf, tempfile::TempDir)> {
    use std::io::{Read, Seek, SeekFrom, Write};
    use sha2::{Digest, Sha256};
    // A unique, exclusively created directory: never execute a reused extracted binary.
    let directory = tempfile::Builder::new().prefix("crawlvora-worker-").tempdir()?;
    let path = directory.path().join("CrawlvoraWorker.exe");
    let mut file = std::fs::OpenOptions::new().create_new(true).write(true).open(&path)?;
    // The payload is appended after linking, avoiding giant LLVM constants.
    // Its size and SHA-256 are pinned in the compiled launcher.
    let size: u64 = env!("CRAWLVORA_WORKER_SIZE").parse()
        .map_err(|_| invalid("Invalid embedded worker size"))?;
    let mut source = std::fs::File::open(std::env::current_exe()?)?;
    let length = source.metadata()?.len();
    if size == 0 || length <= size { return Err(invalid("Missing portable payload")); }
    source.seek(SeekFrom::Start(length - size))?;
    let mut digest = Sha256::new();
    let mut remaining = size;
    let mut buffer = vec![0u8; 1024 * 1024];
    while remaining > 0 {
        let count = remaining.min(buffer.len() as u64) as usize;
        source.read_exact(&mut buffer[..count])?;
        digest.update(&buffer[..count]);
        file.write_all(&buffer[..count])?;
        remaining -= count as u64;
    }
    let actual = digest.finalize().iter().map(|b| format!("{b:02x}")).collect::<String>();
    if actual != env!("CRAWLVORA_WORKER_SHA256") {
        return Err(invalid("Portable payload integrity check failed"));
    }
    file.sync_all()?;
    drop(file);
    Ok((path, directory))
}
