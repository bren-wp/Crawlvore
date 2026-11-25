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
