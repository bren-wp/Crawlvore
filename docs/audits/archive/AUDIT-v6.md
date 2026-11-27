# Crawlvora 6.0 — verification report

## Executed checks

- 28 Python unit/integration tests passed on Linux; new cases cover field detection, queue persistence/cancellation, interruption, history, renderer dispatch with a mocked browser, and XLSX/XML/SQL round trips.
- JavaScript syntax and Python compilation passed.
- Fresh local HTTP API verified 26,261 CSV records, 806 cities, 25,208 telephone entries and 454 websites.
- Chromium isolated fixture rendering: all seven primary views at 1440×900 and 390×844, no JavaScript page exceptions or document-level horizontal overflow. A job table heading collision was corrected. `branding/` contains desktop fixture captures. No actual local HTTP navigation: administrator policy denies it. Reproduce using `python tools/visual_check.py` after installing the Chromium browser.
- Five local repetitions against 26,261 rows: median directory first page 0.69 ms, Zagreb search 15.08 ms, statistics 15.64 ms, CSV export 313.54 ms. These are local Python/SQLite timings, not remote network timings or Windows measurements.

## Security review

- Reviewed local HTTP API host validation, POST token checks, static-file allowlist, CSP, permissions, registry OAuth and pagination, external request validation, exports, credential persistence and new queue routes.
- Private API credentials excluded from the distribution. Registry uses TLS verification and fixed HTTPS host; OAuth token is in process memory. Queue does not store API tokens or query strings. Revoke or rotate credentials exposed in screenshots.
- Playwright traffic is intercepted with an invalid direct proxy and requests are restricted to same-origin HTTPS GET document/script/XHR/fetch, robots rules, caps, delay, no redirects, blocked service workers and WebSockets. No bypass of restricted portals. Renderer dispatch unit-tested, real remote site rendering not confirmed.
- Excel text cell typing protects formula-like values; SQLite SQL quotes strings and keeps raw JSON. XML uses escaped field data. Registry export writes to temporary files and streams to the response.
- Added foreign-key enforcement, provider index and indexed history. Conservative OIB linking avoids selecting arbitrary duplicate matches and detects conflicts with existing source identities. No fuzzy identity merge. Registry raw records remain preserved per snapshot.
- Remaining risks: DNS validation and HTTP connect are not atomically pinned (DNS rebinding risk). Use only known, authorized websites. Browser isolation is not a hardened OS/network sandbox. No independent penetration test, dependency vulnerability scan or formal full security certification was run. Local HTTP reads are accessible to software on the local machine; do not expose the server to the network. Separate OS user accounts and private configuration protection are recommended.

## Dead code and performance review

- Reviewed new modules, entry points, frontend event wiring, imports and call paths; removed unused import from registry export and added guaranteed renderer cleanup. Syntax and tests pass. No complete static call-graph or semantic clone analysis performed; do not interpret this as proof of zero dead code.
- Registry XLSX now uses write-only streaming rows; XML/SQL use streaming output, reducing memory use for category export. Existing directory XLSX/JSON still hold data in memory. Large production snapshot, long-running renderer, multi-process database and disk-space stress tests remain outstanding.
- Daily scheduler runs only when app is open, once per eligible weekday, does not retry failed jobs automatically. Existing registry resume logic is reused. Separate concurrent app instances are not supported. Queue only supports token-free sources and the registry.

## Release blockers

- Production Court Registry OAuth/API access, full category coverage, real remote Playwright rendering and authorized CompanyWall credentials were not verified.
- Windows Portable.exe and Setup.exe are not compiled: Linux environment has no Windows toolchain. `windows/build.ps1` and GitHub Actions build recipe are included, and require actual Windows runner testing (including WebView2 and browser bundling).
- No final brand reference images for pixel comparison; isolated screen rendering is not proof of 1:1 match or full interactive UI integration. Light theme and all dialogs need additional visual regression coverage.
