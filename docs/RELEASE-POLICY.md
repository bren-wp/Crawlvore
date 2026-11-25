# Production release policy

Every production GitHub Release must contain all five assets:

- Portable.exe: standalone Windows Tauri executable with an embedded scraper worker.
- Setup.exe: Windows installer with a native Tauri host and packaged worker.
- Crawlvora-Linux-x86_64.tar.gz: tested native Linux distribution (Ubuntu 24.04 baseline; system WebKitGTK and Chromium runtime libraries are required).
- Crawlvora-source.zip: source from the exact release tag.
- SHA256SUMS.txt: SHA-256 checksums for the other four assets.

The production workflow requires an immutable version tag on main, matching version metadata, committed npm and Cargo locks, a successful quality/security workflow, native builds and smoke tests on Windows and Linux, and a completed four-hour endurance test. It refuses to publish an incomplete asset set. The legacy Windows workflow remains available during migration but does not publish releases.

Before tagging, review the visual differences against the accepted brand reference, complete the live authorized registry/website integration checks, verify upgrade compatibility with the existing database, and review the Python, npm and Rust audit evidence. Credentials are local configuration, never a release asset. Signing certificates and notarization have not been configured; unsigned packages may trigger OS warnings.

The first native release is not approved until all gates have actually passed and the visual and functional parity review is complete.
