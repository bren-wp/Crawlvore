# Crawlvora 8.0.0 — verification and release blockers

## Actual checks in Linux
- 40/40 unittest cases passed, including seven new regression tests for heterogeneous CSS classes, label/value structures, data attributes, Croatian table headings, low-confidence detection, bounded preview, invalid input, and multicast rejection. Python compile and JavaScript syntax checked.
- Packaged-source smoke test (not Windows EXE): bundled 26,261 records and Chromium fixture passed. `verification/runtime-smoke.json`.
- 32 fixture UI captures across seven main screens and company detail dialog, two themes and 1440/390 px. No JS errors or document-level horizontal overflow. Compared to archived **v7 implementation screenshots**, not independent user-provided designs: 31 exactly identical; overview-light-1440 differs by 28 pixels (0.00068% of the image). The precise reason for this difference was not established. These are initial-state fixture views, not a complete interactive or production visual test; the new detection status text was not exercised in the visual fixture. `verification/pixel-diff.json`.
- Local concurrent endurance smoke: requested 12 seconds, actual 12.133 seconds, 10,490 writes/upserts, 631 statistics reads, 656 searches, 454 CSV exports; 12,231 total operations; database integrity ok, zero FK violations, 26,261 initial records plus 100 synthetic records. Four-hour workflow and script provided but not executed. Synthetic data was confined to temporary databases.
- 100,000 synthetic registry rows, three successful comparisons, mean 1.009 s; integrity ok. Not a production network benchmark.

## Source / dependency review
- New extraction code ranks structural evidence, caps sample/candidate work, checks CSS selector and mapping input, preserves preview/runtime extraction behavior. Unrecognized business fields are not invented; universal recognition not guaranteed. Dynamic sites still require supported permitted Playwright rendering; no authentication or anti-bot bypass.
- Additional IP-address filtering explicitly rejects multicast/reserved/loopback/link-local/unspecified addresses rather than relying only on `is_global`.
- Local AST scan: 117 runtime Python functions; one unused-import candidate (`studio.inspect_html`, intentional public re-export used by existing callers); zero normalized whole-function clone candidates and zero selected high-risk call patterns. This is not a proof of no dead code, no semantic clones or security flaws. See `verification/source-audit.json`. Existing security architecture and prior findings in `AUDIT-v7.md`.
- Installed runtime dependency closure: 13 distributions, no version constraint mismatches in scanned installed runtime graph. Windows build dependencies PyInstaller and pywebview not installed in Linux environment. Global pip check reports unrelated moviepy/Pillow conflict. Attempt to install pip-audit/Bandit/Vulture failed (no distribution available in configured package index). Full vulnerability database review, independent penetration test and exhaustive semantic clone analysis remain unexecuted. CI includes tools for the next actual runner.

## Outstanding blockers
- No Windows runner available here: Portable.exe, Setup.exe and Windows native smoke tests NOT executed. Build scripts and CI included; do not advertise binary files until actually built/tested. No GitHub repository was supplied for this project in the current exchange.
- Four-hour endurance workflow NOT executed. Source smoke tests cannot substitute for long-duration production validation.
- No independent separate reference designs were supplied for all screens/dialogs. Archived v7 fixture images are a regression baseline, not independent pixel-perfect design approval.
- Production Court Registry, CompanyWall and remote dynamic site extraction remain unverified. Use authorized access, rotate previously exposed secret, retain the private configuration outside distribution. No credentials are shipped in this ZIP.
