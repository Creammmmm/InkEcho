# IBus capability cleanup: isolated GJS protocol probe

Run `bash experiments/ibus-capability-cleanup-private/run.sh` with the project
`.venv` and `gjs` available. The script uses a fresh private D-Bus session, a
private 0700 runtime directory, the production owned IBus GJS capability and
gate modules, and the production Python owned client. It destroys its private
runtime after exit. The service is a test harness with a synthetic target and a
trusted-owner override; it is not GNOME Shell, a desktop, or an AppImage. No
text commit, desktop IBus service, user credentials, or clipboard is involved.

On this host, three runs each completed 30 real Begin/Cancel/close cycles without
residual capability names. A further 100 races per run closed the capability
at staggered delays while Begin was in flight. Close returned normally 100/100
in all runs; Begin succeeded 4, 5 and 11 times respectively and was rejected 96,
95 and 89 times. No capability names remained after each iteration. Those Begin
successes mean the service consumed the file before its removal; they do not
prove cancellation or dispatch atomicity. This sample did not observe the new
conservative cleanup-failure diagnostic during a normal concurrent rename;
it does not establish the absence of rare safe refusals.

The server consumes by moving the original inode from `cap-*` to `used-cap-*`.
The synthetic unit tests separately cover a foreign replacement, a nonprotocol
rename, a hard link, failed `fstat`, and failed unlink/close; uncertain cleanup
is reported and foreign files are preserved in those controlled tests. When
stat and unlink are separate operations, another same-user process can replace
an entry between them: the check and unlink are not atomic and these tests do
not prove otherwise. The runtime directory and cooperating same-UID processes
are not a hostile-user security boundary. A concurrent legitimate rename may
also be conservatively reported as cleanup failure; do not treat that report as
proof that content was sent or received.
