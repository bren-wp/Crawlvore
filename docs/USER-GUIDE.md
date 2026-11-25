# Crawlvora 8.0.0

**Business Data Intelligence** · Web scraping, organized company records, and reusable projects.

Crawlvora combines a permission-aware HTTP web bot, a visual extraction studio and a searchable business directory. The included dataset contains 26,261 original company records. Data is stored locally in SQLite.

## What’s new in 8.0

- Extraction suggestions are ranked by recognized business fields and coverage, rather than repetition alone. Supports mixed classes, Croatian/English headings, semantic attributes and label/value pairs. Unrecognized fields remain unmapped; always confirm the preview.
- Stronger network validation rejects multicast and reserved addresses, including IPv6 multicast.
- Added 7 regression tests, offline dependency/source inventory, fixed-reference screenshot comparison and four-hour local endurance workflow.
- See `AUDIT.md` for actual results and remaining production blockers. Windows executables and a full vulnerability audit are not yet verified.

## Earlier changes (7.0)

- Compare completed registry snapshots by canonical JSON row content, independent of row ordering. Counts preserve duplicates and identify affected MBS values per category. A changed row counts as one removal and one addition; incomparable categories are flagged.
- Scheduled registry jobs retry only transient network/server failures, at 15 and 60 minutes, for at most three attempts. Access denial and invalid credentials are not retried.
- Public HTTPS connection transport validates DNS results at connect time, connects directly to the approved IP, keeps hostname-based TLS verification, and disables proxies.
- HTML table header mapping and card-level attributes improve automatic business field detection. Preview before collecting.
- 32 isolated UI captures across light/dark, desktop/mobile and the company detail dialog. Test data is clearly identified by filenames.
- Windows packaging adds portable/installed runtime tests and installer/uninstaller verification. Windows build and production API access are not yet verified.
- See `AUDIT.md` for exact test coverage and outstanding risks.

## Earlier changes (6.0)

- Optional Playwright Chromium renderer for authorized same-origin JavaScript websites; no CAPTCHA or access-control bypass. Select the renderer in Scraper Studio or Web Bot. Install the browser once with `python -m playwright install chromium` in the same Python environment. For the Windows launcher: `.venv\Scripts\python.exe -m playwright install chromium`.
- More reliable semantic field detection across multiple cards, including contact links, OIB/MBS attributes, postal codes and industry.
- Persistent job queue for Tvrtke.hr, custom HTML and registry sync. Authorization must be confirmed. API-token jobs remain direct-only; queue stores no token or URL query strings.
- Opt-in weekday schedule in local time; Crawlvora must remain running. One attempt per eligible day; if no new snapshot is available, no redundant full download. Manual retry remains available. Interrupted jobs are marked interrupted; registry checkpoints remain available.
- Company change history for locally observed field changes from v6 onward; not historical records from the government-only API. Identifier matching is conservative, not a fuzzy automated merge.
- Category exports: CSV, JSONL, write-only XLSX (text identifiers, auto filters), XML (typed JSON field values), SQLite-compatible SQL (raw JSON payload). SQL does not target MySQL or Oracle.
- Seven workspaces with the existing mint/obsidian brand. See `branding/` for Chromium screenshots rendered using isolated fixtures. These are not production API screenshots or pixel-diff certification.
- Windows build workflow now includes the Playwright browser. Actual Windows compilation and execution still need a Windows runner.

Verification and limitations: see [AUDIT.md](AUDIT.md). Keep the private `sudreg.private.json` outside public distributions and rotate previously exposed credentials.

## Quick start

- Windows: extract the archive and run `START-WINDOWS.bat` (Python 3.10+ required).
- Linux: `bash start-linux.sh`.
- Manual: `python -m pip install -r requirements.txt` then `python tvrtk_scraper.py`.
- Open `http://127.0.0.1:8765` if the browser does not open automatically.

Existing installation: stop Crawlvora, back up the whole `data` directory, and copy it into the new application folder before launching. The project table is created automatically. The original CSV seed is imported only once into a new database.

## Scraper Studio

1. Open **Scraper Studio**. Enter the public HTTPS URL and confirm permission, or paste/upload an authorized HTML sample (up to 2 MB).
2. Click **Prepoznaj strukturu**. Crawlvora suggests repeating CSS selectors and common business fields.
3. Select a record selector, choose an active field, then click an element in the sample to map it. Edit CSS selectors manually if needed; `a::attr(href)` extracts an attribute.
4. Refresh the preview (up to ten actual sample records). Apply the configuration to Web Bot, set pagination, confirm permission and start.
5. Give the configuration a name and save the project. API tokens and permission confirmations are not saved. Do not put secrets into URL query strings.

The editor displays extracted elements as inert text, not a live embedded third-party website. HTML detection is heuristic; JavaScript-only content requires the optional Playwright renderer; login-protected pages are not supported. The renderer restricts requests to the same origin, so some sites relying on third-party CDNs will not load.

## Sources

- **Tvrtke.hr**: dedicated HTTP adapter, with a search term and page range. CLI: `python tvrtk_scraper.py --crawl --term a --delay 3` (use only with authorization).
- **CompanyWall.hr**, **Company.hr**: configurable authorized JSON API connectors, requiring the actual endpoint, response mapping and credentials where necessary. No access to a paid API is included.
- **Other websites**: authorized public HTTPS HTML using CSS selectors and field mapping.
- **Other APIs**: authorized JSON endpoints, nested response paths and field mappings.
- CSV/JSON import is available for existing datasets.

