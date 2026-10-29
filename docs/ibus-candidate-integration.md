# IBus experimental extension integration

The packaged source under `src/inkecho/platform/ibus_candidate` follows the
separately tested prototype with LF/Tab support added; its four file hashes are pinned in
`ibus_extension.py`. AppImage copies the complete `src/inkecho` tree into its
runtime packages directory. No installation or enablement occurs on application
startup. The compatibility page exposes separate user-initiated install, enable,
disable and status actions. Install invokes the system `gnome-extensions install`
without force, after verifying the packaged payload. Enable checks the installed
extension files against the same hashes first. Disable affects only this UUID.
Status reports what `gnome-extensions info` reports and is not proof of delivery.
Commands have a timeout and do not inherit the AppImage's Python and library paths.

Offline verification: `.venv/bin/pytest -q tests/test_ibus_extension.py` checks
archive contents, no implicit enable, tamper and symlink rejection, explicit
operations and failed-service behavior. These tests use a fake command runner;
they do not alter the host desktop. Separate experimental desktop results are in
`experiments/ibus-gnome-shell/README.md`. The shipped AppImage and UI installation
flow have not yet been exercised on either target OS, and no compatibility claim
follows from those experiments. Installation may require a new login before GNOME
recognizes the extension. Disable does not uninstall the files.

The extension uses a private Shell interface. A panel call returning `attempted`
does not acknowledge target receipt; do not retry an ambiguous delivery. It only
allows printable scalars, LF and Tab; other controls are rejected, not dropped.
The prototype retains consumed tokens in memory and stops accepting
new sessions at 1024; the extension must be reloaded before further attempts.
A crashed client may leave a capability file and block another task. Neither
condition is silently repaired; both require further safe lifecycle work and
real desktop validation. Same-user processes are not isolated by the capability.

## Ubuntu 26.04 Wayland LF/Tab candidate trial

On 2026-10-28, a temporary modified prototype initially failed before control
characters: the guest lacked IBus and the first normal Chinese scalar returned
`delivery_unknown`. After installing IBus from the guest's cached packages and
restarting its disposable desktop, a separate modified prototype delivered
`甲\n乙\t丙` to an owned GTK TextView and to a VTE running a raw byte reader,
not a shell. The first VTE script had a Python quoting error; it was fixed and
repeated. No real shell command was executed.

The final candidate's four files were then installed in the guest and hashes
matched `FILES` in `ibus_extension.py`, including delivery gate SHA-256
`1a449b97986f3ad5ee83f0557487527b98c325c1d7ea018d11950568916d542d`.
The standalone candidate client sent five scalars; the GTK TextView contained
`甲\n乙\t丙`, and the raw VTE reader captured bytes
`e794b20ae4b99909e4b899`. The committed test scripts are
`experiments/ibus-gnome-shell/guest_control_trial.py` and
`experiments/ibus-gnome-shell/guest_control_reader.py`; paths in the guest script
refer to its isolated temporary directory. The trial script subsequently gained
X11 window activation for the Ubuntu 24 trial; its earlier 26 version SHA-256
was `f0a9c35840acd8459a961193f835f585cb5c94b0394d1b7b9664f6f3d7f01c71`.
This verifies that exact extension on
Ubuntu 26 GNOME Wayland in these two owned widgets, not the AppImage, other apps,
Ubuntu 24, or physical hardware. The earlier empty-window test returned
`delivery_unknown` after closing its own window while IBus was absent; it is not
proof of a no-focus outcome with a working IBus service.

Afterward the extension was disabled and uninstalled, enabled-extensions restored
to empty, temporary files removed, ten added packages removed, and the guest
shut down normally with container exit status 0. Package-manager history and
cache remain in this disposable VM.

## Ubuntu 24.04 X11 final-candidate attempt

The same four candidate files were installed and their hashes matched the 26
trial. GNOME Shell reported the extension ACTIVE, and the IBus engine was
`xkb:us::eng`. Three attempts failed before any text was sent because the owned
GTK TextView reported `is_active=False` and `has_focus=False`, despite an initial
mapping wait and explicit X11 `windowactivate`, and a later `windowfocus` attempt.
At inspection, session 5 was active with `LockedHint=no`, GNOME ScreenSaver
reported inactive, and `DISPLAY=:0` / `XAUTHORITY` matched the user service
environment. Other owned windows were not independently tested in this attempt.
Thus LF/Tab on 24 is not validated and these attempts do not show an input
failure after successful focus. The candidate was disabled and uninstalled,
enabled-extensions restored to empty, test files removed, and the VM shut down
normally with container exit status 0.

