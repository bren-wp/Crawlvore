# Croatian desktop release policy

Only HR Full and HR Online are built, for Windows and Linux. Each has installer and portable/archive variants. Full must contain the verified Croatian registry snapshot; Online starts empty in a fresh workspace. Never overwrite an existing workspace. Release checks must include source identity, actual package smoke tests, snapshot counts and checksums, and asset size/digest checks. Raw snapshot 1370 is preserved separately in the private data release. No credentials in distributable packages. Private distribution is not authorization for public redistribution.

Windows Setup is built with NSIS, in Croatian, with a per-user installation and optional desktop shortcut. The actual installer must pass isolated install, reinstall, payload checksum and uninstall checks with a preserved data sentinel. The existing private Inno build remains a separate owner-only fallback until migration is verified on real existing installations. No end-user Python installation is required.

Database-free HR Online publication has an independent, audited release job. HR Full remains restricted to private repositories, and a public repository skips the private snapshot build rather than uploading it. No unsigned automatic updater may execute downloaded code.
