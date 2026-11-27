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
