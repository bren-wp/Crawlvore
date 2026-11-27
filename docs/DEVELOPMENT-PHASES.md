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
