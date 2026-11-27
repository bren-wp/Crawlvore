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

Process-death regression tests terminate a real child process after a durable UK byte checkpoint and after a committed HR registry page. Restart with the same isolated data directory, verify SQLite integrity, and assert no repeated committed page or byte prefix. Completed UK archives now carry a SHA-256 and must match it before offline reuse. Old or corrupted archives remain on disk but are not trusted. This is not yet a native GUI crash test or power-failure certification.

## Packaged worker recovery gate

Native CI must force-terminate the actual packaged worker after committing an isolated synthetic record and preference, reopen the same workspace, verify SQLite integrity, confirm exact record and settings preservation and test graceful shutdown. This gate uses non-distribution fixtures and never touches a real user workspace. It does not simulate power failure or kill the GUI during a live national download; those remain separate acceptance requirements.

## Edition switch retention

After successful GB catalog verification, persist its manifest next to the content-addressed SQLite cache. A later HR or Online edition can reopen the same previously used GB catalog without the embedded archive or a network request. Do not remove any previous snapshot or cached database. A changed/corrupted cached database is rejected on reopen, not deleted. Unopened embedded catalogs are still lazily extracted on first use.

The packaged worker recovery gate now interrupts an actual authenticated 2 MiB-declared HTTP upload after observing the exclusive import lock, verifies that no partially uploaded record was committed, and checks prior committed records and preferences after restart. The input is synthetic; it is not a live registry download or a power-failure test.

## Atomic fourteen-asset promotion

Every completed change on main builds a verified non-distribution candidate; its artifacts are archived in Actions rather than published as an incomplete GitHub Release. Production remains restricted to an explicitly reviewed private distribution. Validate all 14 files, checksums, edition manifest, and ZIP integrity before creating a draft release. Compare every uploaded asset size and server-reported SHA-256 with the local verified bytes; only then publish the draft. A failed upload or missing server digest leaves the draft unpublished. Do not silently substitute database-free executables for the HR or GB packages.

Registry seed installation and transactional integration now preflight destination free space. Existing workspaces and source files remain unchanged when that check rejects an operation. On POSIX, the published seed directory entry is flushed before successful return. Actual power-loss durability remains filesystem and hardware dependent.

## Unified Windows build evidence

CI records the exact source SHA, accepted country snapshot hashes and final EXE sizes/SHA-256 after each edition's native and isolated installer acceptance. The production publisher verifies all four receipts against the release source and combined registry manifest before upload. Receipts stay in CI artifacts rather than increasing the 14 release files. Local archive previews may supply CRAWLVORA_BUILD_SOURCE_SHA only when the exact source has been established; local receipts are not production evidence.

## Portable artifact publication safety

Portable assembly checks free space, writes to an invocation-owned unique staging file, validates the assembled size and worker SHA-256, and publishes by an exclusive hard link. A competing destination is never overwritten; only the current invocation's temporary file is cleaned up. Unsupported filesystems fail closed. Native acceptance must still validate the resulting executable.

## Separate shared-hosting package

The verified candidate workflow also archives Crawlvora-Web.zip separately from the desktop matrix. It is built from the exact committed source, allows only reviewed site paths and empty catalog manifests, and includes the Apache storage deny rule. It never includes local SQLite data, catalog shards or credentials. Extract the archive into a fresh hosting root; preserve existing approved catalogs during upgrades. Actual hosting access controls and operator/legal details still require independent acceptance. The fourteen production release assets remain unchanged.

## Independent deployable web and plugin packages

Build the website and WordPress packages exclusively from an exact Git
commit, using the allowlisted package tools. ZIP members use fixed metadata,
sorted paths and validated CRC; publication is exclusive, so a failed build
cannot replace an existing ZIP. Reproducibility is for the same source and
compression implementation.

A fresh web ZIP includes only empty catalog manifests. An upgrade ZIP omits
all catalog files and preserves deployment-specific SEO config and robots
unless the operator explicitly supplies --base-url. Candidate and production
workflows archive both web ZIPs and their separate SHA256SUMS.txt outside the
14-file desktop production release matrix. WordPress uses the same exact
five-member code-only packaging tool in both workflows.

Private registry distribution, complete verified HR/GB snapshots, strict
visual acceptance and full native/quality/endurance gates are unchanged.
