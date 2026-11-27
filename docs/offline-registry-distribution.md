# Offline registry distribution

Production release acceptance requires the same verified official all-status snapshot in every supported Windows and Linux package: Portable-HR-Full.exe, Setup-HR-Full.exe, .deb and .tar.gz. Fresh workspaces initialize directly from the included SQLite database; no OAuth credentials or download are needed for offline searches. Registry-bearing builds package the compressed database, declared size, SHA-256 and manifest together, and the native smoke tests must verify the installed snapshot against the build's expected checksum. Existing workspaces are never replaced; use the explicit transactional integration procedure with a verified backup for upgrades.

The database is distributed in GitHub release packages, not committed as a large binary to Git history. The full snapshot must be finalized, all categories verified, and redistribution scope reviewed before publication. Public preview builds are not full-registry releases. Current private distribution guard remains in force. Do not include local credentials, private workspace data or backups. Each release asset must remain below 2 GiB; if any exceeds this limit, publication fails rather than silently omitting the data.

Sources: https://data.gov.hr/ckan/dataset/sudski-registar and https://sudreg-data.gov.hr/api/javni . 
