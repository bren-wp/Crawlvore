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

## Local gradient sampling

Native card labels, nested panel frames and chart canvases now sample the local gradient color instead of displaying uniform panel-colored rectangles. Styles inherit their existing font, foreground and control semantics. Sampling occurs after layout settles and pending callbacks are cancelled on destruction. The original controls remain interactive; nested card decorations are excluded. All seven views reduced changed pixels at the measured 1280x700 viewport. The 30% gate is still failing; no production readiness or DPI equivalence is inferred. Reference images remain unchanged.

## Gradient intervals and header accent

The card renderer now derives its band boundaries from RGB channel rounding instead of generating 48 fixed polygons. It retains live native controls and bounded caches. The procedural header raster approximates the two layered reference gradients and is cached by viewport width (four entries, maximum width 4096). It does not embed reference images. Local measurement at 1280x700 shows fewer differing pixels on all seven views; 30% and exact acceptance remain unmet. Physical DPI and cross-platform pixel equivalence have not been verified. No production data was used.

## Deterministic RGB acceptance and pixel-center raster

The Windows hosted-runner capture failure was corrected without rescaling its output. Run 46087547789 subsequently captured all seven views at 1280 × 700 on both platforms. The later Windows run 46087701940 also captured three native dialogs. Its seven-view changed-pixel percentages were 75.740848, 72.910491, 77.892969, 78.038170, 71.007366, 71.115179 and 78.890179 in comparator order. This does not pass 30%, and differences in renderer configuration prevent treating the previous local Windows evidence as a controlled before/after benchmark. The Linux responsive check in the same run failed for registry at 800 × 540; it is not accepted.

The next candidate renders rectangular gradient interiors at physical pixel centers using runs of identical RGB pixels, retaining the existing supersampled corner patches and live widgets. The eight-entry compressed cache and two-million-pixel allocation limit are explicit; larger surfaces use the previous canvas polygon renderer. A local isolated check of the run-generation algorithm (excluding PNG encoding and GUI) matched direct analytical evaluation in fifteen palette/size cases plus 600,000 pixels at 1000 × 600. Full application performance and visual acceptance still require CI evidence.

Capture tests now request Tk scaling corresponding to 96 DPI, record actual Tk scaling, original scaling, font family, OS and Tk version, and require two consecutive identical RGB frame hashes. This is a controlled test configuration, not physical monitor DPI verification. Window sizes and reference files remain unchanged. The strict acceptance threshold is not relaxed; Linux comparisons against Windows references remain diagnostic. The viewport reconciliation fix and new capture procedure must pass CI before claiming the responsive issue resolved.

## Regional error investigation and visible Windows captures

Run 46090693206 completed the Windows and Linux GUI smoke and RGB evidence jobs. The Linux diagnostic changed-pixel percentages in comparator order were 67.205022, 67.533817, 72.418192, 72.722210, 65.216183, 61.393973 and 71.614397. The Windows job reported 74.372210, 72.912054, 77.587612, 77.790402, 70.386384, 70.432478 and 78.839286. These are historical measurements, not a 30% pass.

In all seven Windows images, the four rightmost regions (x=960 through 1279) had mean maximum channel errors above 217 on a 0–255 scale. This consistent anomaly is compatible with clipped or padded captures from an undersized hosted display; it is not proof of a rendering defect or of clipping. Do not treat those measurements as reliable visual acceptance until fully visible captures are verified. The Windows CI now explicitly selects a supported larger desktop mode, with no registry persistence, and capture rejects any client extending beyond the primary display or mismatching actual client geometry. If the hosted display cannot support the requested mode, the job fails rather than reporting a fabricated score.

The next candidate shades inactive navigation buttons, classic sidebar labels and the brand canvas using their local gradient colors. Native table body backgrounds use the local card color, with the original selected and hover states retained. This is a local color approximation for opaque controls, not true transparency. Table font size and default row height follow the reference CSS values of 12 and 39 pixels. The button renderer remains the standard native implementation; a rounded-image replacement has not been accepted on performance grounds. These changes and their added GUI tests require new CI evidence before a visual improvement can be asserted.

## Subpixel gradient correction (PR #19)

Verified Windows CI 46094476278 used the fully visible client capture protocol, preserved original reference PNGs, and passed the RGB evidence job (diagnostic, not acceptance). The strict changed-pixel percentages in comparator order were 65.690513, 64.323326, 69.205692, 70.396540, 62.661161, 58.965290, 70.455692. The 30% milestone remains unmet. The independent evidence archive was artifact 15243056127.

A comparison of the actual reference PNGs revealed an eight-by-eight ordered threshold pattern in clean sidebar gradient pixels. The procedural model uses bit-interleaved x/y phases, a pixel-center 145-degree linear gradient and floor(channel + phase/64). In a fixed diagnostic sample of 43,515 sidebar pixels (x=2..7, y=21..689, plus x=11..219, y=501..689), the ordinary mathematical rounding model matched about 41.13% and the ordered quantization model matched 42,990 pixels (98.79%). This is a local model check against the reference, not a measured improvement of the full new GUI. It is not a mask or relaxed acceptance threshold. Every pixel remains counted by the comparator.

The candidate renderer preserves fractional CSS color-mix endpoints (panel 55%, base background 45%) before quantization, aligns phases to the client viewport, reuses eight-pixel interleaved runs, and applies the same phase to chart background crops and antialiased card corners. Caches and allocations are bounded; large surfaces retain the previous fallback. Opaque native text and controls remain functional and use approximate local solid colors, not true transparency.

An isolated local reproduction of the interleaved algorithm matched the direct mathematical model in 45 configurations (147,000 pixels) and 30 region crops. A cold 1000 × 600 low-contrast surface took 133.04 ms including PNG encoding; the direct per-pixel Python model took 984.01 ms excluding PNG encoding. This comparison does not establish a performance improvement over the previous non-dithered renderer or a full-GUI resize benchmark. New CI must verify actual RGB outcomes, responsiveness and control behavior. No release or final visual acceptance is claimed here.
