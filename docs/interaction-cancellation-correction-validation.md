# Quiet no-speech, task Escape and correction-template validation

Dates: 2026-10-22–23. Source changes on `codex/ubuntu24-input-pipeline`, starting
from `967cd1d` / 0.8.2. This report does not claim a new AppImage acceptance.

## Behavior

- Empty successful ASR text, whitespace-only text, zero-PCM `empty_recording`
  and the provider's explicit `empty` result use the existing `Failure.EMPTY` internal task classification,
  but present idle to the desktop and a non-popup status. They clear previews,
  cancel pending work and release task context; no text or polish request follows.
  Keeping the internal failure classification preserves existing statistics and
  controller API compatibility; it is not a desktop error notification.
- Authentication, network, timeout, malformed response and microphone failures
  are not reclassified as no speech. They keep their existing visible failures.
- A task-scoped `TaskEscape` owns only Escape cancellation. Xorg uses a separate
  X11 connection with passive unmodified-Escape grabs. Lock-mask combinations
  come from the actual `XGetModifierMapping`, including remapped Num Lock; a
  column shared with any real modifier is not ignored. No ordinary key event is selected, observed or logged. No
  GSettings binding is created or overwritten. Conflicting grabs are released
  and rejected. Each terminal state/disposal closes the connection, so an
  ordinary application crash also releases X-server-owned grabs.
- Qt Escape works when an InkEcho window has focus. Native Wayland now uses
  legitimate own-app Registry and task-lifetime GlobalShortcuts Portal sessions,
  not XWayland grabs. Source validation on actual Ubuntu26 confirms synchronous
  production peer-disconnect cancellation and subsequent idle Escape delivery.
  Initial permission, localized trigger display and the active key-release
  passthrough boundary are detailed in [native Escape validation](wayland-task-escape-validation.md).
  This is not a same-SHA AppImage or Ubuntu24 native Wayland support claim.
- Four built-in templates share expanded same/near-sound and near-shape
  correction rules with contextual examples, ambiguity checks, and preservation
  of names, numbers, dates, units, code and versions. Existing IDs, custom prompt
  files and the user's selected prompt are preserved.

## Automated checks

Run in the repository development environment:

```sh
.venv/bin/pytest -q tests/test_application.py tests/test_task_escape.py \
  tests/test_config.py tests/test_ui.py
```

**Actual result: 196 passed in 7.00 seconds**, original run 11393, natural exit 0.
Run used the ordinary host process environment because restricted sandbox runs
stalled in the existing credential-root test's `asyncio.to_thread`/selector wait
and an existing asynchronous UI test. No tests were weakened. Three owned
stalled sandbox runs were stopped only after verifying their exact PID and
command: initial run 93662, diagnostic run 27368 (15-second faulthandler stack
preserved), UI/config run 56038; all exited 143 after targeted SIGTERM. A separate
restricted run excluding the existing hanging credential-root case passed
117 tests, 1 deselected. These are unit/Qt offscreen checks, not physical key,
physical microphone or authenticated cloud checks.

Added assertions cover all recording/transcribing/polishing/injecting states,
stale deferred shortcut arms, release before cancellation callback, rearming,
ordinary/modified/idle keys, shortcut conflicts, no Xorg API use on Wayland,
quiet empty results, actual-error visibility and custom-template preservation.
Existing cancellation, task replacement and late-reply tests remain in the run.

After review, zero-PCM handling and dynamic lock masks were added. Targeted
follow-up checks passed **11 tests, 110 deselected**: quiet empty/whitespace,
explicit provider empty, zero-PCM termination, genuine provider-error visibility,
remapped/shared lock modifiers and an already-selected built-in template reopened
from disk. The first expanded run reported 198 passed / 1 failed because the new
fixture incorrectly read `settings.json`; the product uses `config.json`. Fixing
that test path made the targeted checks pass. No product check was relaxed. The
coordinator owns the final complete clean-HEAD workflow; do not infer it from
these focused results.

Ruff lint/format checks passed on the changed module files. Real model spelling
correction quality is **not measured**: no real credentials or cloud requests
were used, and prompt text assertions do not prove a model will follow it.

## Actual desktop probe

`scripts/validation/task_escape_probe.py` opens an isolated, separate Qt target
process in a dedicated unlocked Xorg session. It checks that an ordinary `a`
reaches the target, Escape cancels a background guard without reaching that
window, idle Escape is delivered afterward, and focus remains on the owned
window. It never searches for or types into user documents. The target is closed
through its own normal control pipe.

```sh
QT_QPA_PLATFORM=xcb python scripts/validation/task_escape_probe.py \
  --package-root /absolute/runtime/packages-or-source-root \
  --output /absolute/isolated-output/escape.json
```

