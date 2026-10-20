# Overlay style and capture readiness repair

Date: 2026-10-20. This report concerns source behavior, not a new AppImage.

## Confirmed cause

A read of only the four display fields in the host's ordinary `config.json`
found `overlay_style=waveform`, `overlay_position=bottom-center`, opacity `0.9`
and duration `2.0`. No credential file or authentication value was read.
`MainWindow.update_state` previously showed an overlay on Wayland only when the
style was `siri`; it explicitly hid waveform and pulse overlays. In addition,
waveform and pulse painting did not draw preview text. An existing waveform
configuration therefore produced neither an overlay nor a visible draft on
Ubuntu 26.04 even when realtime preview signals arrived.

The source repair keeps all three user styles and displays each through the
existing display-only XCB host on native Wayland. All styles now have space for
status and draft text. The main settings application remains native Wayland.
The display protocol adds only a bounded Boolean capture-readiness field:
recording initially says that the microphone is starting, and changes to
listening only after the session reports actual samples. Terminal states clear
readiness and draft text. No clipboard, input method, target capture, speculative
keyboard output or changes to credential storage were introduced.

## Automated checks

Run from the checkout with the local development environment:

```sh
.venv/bin/pytest -q tests/test_overlay_host.py tests/test_ui.py
```

Observed result with the local file/thread permissions required by the existing
credential fixtures: **106 passed in 7.92 seconds**. The newly added tests cover
strict Boolean decoding, readiness clearing after cancellation, and all three
styles showing on the Wayland branch and receiving a draft. Ruff checks and
formatting passed for the changed overlay/UI files.

A restricted execution stalled in the pre-existing
`test_provider_page_persists_bundle_in_own_config_file`; it was stopped by its
owner. The same unmodified test passed with the ordinary local permissions
needed for its fixture. No assertions or product validation were weakened.

## Actual Ubuntu 26.04 source display observations

The private diagnostic tools and results are preserved under
`build/overlay-style-repair-r1`. They create their own configuration and browser
profile, use only the literal `Synthetic live preview`, send no keys, capture no
microphone audio and make no cloud requests. Browser cleanup uses the original
owner's `Browser.close` and natural process wait.

- `host-r1`: failed before a visible display acknowledgement. The follow-up
  standalone `host-diagnostic-r1` established that the development environment's
  XCB Qt plugin could not load `libxcb-cursor`. This is not evidence that the
  AppImage lacks the library: the previously accepted package includes it.
- `host-r2`: supplied the already accepted package's `usr/lib/inkecho` as the
  dynamic-library dependency path while importing the changed source. The
  waveform host acknowledged visible/exposed with 22 synthetic preview
  characters; an actual owned-widget screenshot, `host-r2/waveform.png`, showed
  the waveform and full preview text. A subsequent owned-browser focus guard
  failed, so this run is **not** a passing focus acceptance. Browser natural exit
  was zero.
- `host-r3`: a separate diagnostic required fresh continuous browser focus before
  displaying any overlay. Its first pre-display sample had
  `document_focused=false`, `field_focused=true`, and the main application's Qt
  active-window Boolean was false. The guard stopped the test before the display
  host was started. This establishes that a focus loss can occur before showing
  the overlay; it does not identify what caused that loss. Browser natural exit
  was zero. No other application was activated or inspected.

The failures above are retained as failures. They do not validate all styles,
focus preservation, real microphone accuracy, cloud-generated partials or a new
package. Actual all-style focus acceptance on Ubuntu 26.04 and Ubuntu 24.04 must
be completed in an available owned desktop target before making those claims.

## Three-style display-only follow-up

The portable helper `build/overlay-style-repair-r1/probe-portable.py` accepts an
explicit `--repo` and a fresh `--run` directory. In `--display-only` mode it never
starts a browser and makes no focus claim. With the same source and already
accepted package libraries, `host-display-r1/result.json` records all three
styles visible/exposed with 22 synthetic preview characters, cancellation to
zero characters, idle hidden, and natural display-host exit zero. Actual
owned-widget PNGs for waveform, pulse and Siri were inspected; each showed its
selected animation and the complete synthetic preview. This result explicitly
has `focus_validation_attempted=false` and no browser exit value. It establishes
actual display and clearing, while the independent focus limitations above
remain open. The fixed helper was handed off for Ubuntu 24.04 source validation;
that system's result is not yet claimed here.
