# 8.1.6

- Separate Croatian and English national and database-free editions.
- Restore and verify Croatian registry snapshot 1370 from the private data archive without redownloading it.
- Verify the official UK live-register monthly catalog independently.
- Preserve existing workspace data and language preferences.

# Changelog

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
