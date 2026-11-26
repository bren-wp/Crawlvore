# Changelog

## 8.1.4 — release candidate

- Add explicit, backed-up transactional import of verified registry snapshots into existing workspaces, with conflict detection, rollback and idempotency tests.

- Reject unexpected registry categories, mixed snapshot metadata and repeated page digests during database verification.
- Add a database SHA-256 and category count to verified registry manifests; reject stale manifests on bundle reuse.
- Restrict full registry collection and registry-bearing production release to explicitly reviewed private distribution.
- Include an explicit non-complete registry manifest in public preview packages and checksum all seven release assets.
- Build public candidates from the merged main branch when VERSION changes.

## 8.1.3

See the [8.1.3 release notes](https://github.com/bren-wp/Crawlvore/releases/tag/preview-8.1.3-36b44d5e2ecf).
