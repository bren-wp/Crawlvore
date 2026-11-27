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
