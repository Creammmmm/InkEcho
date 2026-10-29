# Natural focus changes, Ubuntu 24 GNOME Wayland

On 2026-10-28 the same r2 candidate used in the 26 experiment, SHA-256
`f6378650f230215a0ff0a7196a80ddc48e9429e2546b55afe40105d8a5889d05`,
was tested in an isolated Ubuntu 24.04 GNOME Wayland guest. The retained
`run26.sh.txt` (SHA-256 `6e36d829fb02d1a8a33abb0d073a46ad6505adf4ecedeba70173b004c463a07b`)
is byte-identical to the 26 test. It uses the actual package Session and Fcitx
route, two owned native GTK3 TextViews, synthetic audio/transcription, no cloud,
microphone or clipboard. `switch` does not stop or pause the sender.

| Route | Test | A characters | B characters | Result |
|---|---|---:|---:|---|
| auto | switch | 200 | 0 | failed coverage: output completed before B gained focus |
| auto | switch | 43 | 157 | exact concatenation |
| auto | cancel | 2 | 0 | cancelled, exact prefix |
| Fcitx | switch | 60 | 140 | exact concatenation |
| Fcitx | switch | 70 | 130 | exact concatenation |
| Fcitx | cancel | 2 | 0 | cancelled, exact prefix |

The first switch was reported `passed: false`; its B focus arrived after all
output had already reached A, so it provides no active-switch coverage. The
other three switch samples had exact 200-character concatenation. Cancellation
cannot retract in-flight input and these samples do not prove no character can
arrive between cancellation and termination. All sender processes and the
runner exited 0, but this does not turn the failed first coverage into a pass.
Auto-route stderr still contains `Authorization required, but no authorization
protocol specified`; its cause is not established. Fixed synthetic text,
per-commit results, focus timestamps and diagnostics are in the unmodified
`wayland24-natural-r4.log` (SHA-256
`6c16b510b5b37e775c8af2d4866973170df20e89f822e83e3200c8198b3bd1c1`).
The evidence does not establish behavior across arbitrary clients or backends.

Reproduce as described in `../natural-wayland/README.md` in an isolated Ubuntu
24 GNOME Wayland guest. The script restored its input-method environment and
stopped its Fcitx instance. The post-test check showed no Fcitx owner/process,
IBus session environment restored, the private session and test files removed,
and original GDM/account backups intact (`wayland24-natural-r4-cleanup.log`).
The active Wayland VM and explicit responsibility for restoring those backups
and shutting down were handed to the audit agent for an immediately subsequent
isolated XAUTHORITY comparison. This experiment is not package acceptance.
