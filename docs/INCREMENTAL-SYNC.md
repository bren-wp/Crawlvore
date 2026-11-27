# Registry synchronization and update policy

## Croatian Court Register

The raw national mirror has a stable snapshot ID, category, ordinal and
per-page SHA-256 receipt. The worker preserves checkpointed pages and skips
complete categories. On a subsequent sync it verifies receipt continuity,
stored row count and ordinal bounds before resuming. If local rows are
missing within a recorded page, it requests only that original page (using
the original count and offset, not the current page size), validates the
snapshot identity, counts and original digest, compares surviving rows and
inserts only absent rows in a transaction. Unexpected content, conflicting
existing rows or inconsistent receipts fail closed; no automatic deletion,
replacement or cross-snapshot copying. An inconsistent completed run is
marked incomplete. An unchanged, intact snapshot makes no bulk data requests
and does not rebuild the company projection. Equal-count content corruption
is not detected by this fast coverage check; the full bundle verifier still
checks every page digest. A new index accelerates digest lookups.

New desktop and scheduled sync requests, and CLI --registry-sync, do not
automatically start a different complete snapshot when a local run exists.
The current run is resumed if still available. If a different snapshot is
required, the UI shows New snapshot available, including both IDs. Only
an explicit confirmation or CLI --registry-full-refresh authorizes a
different complete snapshot. A fresh workspace can start the initial
download. The isolated distribution builder retains its exact snapshot
pin and complete verification requirements. The UI distinguishes retained,
received and repaired raw rows. The received count includes all records
in a fetched repair page, not just missing records.

Official v3.0.0 developer guidance (page 17, change detection): the
promjene list supplies the last SCN and time per subject, but does not
provide a general changed-row feed for bulk tables. Individual subject
detail calls are for small datasets and are explicitly not appropriate
for bulk acquisition. Do not use equal category counts as evidence of
unchanged contents, nor mix categories from different snapshot IDs.
A future authorized SCN-based subject-level overlay must remain separate
from the verified all-status raw snapshot. This revision does not
implement that overlay or claim a cross-snapshot bulk delta.

https://sudreg-data.gov.hr/api/javni/dokumentacija/open_api

## United Kingdom

Initial or interrupted monthly ZIP downloads retain their strong ETag,
Range/If-Range identity and durable byte checkpoints. An already verified
installed catalog exposes a Check for updates action. This reads only the
official small listing, compares the installed date against the latest
advertised valid date, and returns zero downloaded archive bytes. It
does not transfer or replace the existing catalog. A newer complete
monthly archive is reported, not automatically installed. A genuine
Companies House Streaming API integration requires authorized access,
a compatible initial snapshot/timepoint, persistent stream cursor,
transactional event application, tombstones and a reconciliation strategy.
The monthly basic-company-data ZIP itself is not a delta feed.

https://www.gov.uk/guidance/companies-house-data-products
https://developer-specs.company-information.service.gov.uk/streaming-api/guides/overview

## Acceptance and non-destructive migration

Regression tests cover unchanged snapshot, interrupted page, missing
previously completed page, mismatched digest, confirmation before full
refresh, documented empty API responses and a metadata-only UK update
check. Existing local databases were not altered or migrated during
development. The new index is created by the upgraded application
on opening a workspace. Distribution still requires all national
categories, complete snapshot verification and private release review.
