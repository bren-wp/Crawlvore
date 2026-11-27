# Desktop architecture decision

Status: accepted direction; implementation and verification pending.

Keep the existing Python extraction, OAuth2 registry synchronization, SQLite schema and Playwright worker operational. The desktop target is Tauri 2.12 (stable Rust crate 2.12.7 as checked on 2026-11-25), with a TypeScript 7 frontend. Do not depend on a hypothetical stable Tauri 3. Go is not required for this architecture.

## Migration sequence

1. Establish green Windows and Linux baselines; preserve database migration tests, screenshots and export compatibility.
2. Extract typed API contracts from the existing HTTP endpoints. Migrate the current UI incrementally to strict TypeScript without changing DOM IDs, visual tokens or reference layouts. Ship bundled local assets, not remote executable JavaScript.
3. Add a Tauri desktop host with minimal capabilities and a supervised packaged scraper worker. Use a dynamically assigned loopback port, authenticated IPC, explicit process ownership and bounded shutdown; never grant remote pages desktop IPC or arbitrary shell access. Store credentials in OS-backed secure storage, not the executable or source repository.
4. Introduce Rust implementations of measured bottlenecks only after equivalence tests; keep Playwright as a dedicated isolated worker. Preserve the public API rate limits, DNS controls, consistent snapshots and cancellation semantics.
5. Compile and smoke-test Windows portable and installer packages and Linux distribution. Verify upgrade and rollback against existing data. Run both themes and pixel regression checks on a fixed browser/OS/font baseline.
6. Replace the legacy desktop host only after parity and verified distribution; retain the CLI until a tested migration is available.

Dependency updates must pass tests and vulnerability checks before release. Pin resolved transitive versions with platform-specific lock files once the CI resolves and validates them. Never include private OAuth credentials in release artifacts.

References: https://tauri.app/release/ ; https://github.com/tauri-apps/tauri/releases ; https://www.typescriptlang.org/download/

## Implemented migration stage

The Rust host now supervises a packaged Python worker on a dynamically assigned authenticated loopback origin. The existing scraper, registry and database remain in the worker. TypeScript provides the English-first locale catalog and a persisted Croatian preference. The Windows native packaging workflow builds a standalone embedded-worker portable executable and an Inno installer; Linux packaging creates a tar archive. External web-domain links are passed to the system browser by the Rust-only opener; other new windows are denied. Native compile, package verification, full TypeScript UI migration and production parity remain release gates.

The frontend application source is migrated to TypeScript with explicit API contracts and typed DOM IDs. The compatibility compiler profile still permits implicit any and legacy null handling; the locale module remains strictly checked. External links use the Rust-only Tauri opener and are restricted to HTTP(S) domain URLs without credentials or local hostnames. No native command capability is exposed to the webview.


## Phase 3 ? modularization, increment 1

The Python HTTP framing, loopback host, session-cookie and token checks live in
`local_http_security.py`; the worker retains the existing HTTP status codes and
authorization order. The Rust host delegates process ownership, portable
extraction and startup to `worker.rs` and handshake/navigation policy to
`security_policy.rs`. The TypeScript API and DOM declarations are separated
into `api-contracts.d.ts` and `dom-contracts.d.ts` without changing the existing
classic-script loading model or emitted application JavaScript. No database
schema, credential storage, DOM identifiers or feature behavior is changed.

Next: split worker route handlers and TypeScript feature controllers with
integration coverage, then progressively enable strict compiler options.


## Phase 3 ? increment 2

The classic-script frontend source is split by feature: registry and jobs,
analytics and settings, recovery, protected backups, national catalog and
registry profile. The build assembles the existing two public assets in
explicit initialization order, so the authenticated HTTP allowlist, native
packaging, and browser harness remain compatible. Shared globals are retained
for now; this is a staged source split, not independent ES modules.

Python response serialization and security headers move to
`local_http_response.py`. The Windows-only Rust portable extraction moves to
`portable_payload.rs`, preserving exclusive temporary directories, SHA-256
verification and the worker-owned extraction lifetime.


## Phase 3 ? increment 3

The directory storage class now lives in company_store.py, shared field
contracts in company_fields.py, and registry authorization and transport in
registry_access.py and registry_client.py. Existing core and registry imports
remain available; no schema or migration changes. The Rust window composition
is isolated in window.rs. The frontend now inherits the full strict TypeScript configuration, including
noImplicitAny, useUnknownInCatchVariables and strictNullChecks. Shared
classic-script state remains for compatibility with the deployed asset paths. Acceptance requires native package builds,
the full isolated regression suite and browser integration, not source
reorganization alone.

The authenticated HTTP handler is now constructed by local_http_routes.make_handler
with explicit per-workspace dependencies. Startup, workspace lifecycle and
shutdown remain in src/tvrtk_scraper.py. Route behavior, tokens and permissions
are preserved.
