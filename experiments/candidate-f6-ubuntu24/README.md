# Candidate f6: Ubuntu 24.04 isolated output probes

Candidate: `InkEcho-0.10.2-x86_64.AppImage`, SHA-256
`f6ceb6311069f85b180bafd446f546247b5e592735ba26035455a571c5eb5164`.
This is an uncommitted source snapshot, not a release. Its output router in the
image was separately hashed and matched the working source at build time.

The actual Ubuntu 24.04.5 guest ran on KVM using a temporary qcow2 overlay over
read-only original and base images. Both Xorg and native Wayland had an active
GNOME session; the candidate hash was checked inside each session. Test scripts
use disposable configuration and a private Fcitx, synthetic fixed text, stub
recording and stub transcription; target controls were owned GTK fixtures. This
is not actual microphone, cloud, physical shortcut, browser or terminal testing.

The first Xorg run (`x11-run.log`) failed auto mode because its instrumentation
wrapped `_choose_auto` with an obsolete zero-argument signature. The corrected
`sender.py.txt` forwards all arguments. The subsequent `x11-run-r2.log` reports:

- Auto Fcitx full and cancel: pass; explicit Fcitx full and cancel: pass.
- Auto zero-prefix keyboard fallback full, switch, cancel: pass.
- Owner-change: **not passed**, delivery reported unknown after one character.
  The log does not prove the replacement service acquired its name. No automatic
  retry was reported; the remainder cannot be claimed delivered.

In `wayland-run.log`, auto and explicit Fcitx full/cancel all passed. Keyboard
fallback full, switch and cancel failed; no successful target text delivery was
observed. Owner-change was also **not passed** with `delivery_unknown` after the
first character. This does not establish a usable generic 24 Wayland fallback.

The scripts are the exact test sources, save for `.txt` suffix. Run the supplied
`run.sh.txt` only inside a disposable guest after arranging the `probes/` paths
and standard desktop environment it specifies. The runner's zero exit status
is not a success indicator: each JSON `passed` field must be examined. The test
bridge was installed only inside the disposable guest and disabled by the script.
The guest shut down normally (QEMU container exit 0); its temporary overlay,
seed and private SSH-key copy were removed. The original images were read-only.
The initial failed KVM launch used an incorrect device group and sent no input.

This is partial 24.04 evidence only. IBus auto selection, real speech,
physical shortcut, packaging acceptance and all-system support remain unproved.
