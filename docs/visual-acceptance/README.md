# Native visual acceptance

Reference images were captured from the existing running application UI using the same six-company synthetic fixture and a 1280 × 700 viewport, device scale factor 1. The native candidate was captured from actual Windows client pixels at the same dimensions. The reference is the rebranded original renderer, not a reconstruction of user screenshots. Native captures are in ../screenshots-native. No production data was used.

Run the exact comparator:

    python tools/native_pixel_compare.py docs/visual-acceptance/reference-1280 docs/screenshots-native visual-diffs

The command returns 1 for any difference and rejects unequal image dimensions. It creates a lossless RGB difference image per page and report.json. --report-only is for measuring development progress, never final acceptance. The initial measurements are in before.json. The current report is in ../screenshots-native/comparison.json.

The current candidate fails strict acceptance on all seven pages. This is diagnostic evidence, not a complete feature or release acceptance certificate. Further work must cover all dialogs, interactive states, native fonts, gradients, rounded surfaces, charts, DPI and operating systems. Screenshots from different rendering stacks and actual OS DPI settings must be aligned; never resize or mask away differences to claim exact parity. The current evidence is limited to one Windows client viewport and a synthetic dataset. The 960×600, 800×540 and 640×420 checks test access to content, not exact pixels.

Keep the reference renderer until native feature parity and visual acceptance are established. Stable native production release must not be described as fully verified on the basis of the current smoke tests or visual reports.

## Intermediate milestone

Use --max-changed-percent 30 to check that each of the seven pages has at most 30% differing RGB pixels. This is a separate development milestone; the default gate remains zero. The latest candidate still fails both gates. Procedural card surfaces, native charts, filters, task indicators and the original launcher assets are now integrated. Reference PNGs remain unchanged.

## Layout geometry iteration

Wide windows use an overlay vertical scrollbar in the outer margin, retaining the reference content width. Narrow windows retain reserved scrollbar space and the responsive card layout. Dashboard card dimensions, chart proportions and six-row chart spacing were corrected; shared typography and progress-bar thickness now more closely follow reference CSS. The experimental custom ttk image-button renderer was excluded because its initial smoke run did not complete promptly. The measured candidate still fails the 30% gate; data and analytics show small regressions. Real DPI and cross-platform pixel acceptance remain open. No source reference images were changed.

## Native raster assets

The logo surface and navigation line icons now use bounded, supersampled RGBA PNG generation in the Python standard library. The runtime has no new graphics dependency. Keep the existing ttk button control layout: the experimental nine-slice button element caused invisible labels initially and excessive CPU activity during full-window resize testing even after fixing label stacking. It is not shipped. The accepted icon-only candidate completed the seven-view capture and responsive checks, but the strict 30% and exact RGB thresholds remain unmet. Tiny RGB regressions are recorded, not masked. Reference captures remain unchanged.
