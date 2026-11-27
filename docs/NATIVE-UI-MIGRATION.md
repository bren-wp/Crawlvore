# Native desktop migration

## Implemented phase

The native migration candidate now uses Tcl/Tk rather than Qt or Slint to avoid a new large runtime dependency. It renders widgets without HTML, JavaScript, WebView2 or WebKit. It is not yet a replacement for the production Tauri application. Windows and Linux source runs use the existing workspace location. The worker runs in a separate process, serves only authenticated loopback API requests, denies HTML/JavaScript requests in native mode, and shuts down with the parent pipe. No browser is opened.

Run in an isolated test directory with the runtime dependencies installed:

    python src/native_desktop.py --data-dir path-to-disposable-workspace
    python src/native_desktop.py --native-smoke

The smoke test creates a temporary synthetic workspace, reads the real API, opens a company profile through the actual native widget renderer, and closes cleanly. The migration CI builds separate executables for Windows and Linux without packaging the HTML assets and runs this smoke test. These are development candidates, not stable production releases.

## Feature parity gate

Implemented in candidate: original dark palette, 242px sidebar, dashboard metrics, city and contact coverage charts, recent companies, paginated company directory; debounced search; OIB/MBS, city, NKD and contact filters; grouped profile; secure access configuration; synchronization controls and completion refresh; basic backup creation.

Remaining: detailed analytics, full job scheduling and history, complete registry category browsing and export, import/export tools, mail and history, protected backup catalog and restore/replication/integrity tools, complete application settings, update integration, keyboard and layout parity, crash recovery, long-duration CPU/RAM measurements, complete Windows/Linux packaging and edition acceptance.

Keep the production renderer until these functions have equivalent native controls and all migration acceptance tests pass. Do not remove the existing database services, change the workspace identity or ship a partial replacement as stable. After parity, remove Tauri, its browser dependencies, HTML assets, TypeScript build and legacy UI tests from production packaging; update NSIS and Linux dependencies accordingly.

## Secure updates

A separate updater client supports signed manifests, bounded HTTPS downloads, edition and downgrade checks, staging and explicit installer confirmation. Portable replacement, rollback and native UI integration are still pending. Do not automatically execute packages without authenticated metadata.

Pixel-perfect parity is not established by a successful smoke test. Compare native captures against the current production reference at the same viewport, DPI and font, then review differences before replacing the production shell.
