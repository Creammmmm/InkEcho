# Blue branding validation

Date: 2026-10-13. The user supplied the microphone-and-paintbrush artwork through
[this image reference](https://chatgpt.com/s/m_6acd183cd9648191a6977d2145a646ba).
`src/inkecho/assets/inkecho.png` preserves the original 1254 × 1254 PNG byte for
byte; no redrawing, recoloring, cropping or background removal was performed.

Original and repository copy SHA-256:

```text
11b84a241495717675d216758ed46a5793bce69ae8765e73cd4ab2ab71e0bff9
```

Qt smooth scaling produced PNG icons at 16, 24, 32, 48, 64, 128, 256 and 512
pixels. The application/window icon, sidebar, tray, desktop notifications,
desktop launcher and AppImage all reference this artwork or its resized PNGs.
The AppImage `.DirIcon` links to `inkecho.png`; the former application SVG has
been removed. The original SVG and a 16-pixel PNG remain only as migration-test
fixtures.

The theme uses white cards, an ice-blue background, navy text and royal-blue
primary buttons, selection, focus borders and progress indicators. Error red
remains distinct. Calculated sRGB contrast ratios are 12.2:1 for body text,
5.4:1 for muted text, 6.62:1 for white primary-button text, and 8.1:1 for selected
navigation text. These measurements cover those color pairs, not a complete
accessibility certification.

## Safe desktop icon updates

The desktop integration module recognizes exact SHA-256 hashes of the eight
previous InkEcho assets. It upgrades an old PNG only when the launcher has the
InkEcho managed marker and the old icon matches the corresponding known hash.
It then removes the matching retired SVG so desktop icon lookup cannot prefer
the old artwork. Unknown or symlinked icons are preserved and reported as a
conflict. Configuration and keyring contents are not part of icon migration.

```sh
.venv/bin/python -m pytest -q \
  tests/test_integration.py tests/test_ui.py tests/test_notifications.py
```

Result: **32 passed**. This includes migration from real previous icon fixtures,
rejection of unrelated icons, preservation of user changes and existing desktop
launcher checks. Ruff lint and formatting passed for all seven branding code and
test files.

## Visual acceptance

All nine settings pages were rendered with an isolated, newly initialized
configuration and no API keys:

```sh
QT_QPA_PLATFORM=offscreen XDG_SESSION_TYPE=x11 .venv/bin/python -m inkecho \
  --config-dir /tmp/inkecho-branding-fixture/config \
  --data-dir /tmp/inkecho-branding-fixture/data \
  --screenshot-dir build/branding --quit-after 0.1
```

The source launch reported nine screenshots and a visible offscreen window. Each
of `build/branding/page-01.png` through `page-09.png` was visually inspected:
the supplied blue artwork appears in the sidebar, the palette is consistent,
Chinese labels remain readable, and longer forms retain their scrollbars.
These are source/offscreen visual checks, not proof of native desktop icon-cache
refresh or of the final AppImage. Final package and installed-icon checks are
recorded by the release acceptance workflow.
