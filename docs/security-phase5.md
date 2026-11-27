# Phase 5 ? security and code safety, increment 1

Baseline: 92a8e0800864402083e512c6842d4fb31c82a46d.

- Reject duplicate Host, Cookie and X-Local-Token headers; reject foreign or ambiguous Origin on state-changing local requests. Requests without Origin remain supported for native clients. Malformed URL parsing returns a controlled 400 response.
- Consolidate shared packaged/preview snapshot manifest checksum validation. Keep distinct complete and partial snapshot acceptance rules; never overwrite existing workspaces.
- Treat literal __all__ compatibility exports as used by the lexical audit, rather than deleting the public import contract.
- Verify original reference hashes during pixel comparison; strict mode cannot accept zero comparisons.

## Local evidence

16 targeted tests passed (7 HTTP security/response, 2 module boundaries, 6 seed, 1 live worker integration). Runtime AST inventory: 260 functions, 0 unused import candidates, 0 whole-function normalized clone groups, 0 flagged high-risk call patterns, 0 dependency resolution issues. Four-statement clone scan: 405 windows, 0 candidates. pip check: no broken requirements. These bounded scans are not proof of no vulnerabilities or semantic duplication.

## Remaining acceptance

Full regression and native CI, dependency vulnerability scanning, Bandit/Vulture, Rust and TypeScript security review, backup/restore fault injection, vault lifecycle and manual security review remain required. Original design references and native visual acceptance remain outstanding. No production release authorized by this report.


## Increment 2 ? verified recovery publication and cross-stack gates

- Backup publication uses an exclusive hard link instead of a potentially
  replacing POSIX rename. Fault injection demonstrates that a failed publication
  leaves the previous backup byte-for-byte unchanged and that failed restore
  publication cannot activate a partial workspace.
- PHP catalog readers have bounded reads, a search deadline, shard and country
  validation, and an allowlist of public fields. Sole-trader and unclassified
  tax identifiers are removed before matching and presentation.
- Native navigation rejects destinations outside the exact worker origin,
  including missing ports and embedded credentials. No global Tauri API or
  capabilities are exposed.
- TypeScript noUnusedLocals and noUnusedParameters are enabled. A lexical
  regression check guards against introduction of known raw HTML execution
  and browser persistence sinks. Neither is a comprehensive semantic audit.
- RustSec cargo-audit 0.23.0 is a separate CI job included in reusable quality
  acceptance. Vault CI also runs for backup persistence changes.

### Evidence and remaining gates

The preceding commit passed 173 of 175 Python tests on Windows (2 Linux-only
tests skipped), and its GitHub quality job passed PHP/WordPress integration,
npm audit, pip-audit, Bandit and Vulture steps. Local native vault tests passed
8 of 10 (2 real Linux Secret Service tests skipped); Windows DPAPI was exercised.
The 12 data-safety tests passed after exclusive publication changes, including
the two new fault-injection cases. PHP CLI syntax and four isolated catalog
checks passed on a byte-verified copy of the modified file. Full web HTTP CI
and Rust unit/SCA results for this revision still require verification.
No scanner result is a security guarantee. Complete cross-language dead-code,
semantic clone, dependency, packaging and manual threat review remains an
acceptance requirement. Filesystems without hard-link support fail closed;
original databases and older backups are retained.

## Increment 3: audit evidence and supply-chain hardening

Verified baseline: e0a914fa0905cd76e59a4de13d8478c4f18e3253.

- Quality and security run 45920343256: both verify and rust-dependencies
  jobs passed. Logs show 179 Python tests, npm and pip vulnerability checks,
  Bandit medium/high gate, Vulture 90% gate, PHP HTTP acceptance (12 pages),
  real WordPress integration, 65 browser controls and 320 view / 80 dialog
  cases without detected layout errors.
- Secure vault run 45920343257: Windows 8/10 (2 Linux-only skipped), Linux
  7/10 (3 Windows-only skipped). Both real OS vault namespaces verified.
  Local Rust navigation/handshake tests passed 3/3; local Python suite 177/179
  (2 Linux-only skipped).