## One-use capability lifecycle design (not implemented)

`experiments/ibus-gnome-shell/delivery_gate_v2.js` is an offline policy model,
not the shipped extension. It assumes a trusted synchronous `consume(token)`
operation has authenticated and atomically consumed a capability before Begin
returns. A sender can begin at most once while its D-Bus unique name exists;
Cancel closes the task, and NameOwnerChanged removes the sender only after it
disappears. Each Commit still checks that exact sender and a monotonically
increasing sequence; delivery exceptions permanently fail the task. There is no
long-lived token set: a Node test runs 2048 sequential one-use sessions, tests
same-owner and different-owner replay, overlapping clients, cancellation, owner
loss and sequence replay. Unique names must not be reused by the same bus.
This is a model test only: it does not prove that the filesystem consumer works,
that real D-Bus owner-loss signals arrive correctly, or that resource use is
bounded when many malicious senders deliberately keep connections open.

A possible consumer would open a private runtime directory without following
links, open and authenticate the capability with no-follow, and atomically rename
its name to an unpredictable quarantine name without replacing an existing
entry. It must verify that the renamed entry matches the held descriptor before
it consumes or removes anything; if it does not, it must fail closed and preserve
unrelated data. The live client should keep an exclusive advisory lock on the
capability inode. A later client can only consider recovery after taking the same
lock non-blocking, verifying owner, mode, type, identity and an owned protocol
marker, then quarantining the candidate. Unknown files and old clients without
the locking protocol must never be automatically removed. The extension must
consume before exposing a successful Begin and must not re-read the removed file
on Commit. Server/client crash at each step, extension reload, concurrent Begin,
owner loss, hard links, replacement, symlinks and malicious same-UID processes
all need dedicated tests.

No filesystem implementation has yet established a complete race-free sequence:
checking a renamed path and then unlinking it is itself subject to replacement,
and same-UID processes can access or interfere with the runtime directory.
Atomic rename alone does not eliminate that boundary, and an advisory lock only
works for cooperating versions. Do not claim this proposal fixes stale files,
exhaustion, all races, or protects against same-user adversaries. Until a real
consumer and cross-desktop tests exist, the shipped candidate retains its 1024
limit and rejects a pre-existing capability file.

### Independent filesystem lifecycle prototype

`experiments/ibus-gnome-shell/v2_lifecycle.py` and
`test_v2_lifecycle.py` explore the proposed protocol without changing the
product. Each task creates a separate random capability name and random token,
holds an advisory lock on the created inode, and never scans or deletes other
tasks' files. The receiver checks a no-follow descriptor, owner, regular-file
type, mode, link count and token, and uses Linux `renameat2(RENAME_NOREPLACE)` to
atomically move the source name to its corresponding consumed name. A moved
inode mismatch fails closed and preserves the moved object. After successful
consumption a repeated Begin cannot find the original name, including after a
receiver restart. Only the exact D-Bus sender bound at Begin can commit; sequence
numbers cannot repeat. Sender loss clears in-memory state. Old source or consumed
files left by a crashed task do not block a different random task; the prototype
deliberately leaves them in place rather than risking removal of another task's
file. This avoids operational blockage, not unbounded accumulation of leftovers.

Run `.venv/bin/pytest -q experiments/ibus-gnome-shell/test_v2_lifecycle.py`:
six tests pass, including 2048 sequential tasks, one real subprocess exiting
without cleanup, receiver restart, concurrent Begin, replay, symlink and occupied
consumed-name rejection, and preservation of unrelated files. These are Python
and filesystem tests, not GNOME Shell, GJS, real D-Bus, or desktop tests. The
prototype assumes cooperating same-UID processes; an attacker running as that
UID can replace entries between checks, access tokens, deny service, or race the
client's identity-check-then-unlink cleanup. `renameat2` does not eliminate all
same-user races. It also relies on unique sender names and trustworthy owner-loss
notifications from the bus, neither of which is established by the offline test.
The token is not a boundary against same-user adversaries. The production bridge
continues to use the original lifecycle and has not gained these properties.

## GJS V2 prototype and isolated desktop trials

The separate `experiments/ibus-gnome-shell/v2_candidate/` extension and client
implement the V2 protocol; they do not replace the product's extension or
client. The GJS consumer opens the runtime directory without following its final
symlink, anchors candidate paths at the held directory descriptor using procfs,
checks a no-follow regular file descriptor and token, and calls GIO move without
overwrite or copy fallback to consume its name. It checks the moved inode against
the held descriptor and fails closed on a mismatch. Commit and Cancel rely on
the bound unique bus sender and session sequence. The Python task creates a
random per-task file and retains its lock; leftover files are not inspected or
deleted by later tasks. The V2 design does not protect against a malicious
same-UID process, and client cleanup still uses a check followed by unlink.
Stale files can accumulate. No claim is made that all races are eliminated.

