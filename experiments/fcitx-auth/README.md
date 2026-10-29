# Offline Fcitx task authorization exploration

**Not integrated or secure by itself.** The existing addon exposes `Commit(s)`
without authorization to every peer able to call it on the session bus. The
existing experimental binary remains unchanged. Do not enable or publish that
endpoint as an authorized product backend.

This offline model assumes, but does not implement, a trusted authorizer that
provisions exactly one unpredictable 256-bit task capability and the verified
D-Bus unique sender into the addon through a channel inaccessible to other
session peers. It binds that task to the sender, a monotonic deadline and a
strict scalar sequence. A sequence is consumed before delivery. Cancellation,
expiry, malformed text, unsuccessful delivery and uncertain delivery end the
task; no automatic replay is allowed. Cancellation cannot retract a call
already queued or in progress. Focus is resolved at delivery, not recorded in
the grant. The model keeps neither submitted text nor delivery exceptions.

The key unresolved issue is **trusted provisioning**. Same UID, PID checks,
first-caller registration, a user-readable file or environment variable, and
a D-Bus method that accepts a caller-chosen token do not authenticate the
product against a hostile same-user process. A secret sent over a channel whose
confidentiality or peer authenticity is not established is no solution either.
Even a private channel may not isolate processes with equal OS privileges;
same-user debugging, process inspection or bus monitoring constraints must be
part of an explicit threat model. Sender uniqueness requires the actual bus
sender supplied by the bus, never a caller-provided string. Unique names are
connection scoped; loss/restart invalidates grants. The production addon must
also remove or deny its old unauthenticated method, fail closed until authorized,
and protect task setup, replacement, cancellation and ownership atomically.

Before changing the native binary, review and demonstrate a provisioning channel
and its real threat boundary, then test unauthorized independent clients,
forged credentials/senders, task replay, disconnect/restart, concurrent calls,
expiry, cancellation and lost replies under both Ubuntu versions. Verify that
no text or capabilities appear in logs, and repeat same-binary package and
app-level acceptance. This model is synchronous and does not prove D-Bus
ordering, confidentiality, integration, race-freedom or protection against a
same-UID adversary. Run its offline checks with
`.venv/bin/pytest -q tests/test_fcitx_task_policy_experiment.py`.

## Capability-file candidate

`capability.py` and `capability_gate.h` are separate offline candidates, derived
from the IBus experiment's exclusive per-task random capability file and
bus-provided unique sender binding. The creator checks an owner-only runtime
directory, creates a random 256-bit token as lowercase hexadecimal with an
exclusive 0600 no-follow file, and removes only the inode it created. The gate
opens the runtime directory and file with no-follow, validates ownership, file
mode, type, size and link count, then binds begin to a sender and enforces
sequence and cancellation. This is serialized-event-loop pseudointegration;
it is not exposed on D-Bus and does not modify the existing addon.

This reduces accidental and tokenless calls only. A same-UID process may read or
replace the file, observe D-Bus calls, control the process, race cleanup, or
impersonate the application; file metadata and token are not a strong boundary
against it. The sender must be obtained from Fcitx's actual D-Bus invocation,
not passed as an argument: whether the available Fcitx API exposes an
unforgeable invocation sender remains unverified. Replay memory is bounded and
process-local: an addon restart loses it, so stale-file lifecycle and restart
recovery remain unresolved. An in-flight callback cannot be revoked. A prior
open `Commit(s)` endpoint would completely bypass this candidate: production
must remove or disable it before any protected endpoint is considered.

Offline validation: run `.venv/bin/pytest -q tests/test_fcitx_task_policy_experiment.py`
and `g++ -std=c++20 -Wall -Wextra -Werror experiments/fcitx-auth/capability_gate_test.cpp -o /tmp/inkecho-cap-gate-test && /tmp/inkecho-cap-gate-test`.
Both passed on the development host; no Fcitx runtime, VM, D-Bus authorization,
AppImage integration or Ubuntu compatibility is established by those tests.
