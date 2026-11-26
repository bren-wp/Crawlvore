fn main() {
    for key in ["CRAWLVORA_WORKER_SIZE", "CRAWLVORA_WORKER_SHA256"] {
        println!("cargo:rerun-if-env-changed={key}");
    }
    tauri_build::build()
}