Actual Xorg desktop result: **passed**, dedicated Ubuntu 24.04 VM, source
module (not a new application package). Original SSH execution completed
naturally with exit **0**, elapsed **0.864 seconds**. Raw results are retained at
`build/ubuntu24-input-pipeline/escape-actual-r1/{escape,execution}.json` and
`stdout.txt` / `stderr.txt`; guest originals remain in
`/home/inkecho/inkecho-escape-repair-r1/`. The source was frozen and SHA-checked
before transfer and again remotely:

- `platform/escape.py`:
  `e2ac159cfaaf500421009e57cf45f9e5f867d2263d01036f882358194930460e`
- Probe:
  `a86836070f397fdf5d3b5d5197befa8b782e5f3f9b7217ac855dfbb5d8f13cd4`
- Frozen source archive:
  `5ccc37bae5bd3c14bb51ce2f0f53bc40d4942a099ca04a701751086b6fad7a21`

The actual GNOME session was `x11`; selected GNOME environment was used without
an IM override (`GTK_IM_MODULE` unset, `QT_IM_MODULE=ibus`,
`XMODIFIERS=@im=ibus`). The unchanged already-accepted 0.8.0 runtime supplied
Python/PySide dependencies, while the recorded Escape module originated from the
frozen source override. This is deliberately a **source-module desktop check**.

The separate target process PID 3709 received ordinary `a`, did not receive the
active Escape consumed to cancel the background guard, received idle Escape
afterward, and retained focus. The grab was released and the owned target exited
**normally with 0** through its stdin control pipe. No physical keyboard or user
application was used. Existing conflicting grabs and remapped lock columns are
covered by unit checks, **not by this actual desktop probe**. GUI ownership was
explicitly transferred back to the CLI validation agent after completion.

A negative run on a declared Wayland session also saved `ok:false` and the
expected explicit Xorg-required error before opening a display:
`build/ubuntu24-input-pipeline/escape-portal/xorg-probe-wrong-session.json`.
This verifies error-report persistence, not Wayland cancellation support.

A new package must separately pass the normal same-SHA Ubuntu 24.04 / 26.04
acceptance gate before delivery.

## Wayland API investigation

The official [GNOME Shell implementation](https://github.com/GNOME/gnome-shell/blob/main/js/ui/shellDBus.js)
restricts private accelerator calls to expected desktop services; InkEcho must
not impersonate them or enable unsafe evaluation. The official
[GlobalShortcuts portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html)
provides authorized per-session bindings, normally with a configuration dialog,
and each session can bind once. Further work must verify an acceptable task-only
lifecycle and available compositor support, rather than persistently swallowing
Escape while idle or silently claiming Wayland support.


Actual host observation (separate from any Xorg probe): read-only
`org.freedesktop.DBus.Properties.Get` returned GlobalShortcuts **version 1**.
Then the ordinary source CLI probe attempted only `CreateSession`, before any
`BindShortcuts`; the actual portal rejected it with
`org.freedesktop.portal.Error.NotAllowed` (original run, natural exit 1).
No shortcut or authorization dialog was created, no desktop setting was written,
and the probe disconnected its own D-Bus connection. Raw result:
`build/ubuntu24-input-pipeline/escape-portal/host-lifecycle.json`; reproducible
probe source: adjacent `lifecycle.py`.

This rejection is evidence about this probe's current application identity,
**not proof that the compositor universally lacks the portal**. No identity was
forged and no permission setting was changed to bypass the rejection. Official
[GNOME portal code](https://github.com/GNOME/xdg-desktop-portal-gnome/blob/main/src/globalshortcuts.c)
closes accelerator bindings with its session. This paragraph records the initial
identity-less negative probe; its earlier incomplete conclusion was superseded
by the legitimate host Registry follow-up on2026-10-23. Registry1 and portal1
accepted own-app Register→CreateSession→Close. Same-description rebind completed
in115.313ms with no provider window observed in89 samples over4.736s (50ms sampling,
not a claim about arbitrarily short flashes). Real production TaskEscape later
passed abort/disconnect→same-turn cancellation→idle Escape against an owned native
Qt target. Active Escape press was intercepted, but its key release reached the
target after disconnect; never claim the entire pair was suppressed. Four guarded
fixture failures sent no keys and remain recorded. Full source hashes, raw paths,
normal cleanup, authorization limits and107 passing focused checks are in
[native Wayland validation](wayland-task-escape-validation.md). Package support
still requires the mandatory same-SHA dual-system actual-package gates.

The selected built-in prompt is loaded by ID directly from the current
`BUILTIN_PROMPTS` on every `ConfigStore.load_prompt` call. An existing
`builtin-agent` selection consequently receives the updated rules without
rewriting `config.json`. Its preservation and current rules are asserted in the
follow-up test; custom prompt files still load their original user body.
