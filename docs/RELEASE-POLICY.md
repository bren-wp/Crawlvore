# Production release policy

The original seven desktop release assets are:

- Portable.exe: standalone Windows Tauri executable with an embedded registry worker.
- Setup.exe: Windows installer with a native Tauri host and packaged worker.
- Crawlvora-Linux-x86_64.tar.gz: tested native Linux distribution (Ubuntu 24.04 baseline; system WebKitGTK runtime libraries are required).
- Crawlvora-Linux-amd64.deb: installable desktop package with system dependencies and application-menu entry.
- Crawlvora-source.zip: source from the exact release tag.
- REGISTRY-MANIFEST.json: verified registry snapshot identity and coverage.
- SHA256SUMS.txt: SHA-256 checksums for every other published asset.

The production workflow requires an immutable version tag on main, matching version metadata, committed npm and Cargo locks, a successful quality/security workflow, native builds and smoke tests on Windows and Linux, a successful million-record performance benchmark and a completed four-hour endurance test. It refuses to publish an incomplete asset set. The native workflow is the only active desktop packaging pipeline; legacy scripts are retained for historical development only.

Before tagging, review the visual differences against the accepted brand reference, complete the live authorized registry integration checks, verify upgrade compatibility with the existing database, and review the Python, npm and Rust audit evidence. Credentials are local configuration, never a release asset. Signing certificates and notarization have not been configured; unsigned packages may trigger OS warnings.

The first native release is not approved until all gates have actually passed and the visual and functional parity review is complete.

The production API smoke test is available in `tools/live_registry_check.py` and the manually dispatched `live-api.yml` workflow. Configure the OAuth2 secrets privately in the `production-api` environment, approve the run, and verify its result before tagging. The smoke test reads only one company row, does not log record contents or credentials, and is not a complete production mirror test.

An explicitly labeled prerelease candidate may be published from the data-safety-release branch only after quality and native packaging workflows succeed for the same commit. It contains all six assets and checksums, is never marked latest, and does not satisfy or bypass the production gates. Production release remains subject to the existing tag workflow and acceptance criteria.

## Windows edition matrix

Production requires 13 assets: the original seven plus Portable-HR.exe, Setup-HR.exe, Portable-GB.exe, Setup-GB.exe, Portable-Online.exe and Setup-Online.exe. Full embeds both reviewed catalogs, HR only Croatia, GB only UK, and Online embeds neither registry nor legacy CSV. Existing data is preserved on upgrade. HR acquisition uses authorized Crawlvora Connect/Sync; UK supports explicit download of the official monthly snapshot. The private release gate remains mandatory. Local preview uses `windows/package-native.ps1 -Edition HR` (or Full, GB, Online) with CRAWLVORA_PRIVATE_PREVIEW=1 and staged snapshots; compile frontend first. Each pair is promoted after isolated native smoke, install, payload verification and uninstall. No public upload of raw data until reviewed.

## WordPress distribution

Keep all 13 desktop release assets and add Crawlvora-WordPress.zip as the fourteenth required asset. The plugin contains code only, consumes reviewed JSON catalogs, and must pass PHP syntax, catalog unit checks and disposable WordPress integration before publication.

## Durable acquisition

Retain original UK archive bytes in the workspace downloads directory. Resume with HTTP Range and If-Range only with a matching strong ETag, exact Content-Range and declared total. If the server returns a new full response, stage separately and retain the earlier partial. Completed archives are reused for retrying indexing. Only derived scratch files may be discarded. Existing installed catalogs and user databases are never replaced by download operations. HR sync commits each validated page and checkpoint in the same transaction. A changed or unavailable remote snapshot cannot be resumed by mixing data. Fault-injection and actual native interruption/restart tests remain separate acceptance gates.

## Credential durability

Secure persistence is selected by default in Crawlvora Connect. Windows DPAPI and Linux Secret Service protect credentials per OS profile and workspace; successful save requires vault read-back. Explicit session-only mode remains available. Restarting or upgrading editions must retain authorized access when using the same workspace and OS profile. If the secure vault is unavailable, never silently store plaintext. Uninstall must not destroy national catalogs or user databases. Explicit removal of saved access is available in Connect; portable editions have no OS uninstall event. Automatic vault cleanup on installer uninstall is not yet verified and must not delete other workspace credentials or backup-vault records.
