# Partial offline registry preview

Use `python tools/prepare_registry_preview.py SOURCE.sqlite3 NEW_DIRECTORY` to make a consistent SQLite online backup of a live collection, verify all committed page digests and counts, and build the company directory from currently available official names. Subjects without names remain accessible in the raw registry browser by MBS; no company names are fabricated. The source is read-only and the destination must not exist. The generated manifest explicitly records `complete: false`, all discovered category counts, collected counts, SHA-256, and the directory projection count.

The preview seed can initialize an isolated offline workspace via the existing seed installer. It must not be passed to the full production build pipeline. Public redistribution remains subject to a documented scope and licence review; never publish OAuth credentials or personal workspace data. Full registry acceptance still requires all categories and the full projection.
