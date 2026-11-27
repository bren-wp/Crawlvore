# Crawlvora design contract

The only approved design references are the ten English dark desktop concepts listed in `branding/reference-lock.json`. All earlier v7/v8 fixture baselines are retired. The original eight new concepts are preserved byte-for-byte; Analytics & Reports and Settings are cropped as separate screens from the generated two-window concept. Upload `Crawlvora-Design-References-10.zip` to the existing PR branch root to trigger the verified import workflow, or run `python tools/import_design_references.py Crawlvora-Design-References-10.zip` locally.

References are design mockups, not screenshots or proof of features. Do not use invented growth, API latency, contact details, queue status or totals as runtime data. Preserve native Windows/Linux titlebars, accessible keyboard controls, real data, the existing safe scraping policy and permission controls. The generated references are dark and English; light/Croatian views are derived and still require review. Match the layout, colors, iconography and spacing of every window, with actual data and appropriate empty/error/loading states. Do not display an unsupported control as operational. 

Actual capture workflow renders the application separately. Its output is not an approved reference and must not overwrite the original PNGs. Exact pixel matching requires aligned viewport/native chrome, a frozen synthetic data fixture and review of layout differences. Current comparison intentionally reports missing or non-comparable images instead of silently resizing or rebasing them.

The redesign introduces the shared shell, compact tables, mint line icons, dark gradients, reorganized directory, collection and extraction screens, analytics from real locally recorded values, and settings for existing theme, language, registry and scheduling controls. Remaining discrepancies include unsupported options in the conceptual artwork, additional dialog states, precise native chrome and reference-level visual alignment. Production release is blocked if the ten original PNGs are missing or changed.

Registry-only scope: the collector and studio design concepts are retired; preserve the original locked reference archive for provenance, but compare only the eight remaining screens. No third-party scraper navigation or fake controls are permitted. Settings gains private OAuth credential input; exact visual acceptance remains pending.

## Phase 4 ? live layout acceptance, increment 1

The approved reference lock is present, but the original reference PNGs are missing from the current checkout. Do not treat README images, current screenshots or fixture baselines as replacements. Exact reference acceptance remains blocked until the original archive passes its locked SHA-256 verification.

The live worker layout regression checks use a disposable synthetic catalog, both languages, both themes, six viewport sizes (360x300, 390x844, 768x480, 1024x600, 1120x720, 1440x900), all eight live views and company dialog dimensions. Before the fix, 40 view combinations showed overflowing telephone cells. After permitting contact and action text to wrap, 192 screen cases and 24 dialog checks passed with no detected visible cell overflow, page horizontal overflow or JavaScript errors. This is a browser layout test, not native DPI or pixel-perfect certification. The national view is exercised without a downloaded UK catalog.

Run python tools/layout_acceptance.py layout-evidence after compiling the frontend. The JSON report records the executed matrix and detected failures. Quality CI now runs this gate.

## Phase 4 ? increment 2

The active navigation button exposes aria-current and the UK subview retains the directory highlight. Company dialogs have accessible names; the UK profile uses a responsive property grid with wrapped long names instead of a table scrolling container. The live layout matrix now adds effective viewports and Chromium device scale factors for 125%, 150%, 175% and 200%, with both themes and languages, synthetic verified UK data, profile tabs and keyboard dismissal. These browser emulations are not OS-level DPI or native WebView acceptance. The layout report is retained in quality evidence, and strict production comparison must verify the original locked PNG hashes before comparing pixels.

## Phase 4 handoff

The responsive acceptance matrix passed 320 screen cases and 80 dialog cases on the preceding revision. Reference PNGs remain absent; exact visual acceptance and native DPI certification remain open. The pixel comparison now rejects changed reference bytes even outside strict production mode and cannot pass an empty comparison in strict mode. Do not waive this gate when moving to security work.
