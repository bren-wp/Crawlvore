# Crawlvora 7.0.0 — verification report

## Executed in Linux

- 33 automated unit/integration tests pass (28 previous tests and 5 added tests: public DNS pinning, mixed public/private DNS rejection, complete-snapshot diff, scheduled retry, table mapping).
- Python compilation and JavaScript syntax checks pass.
- Source runtime smoke test passed: actual Chromium rendering of a local HTML fixture, bundled CSV seed (26,261 rows), and asset presence. This is not a Windows executable test.
- 32 isolated UI captures: seven main screens plus company profile dialog, each in two themes at 1440×900 and 390×844. No page exceptions, no document-level horizontal overflow; dialog fits viewport. Snapshot comparison button was exercised against a mocked endpoint. These are not live API captures or pixel comparisons to independent design references.
- Synthetic volume test: 100,000 registry rows across two snapshots, three comparisons, 500 correct changed MBS results per comparison, SQLite integrity_check=ok. Insert 0.469 s; mean comparison 1.004 s on this environment. This is not a multihour endurance test or a production load benchmark.

## Security / source review

- External HTTPS clients use a custom urllib3 connection class with a single DNS result set at connection time; rejects all results if any address is non-global, connects to an approved literal IP, verifies peer IP, retains TLS hostname/SNI verification, rejects proxies and has no plain HTTP adapter. DNS tests use mocked sockets; no independent network penetration test or OS-level browser sandbox assessment.
- Registry automatic retries are bounded (two additional attempts at 15 and 60 minutes), only for transient network/5xx errors; 401/403/429, invalid data and user cancellation are not automatically retried. Application must remain open to run the scheduler.
- Snapshot comparisons require completed snapshots and compare row multisets, not assumed row IDs. Categories with differing manifests are not compared. Modified rows count as one removed and one added. The comparison does not claim to be the registry's official change feed.
- Cross-source final merge checks reject conflicting OIB/MBS identities; no broad fuzzy matching. Legacy name/city matches remain a potential false-match risk. No complete deduplication proof.
- Reviewed imports using AST name references and removed five unused imports. Not a proof of no dead code or semantic clones.
- Runtime dependency versions observed: requests 2.32.5, urllib3 2.7.0, BeautifulSoup 4.14.3, openpyxl 3.1.5, Playwright 1.57.0. Environment-wide pip check reported unrelated moviepy/Pillow conflict. Online dependency vulnerability database scan and independent full penetration test not executed; CI recipe added for pip-audit and Bandit. No clean security certification claimed.

## Remaining release blockers

- Windows Portable.exe and Setup.exe are not compiled or run in Linux. Windows script adds actual packaged smoke test and silent install/uninstall check; unexecuted on Windows. Build artifacts cannot be claimed to exist.
- Production registry and CompanyWall network calls, actual endpoint/category coverage and dynamic remote website extraction are not verified. No credentials are embedded in distribution. Existing local private configuration remains supported; rotate exposed secret before production.
- Universal automatic extraction cannot be guaranteed; the heuristic preview now supports semantic fields, table headings and card attributes, but unknown layouts require mapping. Authorization and robots rules still apply.
- No independent per-screen brand reference supplied for exact 1:1 pixel comparison. Both themes and dialog are fixture-tested only; local HTTP navigation blocked in prior environment checks.
- Full dependency audit, extended endurance, production performance, independent security assessment and complete dead-code proof remain outstanding.
