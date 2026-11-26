# Changelog

## 8.1.4 — release candidate

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
