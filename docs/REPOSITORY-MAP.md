# Repository map

- `desktop/`: native Tauri host and platform configuration.
- `frontend/`: canonical TypeScript UI sources; `static/`: bundled web interface.
- Root Python modules: existing worker, storage, registry and recovery implementation. Keep runtime import paths stable until a tested package migration.
- `windows/` and `linux/`: native packaging.
- `webstranica/`: shared-hosting PHP site.
- `wordpress/`: standalone business directory plugin.
- `branding/`: locked reference artwork and fixture comparison inputs; `docs/screenshots/`: product captures only, with capture provenance.
- `tests/` and `tools/`: automated acceptance and engineering utilities.
- `docs/audits/archive/`: historical audit reports, retained for provenance; current audits remain under `docs/`.
- `verification/`: existing historical evidence, not proof of the current commit.
- `.github/workflows/`: active CI and distribution definitions.

Do not add private workspace databases, national data, secrets, generated installers or dependency directories to Git. Keep locked reference paths unchanged. Move runtime modules only after import, packaging and migration tests cover the move.

## Modular runtime boundaries

- Python: company_fields / company_store (directory schema and persistence); registry_access / registry_client (authorization and transport); registry (snapshot orchestration); local_http_security / local_http_response / local_http_routes (loopback HTTP); tvrtk_scraper (workspace composition and lifecycle).
- Rust: main (host lifecycle), window (native window and navigation), worker (process ownership), portable_payload (verified extraction), security_policy (handshake and URL rules).
- TypeScript: strict compilation, separate API/DOM contracts and feature controllers, explicit classic-script bundle order. Shared runtime bindings remain until a separate ES-module migration is accepted.
