# RAM handoff primitives: local validation

This stage implements only the independent
[handoff module](../scripts/validation/performance_live_handoff.py) and its
[tests](../tests/test_performance_live_handoff.py). It does not implement a live
controller or authorize a cloud comparison. No real credential, public audio
file, external request, guest desktop or network change was used by these tests.
The earlier refusal of the public-WAV / official-destination / stored-key request
remains effective; future live execution requires explicit human authorization.

## Public interface and wire contract

`ReadyExpected(plan_sha256, origins, producer_pid, producer_start)` describes
independently pinned evidence from the future authenticated launcher and reviewed
package inventory. `origins` contains the nine actual module hashes already
audited by the comparison core, including `inkecho.security`.
`receive_ready(fd, expected)` reads one bounded READY frame and returns its
validated dictionary; `validate_ready(ready, expected)` also checks a previously
decoded dictionary. Version, plan, all origins, PID/start identity, exact fields
and both arms' strictly integer zero budgets must match. READY is not itself
authentication or proof of consent: the future controller must authenticate the
SSH peer and independently establish the expected identity and hashes.

`Sender().send(fd, ready, expected, revalidate=..., read_key=...,
read_audio=...)` validates the writable pipe and READY before any callbacks.
After the complete-plan revalidation callback succeeds, it lazily reads exactly
`provider/qwen` and `provider/deepseek`, then reads and validates the original
audio bytes. The module never imports or initializes SecretStore. The future
controller supplies that backend only in its separately authorized live branch.

The wire representation is a four-byte network-order JSON length, bounded
strict UTF-8 JSON metadata, then the unchanged raw WAV bytes. Metadata has a
fixed version/schema, plan and audio hashes, byte count and the two canonical
credentials. It rejects unknown/duplicate fields, unknown/missing refs, invalid
keys and nonstandard JSON constants. No base64 conversion or audio re-encoding
occurs. A READY frame has the same bounded JSON framing without an audio body.

`Receiver().receive(fd, plan_sha256)` returns `(RamCredentials, original_bytes)`
only after metadata, audio and EOF validation. `RamCredentials.get(reference)`
provides Session's existing interface; unknown refs and access after `close()`
fail. Its representation is redacted. Sender and Receiver instances accept only
one attempt, including failures. Partial writes advance the offset; neither
instance reconnects, rewinds, retries a completed prefix or restarts delivery.

All IO accepts only Linux anonymous pipes: FIFO mode, matching
`/proc/self/fd/<n>` anonymous pipe inode, and the correct read/write access mode.
Ordinary files, named FIFOs, sockets and wrong-direction descriptors fail before
callbacks or content IO. Callers own the descriptors and must keep them private,
avoid concurrent descriptor replacement, and close the sending side after the
frame so the receiver can establish EOF. The future owner/controller must also
provide observation, cancellation and process lifecycle handling; these blocking
primitives do not impose a deadline or kill a process.

The default audio constraints are the fixed SHA
`0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf`,
571456 original file bytes, 282322 frames, mono PCM16 at 16000 Hz
(17.645125 seconds). WAV headers and the full PCM payload are checked in addition
to the file hash. Custom `AudioConstraints` are only an explicit synthetic-test
facility; a future live CLI must not expose an override of `PUBLIC_AUDIO`.

Metadata is limited to 16384 bytes, audio to 1048576 bytes, and each key to 4096
UTF-8 bytes. Errors contain only fixed codes, suppress backend exception context,
and do not print frames, audio, keys or arbitrary exception messages. Clearing
credential references is not cryptographic erasure of Python strings. This module
does not establish protection against OS swap, core dumps or privileged process
inspection, and never changes system settings.

## Reproduction and observed results

From the repository root:

```sh
.venv/bin/pytest -q tests/test_performance_live_handoff.py
.venv/bin/ruff check scripts/validation/performance_live_handoff.py tests/test_performance_live_handoff.py
.venv/bin/ruff format --check scripts/validation/performance_live_handoff.py tests/test_performance_live_handoff.py
```

On 2026-10-16, all 52 focused tests passed in 0.10 seconds; Ruff lint and format
checks passed. Root independently repeated the same 52 tests in 0.09 seconds.
Tests use real local `os.pipe()` descriptors, including a concurrent transfer of
more than 500000 bytes of generated silence, three-byte reads and seven-byte
partial writes. They cover strict READY identity/budget mismatches before lazy
reads, truncated prefixes/metadata/audio, excess trailing bytes, altered SHA,
malformed WAV parameters and truncated PCM despite a matching test hash,
duplicate JSON fields/refs, invalid UTF-8 and metadata, private callback errors,
one-shot failure behavior, forbidden descriptor types/directions and unchanged
ordinary file contents with zero lazy callbacks. These are local transport and
guard results, not real credential or cloud acceptance.

An additional combined run with the existing live-comparison and Noble-adapter
tests produced 124 passes and five failures under the restricted sandbox: four
existing loopback-TLS cases could not bind `127.0.0.1` (`EPERM`), and one existing
Noble owned-target control test could not wrap a socket descriptor (`EPERM`).
Those restrictions were not bypassed or used to change the other modules during
that run. Root subsequently repeated the same combined 129-test set in the
existing authorized local socket/TLS environment: all 129 passed in 6.82 seconds,
session 61676 exited naturally with code 0. The preserved log is
`build/performance-live-handoff-root-integration.log`. This environment comparison
confirms the associated local regression set passes with socket permission;
neither run used cloud services, real keys or GUI. It is not a full repository
workflow result or live handoff/cloud acceptance.

A separate root-authorized read-only probe, preserved under
`build/performance-live-handoff-stdio-prep`, observed the current
`docker exec -i → ssh -T` guest stdin as anonymous read-only `pipe:[280597]`,
stdout as write-only `pipe:[280598]`, and stderr as write-only `pipe:[280599]`.
The SSH owner PID 592547/start 28444276 exited naturally with code 0 and empty
stderr. That probe inspected descriptor metadata, not credential/audio payloads;
it demonstrates compatibility of this particular stdio route with the pipe
contract, not a completed handoff, general SSH compatibility or cloud support.
The future execution must still check its own actual descriptors.

## Remaining work

After review of this module, a separate controller/guest worker still needs to
implement the default-plan branch, fresh complete-plan/package/node validation,
authenticated READY handshake, private descriptor forwarding into shipped a13
Python, authorization-gated host credential/audio callbacks, producer handles,
the existing four-call budget, cancellation/join and normal TLS calls within the
actual Noble guest. Any necessary temporary connection of the existing Docker
bridge and restoration to network none remains separately gated. No controller,
network action, real key access or public-WAV upload is implemented or executed
by this stage. Existing Noble local TLS results remain separate evidence.
