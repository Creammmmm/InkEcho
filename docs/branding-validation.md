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

## Replacement artwork, 2026-10-18

The user supplied a new [blue microphone-and-calligraphy-brush icon](https://chatgpt.com/s/m_6ad3c3ff06c8819192fdb6247d09c26d).
The original PNG replaces `src/inkecho/assets/inkecho.png` byte for byte:
1254 × 1254, RGBA, SHA-256
`42449d99f4fb0f87bc14aaa89e68f118ef8568bdb53be8a1fc5bc177a45947a5`.
The transparent outer area and translucent pixels are preserved; the corner
alpha is 0. No cropping, redrawing, recoloring or background removal was applied.
The earlier sections above describe the previous artwork and historical checks.

PySide6 6.12.0 `QImage.scaled(size, size, KeepAspectRatio,
SmoothTransformation)` followed by `save(path, "PNG")` regenerated all eight
existing sizes (16, 24, 32, 48, 64, 128, 256, 512). Repeating this operation on
the original produces pixel-identical images at every size. The 256-pixel PNG
SHA-256 is `f694df1872697f875d6e4c226e4f9dd39e20c2243dc3a10570330807600b7d2f`.
It was visually inspected: the microphone, brush, ink stroke and rounded white
background remain intact. Existing window, sidebar, tray and notification
references use the original PNG. Desktop integration uses all eight sizes;
AppImage construction copies the 256-pixel PNG and links `.DirIcon` to it.
No reference paths or application palette needed changing.

Desktop repair also recognizes the exact eight retired blue PNG hashes. This
permits an explicitly requested repair of managed launchers without treating the
old application icon as an unrelated file. The managed-launcher requirement,
unknown-file rejection and symlink protection remain intact. The old 16-pixel
PNG is retained only as a real migration-test fixture.

Resource checks used Qt to verify PNG decoding, exact dimensions, alpha support,
and pixel equality with a fresh smooth resize. Focused validation:

```sh
.venv/bin/python -m pytest -q \
  tests/test_integration.py tests/test_ui.py tests/test_notifications.py \
  tests/test_packaging.py
.venv/bin/ruff check src/inkecho/integration.py tests/test_integration.py
.venv/bin/ruff format --check src/inkecho/integration.py tests/test_integration.py
```

Result: **71 passed**; Ruff lint and format checks passed. Integration tests use
isolated temporary paths and cover previous-blue migration and refusal to replace
an unowned previous-blue icon, alongside existing unknown-file protections.
These are source-resource and automated checks. No installed files, icon caches,
user configuration or existing AppImage were changed. A newly built package
still requires the same-hash Ubuntu 24.04 and 26.04 acceptance before delivery.
