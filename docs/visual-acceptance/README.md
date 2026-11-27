# Native visual acceptance

Reference images were captured from the existing running application UI using the same six-company synthetic fixture and a 1280 × 700 viewport, device scale factor 1. The native candidate was captured from actual Windows client pixels at the same dimensions. The reference is the rebranded original renderer, not a reconstruction of user screenshots. Native captures are in ../screenshots-native. No production data was used.

Run the exact comparator:

    python tools/native_pixel_compare.py docs/visual-acceptance/reference-1280 docs/screenshots-native visual-diffs

The command returns 1 for any difference and rejects unequal image dimensions. It creates a lossless RGB difference image per page and report.json. --report-only is for measuring development progress, never final acceptance. The initial measurements are in before.json. The current report is in ../screenshots-native/comparison.json.

The current candidate fails strict acceptance on all seven pages. This is diagnostic evidence, not a complete feature or release acceptance certificate. Further work must cover all dialogs, interactive states, native fonts, gradients, rounded surfaces, charts, DPI and operating systems. Screenshots from different rendering stacks and actual OS DPI settings must be aligned; never resize or mask away differences to claim exact parity. The current evidence is limited to one Windows client viewport and a synthetic dataset. The 960×600, 800×540 and 640×420 checks test access to content, not exact pixels.

Keep the reference renderer until native feature parity and visual acceptance are established. Stable native production release must not be described as fully verified on the basis of the current smoke tests or visual reports.