External connectors have a maximum of 100 pages per run, a 3–60 second configured request interval (longer robots delays are respected), bounded responses, public HTTPS checks and no redirects. Requests stop on denied or rate-limited responses. The HTML preview requires an accessible robots.txt and does not bypass authentication or anti-bot protections. Live third-party compatibility was not verified in this release.

### Pagination

| Mode | Example |
| --- | --- |
| Page | `https://example.org/list?page={page}`, start 1 |
| Offset | `https://example.org/list?offset={offset}`, start 0, step 20 |
| Next link | `a[rel=next]` (HTML, same origin only) |
| Cursor | `meta.next_cursor` response path, `cursor` request parameter (JSON) |

The bot stops at the page limit, when a later page is empty, when a next link/cursor is missing, or when results repeat. Existing committed pages remain in the database if stopped. The dedicated Tvrtke.hr adapter can resume completed company profiles; generic sources can be rerun with deduplication, but do not have a durable per-page checkpoint.

## Organized exports

Search and filter the directory by city, contact availability and source. Export all or filtered results as CSV or Excel. Full JSON includes source provenance. XLSX includes 22 named columns, filters, frozen headers and explicit text cells (OIB and postal-code leading zeros are preserved, and formulas are not executed). Unknown fields are left empty. Company records are merged by validated OIB or normalized name and city; name-only matching may require manual review.

## Windows desktop packages

The source contains a desktop window mode using pywebview / Microsoft Edge WebView2, PyInstaller packaging and an Inno Setup installer recipe. On Windows x64 with Python 3.12 and Inno Setup 6 installed:

```powershell
powershell -ExecutionPolicy Bypass -File windows/build.ps1
```

Expected outputs: `dist/Portable.exe`, `dist/Setup.exe`. A GitHub Actions workflow can build the same files on a Windows runner and upload them as workflow artifacts. Edge WebView2 Runtime is required. In desktop mode, data is kept in `%LOCALAPPDATA%\Crawlvora` (including when launched from Portable.exe); the portable executable does not require installation but is not a self-contained portable data directory. Source mode keeps data in the project's `data/` folder.

**Windows binaries were not compiled or tested in the Linux development environment.** The archive includes the actual source and build scripts, not prebuilt EXE files. The desktop window wraps the web UI and is not a native WinUI implementation.

## Verification

Run `python -m unittest discover -s tests -v` and `node --check static/app.js` (Node optional). Fourteen automated tests passed in development, including project persistence, HTML discovery, next-link and cursor pagination, denied access and XLSX safety. The local HTTP API loaded the 26,261 seed records. The final browser rendering and Windows packages remain unverified.


## Sudski registar — javni API v3

1. Stavite privatnu datoteku `sudreg.private.json` uz `tvrtk_scraper.py` (ili uz Portable.exe). Možete je staviti i u lokalni direktorij podataka. Alternativno koristite varijable okruženja `SUDREG_CLIENT_ID` i `SUDREG_CLIENT_SECRET`. Nemojte stavljati tajne u GitHub, ZIP za javnu distribuciju ili javne logove. Datoteka je običan JSON, nije kriptirana; ograničite pristup na vlastiti korisnički račun. Ako su tajne već podijeljene, preporučuje se rotacija.
2. Pokrenite aplikaciju, odaberite **Sudski registar**, potvrdite dopuštenje i pokrenite sinkronizaciju. API adrese su unaprijed definirane. OAuth2 token se dohvaća i obnavlja automatski, s provjerom TLS certifikata.
3. Aplikacija preuzima javnu OpenAPI specifikaciju, iz nje otkriva skupne GET metode koje podržavaju snapshot_id te preuzima najnoviju snimku s istim snapshot_id. Metode koje zahtijevaju pojedinačni subjekt ili druge obavezne filtre preskaču se. Ne koristi masovno detalji_subjekta. Povijesni/državni podaci nisu dostupni preko javnog API-ja.
4. Svaka uspješno preuzeta stranica i napredak spremaju se u SQLite transakciji. Ako se proces prekine, sljedeća sinkronizacija iste snimke nastavlja od posljednje spremljene stranice. Ako je dostupna novija snimka, kreira se zaseban zapis; stara nepotpuna snimka ostaje označena kao nepotpuna.
5. U prikazu kategorija možete pregledavati originalne JSON retke i izvesti cijelu kategoriju u JSONL. Poslovni imenik i postojeći CSV/Excel izvoz koriste osnovne mapirane podatke. Mapiranje je heurističko i nije potvrđeno na stvarnim odgovorima; puni izvorni zapisi sačuvani su odvojeno.

CLI: `python tvrtk_scraper.py --registry-sync --registry-limit 500`

Dokumentacija: https://sudreg-data.gov.hr/api/javni/dokumentacija/open_api i Upute za razvojne inženjere v3.0.0 (26.3.2024).

### Stanje provjere

19 lokalnih automatiziranih testova uključuje simulirane API odgovore, paginaciju, nastavak i odbijanje različitih snimki. Produkcijska OpenAPI specifikacija i autentikacija nisu mogle biti preuzete u razvojnom okruženju (DNS/mrežno ograničenje). Stoga nije potvrđena kompatibilnost stvarnog odgovora ni potpuni dohvat svih kategorija, a stvarni podaci registra nisu uključeni. Windows EXE build i stvarni prikaz u pregledniku nisu potvrđeni.
