# Crawlvora 8.1.1 — Production acceptance record

Baseline commit: `0d80441d2a0ce4899361226886cd6a0036869d1d`.

- [Quality CI 45708962662](https://github.com/bren-wp/Crawlvore/actions/runs/45708962662): 77 tests collected, 75 passed, two platform-specific skips; dependency checks, Bandit, Vulture, TypeScript, browser E2E, fixture layout and performance workflow passed.
- [Native vault acceptance 45708967917](https://github.com/bren-wp/Crawlvore/actions/runs/45708967917): Windows DPAPI real roundtrip passed; Linux Secret Service isolated-session real roundtrip passed. Each platform skipped the other platform's specific test.
- [Million-record benchmark 45707097137](https://github.com/bren-wp/Crawlvore/actions/runs/45707097137): previous synthetic Linux measurement, FTS phrase P95 0.605 ms, same scan P95 337.780 ms, integrity passed.
- Published older [8.1.1 preview](https://github.com/bren-wp/Crawlvore/releases/tag/preview-8.1.1-2f02e6de425d) includes all six assets. It is not the current production release.

## Remaining acceptance gates

Latest native packages, endurance on release SHA, authorized live Court Registry OAuth/API check, original approved reference PNGs, updated Settings reference, strict pixel comparison, actual physical separate disk and replacement-computer drill, refreshed actual English fixture captures and committed dependency locks. Automated source scan and normalized clone candidates are review aids, not proof of semantic equivalence, absence of dead code or complete security. New CI changes require fresh checks. No production release or merge until acceptance. Previous historical audit reports remain in Git history.
