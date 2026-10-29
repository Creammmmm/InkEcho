# Reliable ownership research in network-disabled VM: portal PID is not full mapping

2026-10-29. All IBus/Gio/portal execution occurred ONLY inside a new Ubuntu26
virtual machine. Host executes stdlib file preparation/docker/SSH only, never
loads GI, starts a bus/portal or calls the host input method in this round.
This does not erase the previous round's possible host-IBus contact report.

Isolation safeguards actually checked:
* Container NetworkMode none; QEMU usernet restrict=on, loopback guestSSH forward
  only. No guest downloads or external connection attempts. Original26 backing,
  base, seed and dedicated test key readonly, ownoverlay writable. No host
  display/runtime/sessionbus mount. isolation.log includes exact mount flags.
* launch.py guards the known guest machine-id. It constructs a WHITELIST private
  HOME/config/cache/runtime/IBUS_ADDRESS BEFORE dbus-run-session starts; noDISPLAY,
  WAYLAND_DISPLAY or host/session address inherited. No guestdesktop settings,
  engine or applications were changed.
* Before any synthetic portal FocusIn, standard sessionbus identified actual
  portalPID2296 and /proc/exe root-owned /usr/libexec/ibus-portal. Its actual
  IBUS_ADDRESS/HOME/runtime were verified equal to the new guest private paths.
  This directly closes the earlier activation-environment error.

No text, keys, CommitText, SetSurroundingText, preedit payload or clipboard was
sent/read. Only owned synthetic input contexts and metadata were used. This is
an ownership-interface experiment, not an actual editor/receipt/desktop-support
acceptance test.

Actual observations (raw-guest.tar/result.json):
1. Portal client A session unique:1.3 authenticated to actual PID2305 by standard
   GetConnectionUnixProcessID; B:1.4 to PID2309. Both match original child PIDs.
2. Another connection's FocusIn on A's portal object was rejected. This confirms
   existing portal owner authorization, unlike client-name or geometry guesses.
3. A portal-local InputContext_1 corresponded to private currentInputContext_3;
   B portal-local InputContext_2 corresponded to private currentInputContext_5.
   An owned DIRECT context_4 created between A/B broke any fixed numeric-offset
   inference. Paths must not be equated or mapped by observed ordinal patterns.
4. Final A duplicateFocusIn, without first issuing A FocusOut, left currentB_5;
   the fixture incorrectly expected successful A refocus and asserted. That
   failure is retained (actual.log), NOT relabelled as full protocol pass. It
   reinforces that observing a FocusIn call alone cannot replace current-context
   checks. Exact state-machine cause was not separately proven; no retry.

What is now stronger: a real portal-client PID can be authenticated on the
standard bus while ordinary custom privateIBus PID lookup was previously absent.
What is STILL missing: an authenticated edge between private-current pathR and
portal-local pathL. Upstream portal.c keeps owner and underlying proxy internally
but the observed public interface does not expose their mapping. Event timing,
matching coordinates, equal IDs or offsets cannot supply this edge reliably.
No automatic route or output adapter was enabled.

A concrete potential upstream/optional-provider API (DESIGN ONLY, not implemented
or advertised as working):
ResolveContext(localPath) -> (version, sessionOwnerUnique, privatePath, privateBusGUID)
provided by a trusted portal. Consumer authenticates portal uniqueowner/rootowned
executable, authenticates sessionOwnerUnique→PID via standardbus, requires actual
focusedappPID, matches privatePath AND privateBusGUID to Shell's current IBus
connection/context, and rechecks generation immediately before attempt. Owner
loss/contextdestroy invalidates cached results. Missing method→unknown before
any attempt; any attempted/unknown request is never replayed. Private direct
clients would need a separate daemon-provided authenticated context-owner API;
this portal design cannot be claimed as universal stock IBus detection.
A system portal/IBus upgrade would be a deployment requirement, not a transparent
InkEcho setting, and must not restart an active user service automatically.

No speculative mapping code was added to product. Existing explicit V2 plus
honest submitted-unconfirmed completion remains the practical verified path;
this ownership experiment alone does not justify auto detection.

Cleanup verified inside guest: PIDs2284(sessionbus),2287(privateibus),2296(portal),
2305/2309(clients) all absent in cleanup.json. Both original children exited0;
private daemon explicitly terminated and waited-15. No guest desktop config was
changed, so no input-source/extension restoration was needed. Normal VM poweroff
and original dockerwait returned0 (outer14608 natural0); final-container.json
exited0/Runningfalse/OOMKilledfalse. No processes were killed on host. Overlay
stopped/retained, all logs/errors/source remain; no shared worktree edits.

6offline assertions over immutable VM evidence passed, including preserving the
refocus assertion failure and verifying isolation/PIDs/path mismatch/cleanup.
These are evidence assertions, not a claim the original runtime script passed.

raw-guest.tar SHA256:
581fcc95bbd26ee676d6f9f1979f46eb3e7e11048dc954b24f12741d27dcc421
