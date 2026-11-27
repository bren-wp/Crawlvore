# Changelog

## 8.1.7

- Improve native header, navigation spacing, overview metrics and charts; capture matching 1280×700 lossless reference and native screenshots and add a strict RGB comparator with single-channel regression tests. Current native visual acceptance remains failed.

- Use final reference palette and compact desktop layout; move synchronization above Settings, add native navigation icons and a resizable non-maximized window with adaptive card grids and overflow access.
- Capture actual native windows separately from reference screenshots and check seven pages at compact window sizes.

- Add native settings, tasks, import/export and analytics candidate views with bounded authenticated streaming transfers.

- Rebrand the visible application to Tvrtke, add official product and developer information, remove workspace badges, retain compatibility identifiers and existing data paths.
- Add offline verified legacy seed cleanup with a recovery copy and preservation of linked official records.

- Add reviewed duplicate reconciliation, verified pre-merge backup, preservation of alternate fields, history and original records, and reimport protection.
- Port profile history and additional business data into native widgets; check directory coverage before skipping a completed snapshot.

- Port the original dark palette, sidebar, dashboard metrics/charts and additional directory filters into the native candidate.
- Require the complete Windows/Linux edition matrix in one stable release; allow Online updater selection from the combined signed release.

- Begin WebView-free native migration with real Tcl/Tk directory, filters, profiles, synchronization, and backup creation, authenticated API-only worker mode and independent Windows/Linux build acceptance.
- Normalize the expected Windows installer path in updater acceptance tests.

- Polish loading, focus and profile dialogs; repair obsolete visual-test navigation.
- Build standalone Windows and Linux update clients with pinned Ed25519 trust anchor, bounded HTTPS downloads, signed manifests and explicit installer confirmation.

- Use Crawlvora branding throughout the visible desktop interface, remove the provenance tab and raw provider links while retaining underlying provenance and alternate values in history.
- Add isolated signed update staging and authenticated worker load measurements.

- Retire unreachable historical web scraping, configurable connector, browser renderer and studio engines; keep legacy imported data, provenance labels and active regression coverage.
- Separate runtime dependencies from browser and audit tooling.

- Require authenticated sessions in source and packaged mode; stop logging session URLs in HTTP access logs and bound worker concurrency and idle socket timeouts.
- Remove obsolete PyWebView fallback and use a dependency-free-of-browser worker self-test.
- Update SHA-2 and build dependencies; retain stable Tauri 2 pending full native migration.

- Add measured package-size reports and CI budgets for both Croatian editions.

- Compress the complete offline SQLite seed with XZ/LZMA2, verify the exact decoded bytes with a bounded decoder, retain legacy GZIP support, and avoid recompressing native CI artifacts.

- Add index-backed category ordering and sparse e-mail contact lookup.
- Introduce signed update manifest and bounded package verification with edition and rollback checks; execution is not yet enabled.

- Add single-recipient TLS SMTP correspondence with OS vault, explicit confirmation, security notice template, suppression list, and persistent delivery status.
- Group company profiles and abort stale client-side directory requests.
- Separate database-free publication from the restricted full catalog release.

- Project official primary NKD activity codes with revision labels and add a directory/export activity filter.

- Separate download and directory-projection progress, commit completion atomically, and refresh the business directory immediately after successful synchronization.

- Fixed Croatian dark interface, remove duplicate contact shortcuts and add an e-mail contact filter.

- Move the runtime entry point into src without changing source workspace or packaged data paths.
- Introduce Croatian NSIS installer with isolated install, upgrade and uninstall acceptance.

- Focus exclusively on Croatian Court Registry desktop editions for Windows and Linux.
- Move Python runtime modules into src and separate legacy data resources.
- Retain existing workspaces and verified snapshot archive.

## 8.1.6

