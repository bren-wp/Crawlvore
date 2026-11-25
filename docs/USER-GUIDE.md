# Crawlvora — Court Registry workspace

The sole online collection source is the Croatian Court Registry public v3 API. Existing local company records, source provenance and job history are retained. Web scraper jobs from old versions are cancelled rather than executed. CSV/JSON import and directory/registry exports remain available.

## Connection

In Settings, enter Client ID and Client Secret and apply them for the running session. Use Court Registry → Test connection, then authorize synchronization. For persistence across restarts, use the existing private `sudreg.private.json` in the user's application data directory (or the two SUDREG environment variables). Never commit credentials to GitHub. The desktop packages integrate the API client, not a shared secret. The scheduled refresh requires valid credentials and a running app.

## Existing data

The bundled original CSV contains 26,261 records and is seeded only once. Existing databases are not replaced. Reimport merges compatible OIB/MBS identifiers and conservative name/city/address matches; conflicting identifiers are not silently merged. Old sources remain visible solely as provenance, not as selectable online collection services. Import additional CSV/JSON through Import & Export.

## Synchronization

Use Court Registry to synchronize public bulk categories with the same snapshot ID, resume interrupted pages, browse records, compare completed snapshots and export. Official data updates compatible identity fields while retaining existing contacts. Tasks & Schedule provides the registry-only queue and weekday refresh.

Live credentials, complete synchronization, platform packaging and exact design parity must be verified before a production release.

## Data protection

Every normal launch acquires an OS workspace lock and creates a verified SQLite online backup before modifying an existing database. Backups are stored in the workspace's `backups` directory and are never automatically deleted. A failed backup prevents opening the workspace for changes. First-time seed import and its completion marker commit atomically. Differing incoming nonempty field values are retained in the local alternate_values table. These safeguards do not guarantee survival of disk failure: keep independent encrypted backups. For recovery, close all instances, copy the entire current workspace to a separate location, then restore a verified backup into a new workspace; never overwrite the only original. Backups contain business/contact data and must remain private.

Manual CSV/JSON imports also create a verified backup before writing. Company Profile → Source Links displays preserved alternative values and their source; directory JSON export includes these values as well. Directory exports are not complete workspace backups (they do not restore registry snapshots, all provenance or application state). Use the verified SQLite backup for complete workspace recovery. JSON import remains a directory import, not a database restore.

## Verified offline recovery

From the source distribution, run `python tools/recover_workspace.py /path/to/backup.sqlite3 /path/to/new-workspace` (new directory must not exist; use a local filesystem supporting hard links, e.g. NTFS or ext4). The utility checks full SQLite integrity, foreign keys and required tables, then creates and verifies a separate database. It never replaces the original database or backup. To inspect the recovered workspace using the source application, run `python tvrtk_scraper.py --data-dir /path/to/new-workspace`. Private credentials are not restored. The packaged desktop recovery UI and workspace selector are not implemented yet. Process-exit testing is not physical power-loss testing. Keep independent backups.
