# Private local offline preview

Use a fresh checkout with the captured HR raw SQLite and verified GB directory. Do not publish the staged files to the public repository.

`python tools/stage_private_preview.py HR.sqlite3 GB-directory CHECKOUT --private-local-preview`

The staging command copies and verifies HR pages, materializes available official names without inventing missing names, and compresses the complete GB snapshot. HR remains explicitly incomplete.

Windows: set CRAWLVORA_PRIVATE_PREVIEW=1, CRAWLVORA_REGISTRY_BUNDLE=1 and CRAWLVORA_NATIONAL_BUNDLE=1 before invoking windows/package-native.ps1 with its usual build prerequisites. The worker smoke validates both embedded snapshots. Existing workspaces are never overwritten. The production workflow retains strict full-snapshot and private-distribution gates. Local previews must not be presented as production releases. Linux package integration still requires actual build and acceptance on Linux.
