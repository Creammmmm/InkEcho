# r3 candidate: Ubuntu 24 Xorg and GNOME Wayland

The same unmodified candidate AppImage SHA-256
`23b1b77e41e4e3a8fdd30a9a6a892d5b5babeaa9e303fdbcc3b37731e5a1e105`
was checked in an isolated Ubuntu 24.04 VM in each session. The extracted
package's `fcitx5.py` SHA-256 was
`bf07c2476489590ba56f6ea20d5c65dea15b7f410394bf0efc443806856cfee1`.
The package Session, actual Fcitx service/bridge, and actual keyboard backend
were used with test-owned GTK3 TextViews and fixed synthetic transcription/audio.
No clipboard, cloud, microphone or real user application was used. A test-only
observer wraps real calls to record selection, Commit result, no-target error,
request timeout and keyboard entry without changing replies or behavior.

| Session | Target | Scenario | Result |
|---|---|---|---|
| Xorg | Fcitx | full 200 characters | passed, exact |
| Xorg | Fcitx | cancel after first change | passed, 2-character prefix |
| Xorg | GTK simple | full 200 characters | passed, real Fcitx no_target(0,0,false) then keyboard |
| Xorg | GTK simple | natural switch | passed, A/B 2/198, exact concatenation |
| Xorg | GTK simple | cancel | passed, one-character prefix |
| Wayland | Fcitx | full 200 characters | passed, exact |
| Wayland | Fcitx | cancel after first change | passed, 2-character prefix |
| Wayland | GTK simple | full/switch/cancel | all failed, zero output; keyboard unsupported |

For the three Wayland simple-target attempts the real bridge selected Fcitx and
returned `no_target` with accepted=0, offset=0 and uncertain=false. The actual
keyboard backend then reported that GNOME 46 lacks the required Unicode keyboard
mapping interface. No switch or cancel could be exercised because no character
was inserted; these are not passes. Cancellation cannot retract already-sent
characters. These bounded tests do not prove arbitrary target, cross-framework,
post-prefix or ambiguous-delivery behavior, and do not test the candidate's FUSE
launch or constitute full package acceptance.

`r3-ubuntu24-xorg.log` SHA-256
`13ef77315cf953f657fe1203ab0794d08512b2126ddb5944c4be8991c9a766a9`;
`r3-ubuntu24-wayland.log` SHA-256
`8c8ec1aae607e65c1abe5bcdf1ddc33eff91f53abe0465c847eac95b85fcfd85`.
Raw scripts and Fcitx logs are retained in this directory; code extensions have
`.txt` appended. To reproduce, copy the candidate and scripts into
`/tmp/inkecho-r3-test/` with scripts in `probes/` (remove `.txt`) in an isolated
Ubuntu 24 guest, then run `bash probes/run.sh <sha> x11` or, on the separate
Wayland login, `bash probes/run-wayland.sh <sha> wayland`. The scripts retrieve
the test session's Xauthority without logging it and use private Fcitx data.
The Wayland launcher adds `XDG_CURRENT_DESKTOP=ubuntu:GNOME` and otherwise
matches the Xorg runner's test logic. Each session restored its original input
method environment and stopped its temporary Fcitx. The original GDM/account
session configuration was restored and byte-compared, guest files removed,
VM normally powered down, and container exit 0. Cleanup is recorded in
`r3-ubuntu24-cleanup.log`.
