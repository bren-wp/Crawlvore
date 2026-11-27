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
