# Natural focus changes, Ubuntu 26 GNOME Wayland

On 2026-10-28 the r2 candidate AppImage SHA-256
`f6378650f230215a0ff0a7196a80ddc48e9429e2546b55afe40105d8a5889d05`
was checked and extracted in an isolated Ubuntu 26.04 GNOME Wayland guest.
Its actual Session, Fcitx installer and output router were used with synthetic
recorder and transcription result; no microphone, cloud service, clipboard or
user application was involved. Two native GTK3 TextViews were owned fixtures.

The scripts and raw output are retained unchanged in this directory (the Python
and shell extensions have `.txt` appended). `run26.sh.txt` SHA-256
`6e36d829fb02d1a8a33abb0d073a46ad6505adf4ecedeba70173b004c463a07b`
selects `switch`, not `switch-ready`: after A receives its first character, it
requests focus in B while the production sender runs continuously, without
SIGSTOP or other sender pause. The 200-character fixed synthetic input was
received exactly when A and B were concatenated, in four runs:

| Route | A characters | B characters |
|---|---:|---:|
| auto | 177 | 23 |
| auto | 126 | 74 |
| Fcitx | 31 | 169 |
| Fcitx | 152 | 48 |

A cancellation was also sent after A's first observed change, once per route.
Each result reported cancelled, with two prefix characters in A and none in B;
this does not imply that already-in-flight input is withdrawn or that no output
can arrive between the cancel signal and completion. All six fixture results
reported passed, sender exit 0 and Fcitx as the chosen backend. The shell
runner exited 0. Its log SHA-256 is
`9126b8533f265ca2658ce22a089e7e8c20d0045633a80260113f4de2bd8936ff`.
The auto runs retain `Authorization required, but no authorization protocol
specified` in sender stderr; its source remains unverified. The timing and
split depend on scheduling, and these few tests do not prove arbitrary focus
races, other clients or cross-framework transitions.

Reproduce in a disposable 26 GNOME Wayland guest by copying the candidate and
scripts to `/tmp/inkecho-native-test/`, placing the three scripts in `probes/`
without `.txt`, and invoking `bash /tmp/inkecho-native-test/probes/run26.sh`.
The script saves and restores user-session input-method environment variables,
uses private data/config/cache directories, and starts its own Fcitx process.
Afterward the guest check reported no running Fcitx process or bus owner (the
bus name remained activatable), private session files and the test directory
were removed, and the VM was normally powered down. `cleanup.log`,
`powerdown.log`, and `fcitx.log` retain the actual output. This is a focused
experiment, not full package acceptance.
