# Development acceptance ledger

This ledger records verified evidence separately from implementation work.
It does not authorize publication.

| Phase | Current evidence and remaining gate |
|---|---|
| 1 Product presentation | English README and running-worker captures exist; refresh actual latest native screenshots after visual acceptance. |
| 2 National catalogs | UK complete local catalog verified earlier; HR snapshot 1370 remains incomplete. No raw national data is public. |
| 3 Architecture | Python, Rust and TypeScript source split and strict TS; shared classic-script state remains intentional compatibility work. |
| 4 Visual | 320 layout and 80 dialog cases passed, browser DPI emulation only. Original locked PNG files and native exact matching still outstanding. |
| 5 Security | Quality/security 45921658940 and native vault 45921658989 passed; six upstream RustSec warnings and manual review remain unresolved. |
| 6 Performance | 1,000,000-record run 45921653299 passed; 14,400-second run 45921653337 remains in progress. Full production-scale export and RSS not yet verified. |
| 7 Web and WordPress | Bilingual shared web template and features/downloads routes, SEO generation and independent code-only packages implemented. Latest PHP HTTP, responsive layout, WordPress standards, real hosting, company profiles and Gutenberg acceptance remain open. |
| 8 Production release | Exact private-distribution, verified registry, original design, security, native and endurance gates preserved. No new stable release until verified. |

Latest changes deliberately do not restart the existing endurance run:
only web packaging, web templates, tests, documentation and distribution
workflows are modified. The new commit requires its own CI evidence.


## Follow-up, phases 5 through 8

- Exclusive staged receive and export publication preserves prior destinations
  and removes incomplete invocation-owned files on ordinary exceptions.
  Crash/power-loss durability is not claimed. JSON export avoids an unused
  SQL provenance aggregate and emits each serialized record in one write.
- Windows full export benchmark on 100,000 synthetic rows verified JSON
  (47,888,896 bytes, 2.698 seconds, 43,286,528 bytes peak process RSS) and CSV
  (7,800,284 bytes, 2.093 seconds, 41,402,368 bytes peak process RSS).
  Every record and provenance entry was checked; SQLite integrity passed.
  Million-row full-export acceptance is added to the separate performance
  workflow; existing four-hour run is not cancelled.
- Public PHP catalog path/record validation strengthened; both website and
  plugin provide exact-registration profiles, declining ambiguous results.
  WordPress 1.0.1 source metadata synchronized; not a published plugin release.
  PHP and real WordPress acceptance for these changes is still required.
- Release ZIP checks now reject traversal, duplicate case-insensitive paths,
  nonregular members and unexpected WordPress files. The 14-file release
  matrix and all private distribution, reference and registry gates remain.