- Separate Croatian and English national and database-free editions.
- Restore and verify Croatian registry snapshot 1370 from the private data archive without redownloading it.
- Verify the official UK live-register monthly catalog independently.
- Preserve existing workspace data and language preferences.

## 8.1.5 - Online

- Resume checkpointed registry downloads and repair missing rows from original verified pages without overwriting existing records. Require explicit confirmation for a different full snapshot.
- Check UK monthly catalog availability without downloading an archive again.
- Harden local HTTP authorization, backup publication, streamed transfers, catalog path validation and release ZIP validation.
- Reduce the native Rust dependency surface and add RustSec, WPCS and hosting acceptance evidence.
- Optimize provider counts and full exports; validate million-row JSON, CSV and XLSX workloads in CI.
- Expand bilingual web and WordPress profiles, separate reproducible fresh-install and upgrade ZIPs, and protect existing catalogs during upgrades.
- Preserve the complete private national-data distribution gate. Public Online application releases use a separate code-only publication path; bundled national-data editions retain their full acceptance gates.

## 8.1.4 — release candidate

- Brand registry workflows as Crawlvora Sync and Crawlvora Connect, reduce technical UI details, retain data provenance, reject ambiguous HTTP request framing and expand browser click coverage.

- Avoid repeated large buffer copies in JSON imports; add free-space checks, exclusive import admission and browser registry profile regression coverage.

- Support disk-backed 2 GiB CSV/JSON imports, transactional incremental JSON parsing, bounded-memory full CSV/JSON/Excel exports, and paginated original registry records in company profiles.

- Add local-only Linux dual-database packaging and extracted DEB/TAR smoke acceptance; ignore national data staging in Git.

- Stage verified partial HR and complete GB snapshots for private local preview packaging, with separate smoke acceptance and no relaxation of production release requirements.

- Restore entity filtering, selective exports and national directory handlers in the canonical TypeScript sources so native builds do not overwrite working controls.

- Restrict active national catalogs to Croatia and the United Kingdom; hide unverified countries in desktop and public web navigation.

- Add read-only national catalog, GB indexed offline search and details, compressed snapshot staging and optional native packaging; preserve Croatian workspace isolation.

- Isolate website catalogs by country and add separate Companies House bulk importer and APR download staging.

- Add explicit legal-entity classification and filtering; preserve unclassified records until source evidence is available. Fix the identifier-search browser assertion.

- Automatically recognize OIB and MBS in the directory search without prefixes, retain company-name search and exact indexed identifier matching, and test all three search modes.

- Force the existing MBS lookup index for related registry rows to avoid category-wide scans during high-volume projection; correct the browser E2E JSON import.

- Enable arbitrary combinations of export fields, test actual browser download, and skip unavailable related registry categories during directory projection. Document the reviewed allowlisted SQL construction.

- Add local field-specific CSV, JSON and Excel export with optional deduplication and directory filters. Default registry page size to the supported maximum of 1000.

- Add isolated partial-registry preview preparation with checkpoint verification and explicit incomplete manifest; retain strict production acceptance.

- Require verified offline registry seed and matching manifest in native package smoke tests; guard GitHub asset size.

- Harden native Secret Service executable selection and preserve browser smoke checks under optimized Python; document five low-severity static findings.

- Add explicit, backed-up transactional import of verified registry snapshots into existing workspaces, with conflict detection, rollback and idempotency tests.

- Reject unexpected registry categories, mixed snapshot metadata and repeated page digests during database verification.
- Add a database SHA-256 and category count to verified registry manifests; reject stale manifests on bundle reuse.
- Restrict full registry collection and registry-bearing production release to explicitly reviewed private distribution.
- Include an explicit non-complete registry manifest in public preview packages and checksum all seven release assets.
- Build public candidates from the merged main branch when VERSION changes.

## 8.1.3

See the [8.1.3 release notes](https://github.com/bren-wp/Crawlvore/releases/tag/preview-8.1.3-36b44d5e2ecf).
