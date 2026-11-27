# Croatian desktop release policy

Only HR Full and HR Online are built, for Windows and Linux. Each has installer and portable/archive variants. Full must contain the verified Croatian registry snapshot; Online starts empty in a fresh workspace. Never overwrite an existing workspace. Release checks must include source identity, actual package smoke tests, snapshot counts and checksums, and asset size/digest checks. Raw snapshot 1370 is preserved separately in the private data release. No credentials in distributable packages. Private distribution is not authorization for public redistribution.

Windows Setup is built with NSIS, in Croatian, with a per-user installation and optional desktop shortcut. The actual installer must pass isolated install, reinstall, payload checksum and uninstall checks with a preserved data sentinel. The existing private Inno build remains a separate owner-only fallback until migration is verified on real existing installations. No end-user Python installation is required.

Database-free HR Online builds have independent acceptance jobs, but no independent stable publication job. HR Full remains restricted to private repositories, and a public repository skips the private snapshot build rather than uploading it. No unsigned automatic updater may execute downloaded code.


## Compact distribution

Full packages carry a single lossless XZ/LZMA2 preset 6 SQLite seed. The decoder uses a 32 MiB liblzma memory limit, reads and writes in 1 MiB chunks, rejects truncated or trailing data, and verifies the uncompressed size and SHA-256 before publishing a fresh database. Legacy GZIP seeds remain readable. An existing workspace is never overwritten. Package download size is not installed database size.

Online packages contain no registry seed. Keep native executable stripping and existing PyInstaller exclusions for browser-development tooling; do not remove runtime dependencies simply to reduce size. Linux DEB uses XZ level 6 and the compatible TAR.GZ archive uses GZIP level 9. Native CI artifacts are already compressed, so upload them without redundant ZIP compression.

Each native build and final release must report actual byte sizes and satisfy initial ceilings of 45 decimal MB per Online package and 750 decimal MB per Full package. These are engineering budgets, not measured final package sizes or a guarantee. Report change versus the published 8.1.6 Online baseline. If a budget fails, investigate and optimize or explicitly review the budget; never delete registry records or disable functional/security checks to meet it. All eight final packages must still pass platform-specific acceptance.

## Complete stable release

A stable release must contain all eight Windows/Linux HR Full and HR Online packages, both updater clients, source archive, registry manifest, size report, signed update manifest and checksums. The Online build is independent but cannot be promoted alone as the complete stable release. Keep the existing distribution/privacy gate for the full catalog. Publication verifies the complete signed asset set locally and compares remote asset digests before marking the draft stable.

## Mandatory distribution matrix (no exceptions)

| Package | HR Full (s bazom) | HR Online (bez baze) |
|---|---|---|
| Windows NSIS Setup | Setup-HR-Full.exe | Setup-HR-Online.exe |
| Windows Portable | Portable-HR-Full.exe | Portable-HR-Online.exe |
| Linux installer | Crawlvora-Linux-HR-Full-amd64.deb | Crawlvora-Linux-HR-Online-amd64.deb |
| Linux portable | Crawlvora-Linux-HR-Full-x86_64.tar.gz | Crawlvora-Linux-HR-Online-x86_64.tar.gz |

All eight packages must be built and tested from the same commit, in one release with both updaters, source ZIP, registry manifest, size report, update manifest, manifest signature and SHA256SUMS (16 files total). Windows and Linux acceptance receipts bind actual tested asset digests and database identity to that commit. Missing, changed or unexpected assets block publication. No separate Online-only stable release. The privacy gate remains mandatory.
