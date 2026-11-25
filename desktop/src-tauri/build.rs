fn main() {
    println!("cargo:rerun-if-env-changed=CRAWLVORA_EMBEDDED_WORKER");
    if let Some(path) = std::env::var_os("CRAWLVORA_EMBEDDED_WORKER") {
        println!("cargo:rerun-if-changed={}", std::path::Path::new(&path).display());
    }
    tauri_build::build()
}