- Source audit: 260 Python functions, 405 four-statement windows, no reported
  unused import, normalized clone or high-risk call candidates. Lexical
  inventory also covered 10 TS files, 5 Rust files, 5 PHP files, 3 CSS files
  and 12 CI workflow files. A separate conservative exact-token scan (60-token
  minimum, not a semantic proof) found no candidates in TS/Rust and one PHP
  candidate: the FAQ markup rendered on the home and help pages from the
  same data. The separate web and WordPress catalog implementations are
  intentional independent distribution boundaries. Frontend and native URL
  validation are independent defense-in-depth checks, not interchangeable.
- Removed 41 CSS selector branches for 10 confirmed retired collector/studio
  classes and 12 retired translation entries (generated locale rebuilt).
  Other literal-absence candidates are not automatically deleted: dynamic
  text, translated errors and compatibility paths need case-by-case review.
  After cleanup, TS typecheck/build, 320 view / 80 dialog tests and 65-control
  browser E2E passed locally.
- Pinned 50 external GitHub Actions uses to five full SHA commit IDs resolved
  from their existing official tags. All 12 workflow files reverse exactly
  to baseline when the pins are replaced with their former tags. New
  regression check rejects floating external action references. This does
  not pin every external service, Docker image or system package.

### RustSec residual advisory register

The audit scanned 475 crates against 1568 advisories and exited successfully,
but reported six allowed warnings. None are being hidden or waived:

| Crate | Version | Advisory | Disposition |
|---|---|---|---|
| chrono | 0.4.45 | RUSTSEC-2026-0543 | Unmaintained; serde_with via tauri-utils; no fixed upgrade reported |
| proc-macro-error | 1.0.4 | RUSTSEC-2024-0370 | Unmaintained; GTK/glib macros; no fixed upgrade reported |
| zbus_names | 4.3.5 | RUSTSEC-2026-0371 | Unmaintained; zbus via opener; no fixed upgrade reported |
| zvariant | 5.15.1 | RUSTSEC-2026-0370 | Unmaintained; zbus via opener; no fixed upgrade reported |
| zvariant_derive | 5.15.1 | RUSTSEC-2026-0372 | Unmaintained; zvariant; no fixed upgrade reported |
| glib | 0.18.5 | RUSTSEC-2024-0429 | Unsound VariantStrIter; patched >=0.20; current GTK/WebKit stack uses 0.18 |

The application Rust source contains no direct references to those six
crates or VariantStrIter. This is not a reachability proof for dependencies.
A compatible stable GTK/WebKit/Tauri upgrade is required for the glib finding;
do not force incompatible lockfile versions or migrate to an alpha just to
clear a scanner warning. Upstream monitoring and risk disposition remain open.

### Remaining release/security acceptance

No production release is authorized. Native jobs for the baseline were still
running during this review; the cleanup/pinning revision requires fresh CI.
Actual hosting access rules, comprehensive manual threat review and remaining
dynamic dead-code/semantic candidates are not fully verified. Original design
PNGs and approved private national-data distribution remain independent gates.

## Increment 4: verification and performance handoff

The complete native Windows and Linux package workflow 45920343227 passed
for e0a914fa0905cd76e59a4de13d8478c4f18e3253. The next revision c45b7eff
passed both quality jobs (45921115429) and the native secure vault workflow
(45921115356); native package jobs for that revision are separate.

A changed UK cache identity (device, inode, size and timestamps) or manifest
invalidates the session verification cache. Stable files retain the fast
path; changed files must pass the full SHA-256 and metadata checks again.
Tests exercise same-session corruption and the unchanged-file fast path.
This is change detection, not a proof against a malicious local process
that controls the filesystem concurrently.

Pinned the three WordPress acceptance images to digests observed in the
successful quality run 45920343256. Added an Apache/PHP acceptance script
using the same verified image, a synthetic catalog, explicit AllowOverride
All and direct requests to storage. Actual Apache CI result remains required;
this test does not certify a third-party production hosting configuration.

The six RustSec advisory warnings remain documented and are not waived.
Security verification and the performance work may proceed in parallel;
complete security acceptance is not claimed while those upstream findings,
remaining manual review, or latest CI results are unresolved.
