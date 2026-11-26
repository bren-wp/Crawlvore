# National database packaging

GB uses a read-only, independently indexed Companies House database. The Croatian workspace remains separate. The initial international UI supports GB name-prefix / exact company-number search, paging and original fields. RS is explicitly unavailable until the APR schema and import are verified.

After documented distribution review, stage a verified GB snapshot using:
`python tools/prepare_national_bundle.py GB-verified national-data/GB --distribution-reviewed`

Set CRAWLVORA_NATIONAL_BUNDLE=1 for reviewed native packaging. Both the onedir worker and Windows onefile worker accept the staged national-data directory. Standard CI preview builds do not contain actual national data. The release workflow still needs a verified artifact input and end-to-end distribution-size testing before publishing. The first GB query extracts the compressed database locally; subsequent searches reuse the content-addressed SQLite file. No credentials are included. Do not commit large binary files or unreviewed datasets to Git. Existing Croatian workspaces are not changed.