`XDG_RUNTIME_DIR=<private-0700-directory> gjs -m
experiments/ibus-gnome-shell/v2_candidate/capability.test.js` verified successful
consume, bad token, repeat, destination conflict and final symlink rejection.
`VIRTUAL_ENV="$PWD/.venv" bash
experiments/ibus-gnome-shell/v2_candidate/run_private.sh` used a separate D-Bus,
GJS service and Python client for 2048 sequential tasks with an abandoned
capability preserved. An initial private test completed its 2048 tasks but failed
its overly broad final directory assertion because GIO had created a `gvfs`
directory; the test was corrected to inspect only capability names and rerun
with the local GIO VFS. These tests are not the product integration.

On 2026-10-28, the same V2 extension files were installed separately in isolated
Ubuntu 24.04 GNOME 46 X11 and Ubuntu 26.04 GNOME 50 Wayland desktops. File
SHA-256 values for `extension.js`, `capability.js`, `delivery_gate.js`, and
`metadata.json` were respectively
`421516cb3269313586669dec2fefc2c92798fa6f5bbe9e30ac44a73a86a74ec8`,
`fcbaf3e7fd0184ca3141f3c4d811f7496ef753fd6282714ec128a26151a1c881`,
`21ce51e500aaed1afc5403a8614903d4d9de027b786afe59a717840e7265a63e`, and
`c53d67c6b8d2e9769e7dcf0a3b6545dbc57673e8ea29a7e487bf55761c214317`.
Both used client SHA-256
`e8e61f5e3c05f029c6af961799126d744b967f03ea54bcf5b9e52c544b5469e8`
and guest test SHA-256
`e92520514757ad72d68b9a011c81b2dc08fc0a1807cf0868a150f18a6f71da6f`.
In both, two owned GTK entries received 甲 and 乙丙, the xkb/us engine stayed
unchanged, another sender was rejected, cancellation stopped the next character,
and cancellation while holding a reply after server processing stopped the next
character. A queued request cannot be retracted by this test. The initial 24
attempt stopped before sending because the test script imported Capability from
the wrong module; the fixed script was rerun. On 26, installing missing IBus
packages was required. A later attempt to select libpinyin was reset by GNOME to
xkb before the test, so the V2 trial did not test a non-XKB engine.

Both guests restored empty enabled-extension lists, removed the prototype and
temporary files, and shut down normally with container exit 0. The 26 guest also
restored its xkb/us input source and removed the ten installed test packages;
a cleanup attempt to explicitly select xkb warned that setxkbmap lacked X11
authorization, while the prior test had already confirmed xkb/us as the active
engine. Package manager history and cache remain in the disposable guest. These
are separate prototype trials, not AppImage tests, full adversarial file-race
verification, preedit tests, browser/terminal tests, or proof of target receipt.

## V2 integration after prototype trials

After the preceding desktop trials, the candidate V2 extension and unique-file
client were connected to the explicit IBus route and its separately initiated
install/enable controls. `FILES` now pins the four V2 extension hashes recorded
above. Existing installations of the old UUID are not silently modified: users
who enabled the earlier experimental extension should disable it using GNOME's
extension manager. Automatic mode still uses the keyboard; IBus is opt-in.
The earlier sections describe the state and hash at the time of each trial.

This integration has unit and protocol tests but has not been validated as the
same AppImage on both Ubuntu releases. The actual desktop tests above used the
standalone V2 client and prototype extension, not the packaged application.
GNOME private API compatibility, non-XKB engine composition/preedit, focused
terminal/browser behavior, potentially already-dispatched cancellation, same-UID
file interference and stale-file accumulation remain open. `attempted` still
means only that the panel call was made, not that a target accepted the text.

After the recorded desktop trials, Ruff-only formatting/import ordering changed
`experiments/ibus-gnome-shell/client.py` SHA-256 to
`fe83b5c20c334a5da8a464454cc2028150f6f22285c0b0369aa676bdc33c7e91` and
`v2_candidate/guest_protocol_test.py` SHA-256 to
`c8390b839c0ff37670e184e5ba2e1caeb5ce356cf9f4b5bb4ce059689ba8f107`.
The earlier hashes remain the actual files used in the corresponding trials;
these formatting-only revisions have not been retested on the desktop.
