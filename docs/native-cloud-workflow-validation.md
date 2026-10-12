# Native cloud workflow validation — 2026-10-13

## Purpose and scope

The earlier alpha4 authenticated ASR check exercised `ProviderClient` alone.
This bounded follow-up was intended to add the previously untested combination:
extracted alpha6 runtime → production `Session` → configured real ASR and optional
polishing/fallback → direct input into an owned native GTK target.

The input is the existing public Aliyun WAV sample, **not microphone audio**:
571456 bytes, 17.645125 seconds, mono 16000 Hz, 16-bit PCM. Its required SHA-256 is
`0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf`.
The public source was
`https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/sensevoice/rich_text_example_1.wav`.
The script replaces `Recorder` with a public-file source and otherwise delegates
to production orchestration and provider clients. It does not include MainWindow
notifications, physical shortcuts, or real microphone validation.

## Guardrails and reproduction

`scripts/validation/native_cloud_workflow_probe.py` requires explicit live-cloud
opt-in, an unlocked native Wayland session, the exact public-sample hash, and
application imports from the declared extracted package. Each role is limited to
one call, without automatic billable request retry. It reads existing configuration
and Secret Service credentials through production interfaces. For the entire
asynchronous probe, a process-local context replaces `inkecho.config.atomic_write`
with a function that raises `ConfigurationWriteBlocked`. This blocks both the
backup and rewritten record that a legacy-schema load would otherwise create,
as well as ordinary saves. The original writer is restored on exit. This is a
write-time guard, not a preliminary schema check; later reads remain protected
if a file is replaced between reads. No product configuration code is changed.

Before reading credentials or sending audio, capture must identify the disposable
GTK fixture's own process. Additional ownership checks precede input and text
readback. Production focus, generation, caret and cancellation guards remain intact.
The fixture's `-` output mode keeps text in memory; comparison reports only a
boolean and character count. Neither raw responses, transcripts, keys nor private
workspace URLs are printed or written. No ambient audio or clipboard is used.

After coordinating exclusive desktop focus, the attempted command was:

```sh
probe_appdir="$PWD/build/audio-alpha6-extracted/squashfs-root"
PYTHONHOME="$probe_appdir/usr" \
PYTHONPATH="$probe_appdir/packages" PYTHONNOUSERSITE=1 \
QT_PLUGIN_PATH="$probe_appdir/packages/PySide6/Qt/plugins" \
QT_QPA_PLATFORM=wayland LD_LIBRARY_PATH="$probe_appdir/usr/lib/inkecho" \
"$probe_appdir/usr/bin/python3" scripts/validation/native_cloud_workflow_probe.py \
  --sample /tmp/inkecho-public-asr-fixture.wav \
  --package-root "$probe_appdir/packages" --allow-live-cloud
```

Do not rerun automatically: this is an opt-in billable validation, and desktop
focus must first be available and exclusively coordinated.

## Actual result

One attempt ran after the other native test released all owned windows. GNOME's
unlocked-session precheck passed. Qt reported `There are no outputs - creating
placeholder screen`; the owned GTK target could not be captured. The script
stopped with `InputUnavailable` after 1.292 seconds and cleaned up its fixture.

- Application version: `0.1.0a6`, loaded from the extracted package.
- Task states and outcomes: empty; no task began.
- ASR calls: **0**. Polishing calls: **0**.
- Credentials were not read: failure occurred before `Session.toggle()`.
- Microphone captured: **false**. Transcript saved: **false**.
- No API authentication, ASR result, polishing result, or text insertion was tested.

Therefore this particular production Session/cloud/native input combination is
**not yet validated**. Earlier successful native GTK direct-input evidence and
separate microphone/local-service evidence must not be presented as a single real
user-speech/cloud workflow. The display-output/focus obstacle remains to be
investigated without weakening capture safety.

Static checks: Ruff lint and formatting passed for the new probe and fixture
memory mode; `git diff --check` passed. The alpha6 runtime also loaded the script
successfully for `--help` without creating a GUI or sending requests.

## Read-only display diagnosis

One coordinated read-only follow-up located the actual native compositor and
compared three independent display interfaces, without creating further windows:

| Check | Observed result |
| --- | --- |
| Wayland socket | `/run/user/1000/wayland-0`, exists |
| Socket owner, from `/proc/net/unix` inode and `/proc/*/fd` | `gnome-shell`, PID 3143 |
| GNOME ScreenSaver `GetActive` | `false` |
| Mutter DisplayConfig `GetCurrentState` | 0 physical monitors; 0 logical monitors |
| System GTK 3 / `GdkWaylandDisplay` | 0 monitors; 0 positive-size output geometries |
| Extracted alpha6 Qt / native `wayland` | 1 placeholder screen; 0 positive-size geometries |

Only counts and process/socket metadata were emitted; monitor identities, window
titles and user content were not inspected. GTK used `get_n_monitors()` and
monitor geometry positivity. Qt used `screens()` and screen geometry positivity.
The Mutter reply was reduced in memory to the lengths of its monitor and logical
monitor arrays; the full reply was not printed.

These consistent observations establish that the current GNOME compositor
advertises **no display outputs**, despite reporting an unlocked screen. This is
not isolated to the packaged Qt runtime: system GTK and Mutter agree. The
historical transition that removed the outputs was not observed, so no claim is
made about why they disappeared or about the user's earlier incident.

No settings, display configuration, lock state, or input were changed. The checks
did not launch additional application windows. Further blind native attempts
stopped; obtaining real compositor focus requires display outputs to become
available again. No product code change or weakening of target checks is
justified by this environmental evidence.


## Configuration write guard regression

Review identified that production `ConfigStore` may migrate schema-zero files
while loading them. The earlier attempt used current-schema configuration and did
not trigger migration, but a general read-only promise required the explicit
write guard above. The cloud/desktop attempt was **not rerun** after this repair.

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q \
  tests/test_native_cloud_probe.py
```

Result: **4 passed in 0.10 seconds**, using only disposable temporary configuration.
Legacy load is rejected with original bytes and directory entries unchanged;
current-schema load succeeds while saves are rejected; replacing a current file
with a legacy record between reads still rejects migration; initial saves cannot
create a missing configuration directory. The original writer is restored after
the context exits. No user configuration, credentials, network, or desktop was
accessed by these tests.
