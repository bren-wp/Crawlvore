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
