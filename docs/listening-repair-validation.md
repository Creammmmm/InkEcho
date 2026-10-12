# Listening cancellation repair — 2026-10-13

## Evidence and cause boundary

The user's safe application log showed recording → transcribing → cancelled,
including cancellation approximately 7–11 ms after entering transcribing. It did
not contain a provider error or the originating accessibility event. Inspection
confirmed that the old accessibility event handler invalidated the captured target
on **any** focused/active/defunct state event, including events from unrelated
applications. This is a reproducible defect; the particular event responsible for
the user's observed cancellations has not been captured.

A secondary Qt process exiting after shortcut delivery and notification widgets
were investigated as possible sources. Neither is asserted to be the proven cause.
In the isolated Qt lifecycle probe below, zero relevant foreign state events were
observed. Actual native notification lifecycle reproduction remains unverified.

## Change and safety review

Only a captured control losing focus, its window losing ACTIVE, either captured
object becoming DEFUNCT, or the captured caret moving invalidates immediately.
Unrelated loss/destruction events do not invalidate the target. A foreign focus or
activation gain triggers a fresh, bounded check of the captured target's existing
process, focused/editable/active/caret/generation guards, without a blind delay.
Concurrent checks are coalesced; late results cannot revive an expired generation
or cancel a newly captured target. Genuine focus loss followed by focus return
remains permanently invalid. Direct insertion still checks the target and task
cancellation immediately before the single targeted AT-SPI call. No clipboard
fallback or global keyboard injection was added.

The accompanying visible cancellation feedback is recorded separately in
[listening-feedback-validation.md](listening-feedback-validation.md).

## Focused automated verification

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q \
  tests/test_platform_accessibility.py tests/test_application.py
```

Result: **48 passed, 1 skipped**. The opt-in native bus ownership test was skipped
by this command. Regressions cover unrelated application/window destruction and
focus-loss events, genuine captured-target/window loss and destruction, foreign
focus gain with a valid or invalid current target, away/back while validation is
pending, and stale validation completing after capture of a different target.
Ruff checks and formatting passed for changed source, tests, and the probe.

## Actual desktop transport probe

The probe uses only disposable owned GTK 3 text fields; it verifies the target's
D-Bus process identity equals the child PID before inserting fixed Unicode. No
user documents, microphone, provider credentials, cloud calls, or clipboard are
used. It destroys its own children on completion or failure.

Native GNOME Wayland: a first bounded capture-only run succeeded with the owned
fixture PID. A subsequent lifecycle/insertion run could not obtain an ACTIVE,
focused editable target and stopped before insertion. Thus this investigation
**does not establish a native Wayland completed input workflow**. No private
compositor setup, desktop unlock, or permission workaround was attempted.

Private Xvfb `:97`, private D-Bus, host GTK 3 and development Python:

```sh
dbus-run-session -- bash -c '
  build/listening-test-tools/root/usr/bin/Xvfb :97 \
    -screen 0 1280x900x24 -nolisten tcp & probe_xvfb=$!
  trap "kill $probe_xvfb" EXIT
  sleep 1
  DISPLAY=:97 XDG_SESSION_TYPE=x11 \
  LD_LIBRARY_PATH="$PWD/build/listening-test-tools/root/usr/lib/x86_64-linux-gnu" \
  PYTHONPATH=src .venv/bin/python scripts/feasibility/listening_event_probe.py \
    --xdotool "$PWD/build/listening-test-tools/root/usr/bin/xdotool"
'
```

Result on 2026-10-13: **passed**, approximately 4.9 seconds. Observed:

- Owned target captured; target survived a transient offscreen Qt application
  opening and closing. Relevant foreign Qt state events observed: **0**.
- Three explicitly **synthetic** foreign events (`defunct=true`, `focused=false`,
  `active=false`) were replayed through the real private accessibility D-Bus.
  All three reached the handler. Each meets the old unconditional cancellation
  predicate; the corrected handler preserved the captured target.
- Fixed Chinese/Latin/emoji Unicode was inserted exactly into the owned GTK field.
- Explicit cancellation and focus-away/back caused no additional insertion.
- Cloud calls: **0**.

This proves the targeted event regression over actual transport and safety guards
on an isolated X11 GTK fixture. Synthetic events are not evidence that the user's
shortcut subprocess or native notification emitted those events. It also does not
establish GTK 4, browser, terminal, or broad native Wayland compatibility. The
packaged microphone/local-provider workflow is recorded by release validation in
[listening-repair-release.md](listening-repair-release.md).

## Follow-up: native session lock state

A later bounded diagnostic on 2026-10-13 found the **current** GNOME Wayland
session locked. Reproduce the read-only session checks with:

```sh
loginctl show-session auto -p Type -p Active -p LockedHint
gdbus call --session --dest org.gnome.ScreenSaver \
  --object-path /org/gnome/ScreenSaver \
  --method org.gnome.ScreenSaver.GetActive
```

Observed independently: `Type=wayland`, `Active=yes`, `LockedHint=yes`; the GNOME
screen saver call returned `(true,)`. Here session `Active=yes` means the login
session is active, not that an application window has keyboard focus.

Before noticing the lock, a disposable owned GTK fixture was sampled three times
at one-second intervals. Its `window_active`, `window_toplevel_focus`, and
`textview_has_focus` were all false. Its corresponding owned AT-SPI window also
reported ACTIVE=false and FOCUSED=false. No discrepancy between GTK and AT-SPI was
observed; refusing capture was correct for that window. The fixture was cleaned
up without text insertion. No screen unlock or focus restriction workaround was
attempted, and further native attempts stopped.

This explains the current validation obstacle, not the earlier user's incident:
its historical lock state was not recorded and cannot be inferred. Native
Wayland end-to-end recording/recognition/insertion acceptance remains incomplete.
No product change is justified by this lock-state diagnostic alone; alpha5's
existing focus and cancellation guards remain intact.

## Unlocked native Wayland follow-up: direct input passed

Later on 2026-10-13, the root agent observed GNOME `GetActive` return `(false,)`.
With the desktop unlocked, the existing probe ran successfully on the actual
GNOME Wayland session, with no application source change:

```sh
PYTHONPATH=src .venv/bin/python scripts/feasibility/listening_event_probe.py
```

Result: **passed**, approximately 3.83 seconds. The probe captured its own GTK 3
fixture's actual focused editable target and verified its authoritative D-Bus PID
before any insertion. Exact Chinese, Latin, and emoji text reached that owned
field. Explicit task cancellation inserted nothing. Opening a second owned GTK
window invalidated the original target; its expired token could not insert after
the second window closed. Both fixture processes were cleaned up.

The transient offscreen Qt process did not disturb the target, and again emitted
**zero** relevant foreign state events. Three explicitly synthetic unrelated
state events replayed through the actual native AT-SPI bus were observed and did
not cancel the target. This establishes the regression behavior over native
transport, not the original user's precise cancellation event source.

This new result supersedes the earlier pending status **for owned GTK 3 native
Wayland direct input and cancellation only**. It does not establish every
application's support, GTK 4 support, cloud recognition quality, or a complete
microphone/provider/application workflow. No microphone, API credentials, cloud
calls, user-document reads, clipboard access, system setting changes, or screen
unlock were performed in this probe. Packaged native workflow testing is a
separate release validation task.
