# IBus long-session validation

The bounded owned IBus route now negotiates a distinct long-session protocol. It fixes one task ceiling at Begin, no later than the caller's absolute deadline or the 555-second protocol cap. Each v2 commit also has a shorter independent dispatch deadline. A complete v1 service keeps its original bounded protocol and ceiling. Malformed or partial schemas fail closed. An existing older extension is not overwritten automatically.

The new ceiling does not create a target-application acknowledgement. A request already dispatched before cancellation can still be in flight; no new text request is issued once the local task is inactive, and an uncertain result is not replayed. The single-request deadline and cancellation are not an atomic cross-process operation.

## Desktop experiments

On 2026-10-31, separate offline Ubuntu 24.04 and 26.04 GNOME Wayland QEMU snapshots used an old AppImage as the dependency runtime and the candidate source as an overlay. They are **source-candidate tests, not acceptance of an unchanged AppImage or a release**. The old backing disks and input shares were read-only, with independent guest write layers and no external network, real microphone, provider credentials or user text. Each test used a synthetic recorder, synthetic transcription and streaming polishing provider, and a self-owned native GTK text field. The stream result differed from the transcription.

The guest launcher checked the source's regular-file manifest; the 26 run checked all 94 listed files against the final manifest before testing. The 24 stage checked the preceding 94-file version, after which the locally observed D-Bus cleanup fix changed the Python client in the test overlay; the final 24 and 26 input manifests match, but the full final 24 tree was not independently rechecked inside the guest before the runs. The manifest excludes symlinks and cache files. After the experiments, the application version metadata was advanced for this commit, so the exact post-commit source tree was not the tested overlay. The common final manifest SHA-256 is `7c1372b24db3eb004e38be5ea6fcb7195923303bba57f955977bc3d3f1fc7cad`.

Each long test used a single actual Session and v2 Begin, with a deliberate 61-second gap in the synthetic polish stream. The recorded first-to-last commit spans and independently observed GTK text were:

| Guest and selection | Commit span | Observed synthetic text | Session result |
| --- | ---: | ---: | --- |
| Ubuntu 24.04, auto | 61.965 s | 44 of 44 characters | unconfirmed |
| Ubuntu 24.04, explicit owned IBus | 61.997 s | 44 of 44 characters | unconfirmed |
| Ubuntu 26.04, auto | 62.014 s | 44 of 44 characters | unconfirmed |
| Ubuntu 26.04, explicit owned IBus | 62.025 s | 44 of 44 characters | unconfirmed |

The harness recorded the actual selected IBus path, one v2 Begin, individual commit deadlines no later than that task ceiling, target focus, target content and Session outcome. These observations concern the controlled GTK field, not a general receipt guarantee. Each guest also ran a programmatic cancellation after partial streaming: 39 synthetic characters were present, no new Commit was recorded after cancellation, and the later synthetic suffix was absent. This is not a physical Escape test or proof that an already in-flight request can be retracted.

On each snapshot, the previously installed legacy asset set and a separately staged complete v1 set were checked with the candidate installer: install and enable were refused with an upgrade message and the checked files remained unchanged. The candidate was then staged explicitly in the disposable guest and the guest was restarted. Both guests restored the original extension and the recorded GNOME extension settings, unmounted the AppImage and shared directories, shut down normally, and archived the disposable layer. AppImage cleanup and restoration have separate local records; shared-directory unmount was observed in the command output but not separately saved, so the current archive alone cannot independently verify it. Both containers reported exit 0 and no OOM; archive streams were verified. Raw guest logs and snapshots remain local and are not included in this report.

The first Ubuntu 24 staging attempt found the initial extension was legacy rather than v1; a subsequent fixture copy was correctly refused because its files were group-writable. The script restored the initial extension; after correcting fixture modes, both old-version checks passed. The initial strict SSH host-key check also rejected the stale known-host entry; the guest's fresh public key was checked against its virtual serial record before a new strict connection. Those two staging failures and the SSH key comparison are reported from the tool output at the time; independent raw logs for them were not retained, so the current archive alone cannot verify those observations. No SSH host keys or guest initialization material are included here.

## D-Bus cleanup observation

Two initial Ubuntu 24 v2 cancellation runs finished without a later Commit and showed an unhandled `BrokenPipeError` from a dbus-next write Future during disconnect. The second console was saved; the first error is recorded only in the tool output at the time and cannot be independently verified from the retained console files. An old-client comparison used the same guest and v1 protocol, with only its asset-recognition module overlaid to recognize the candidate service; one cancellation run did not log that error. An earlier comparison stopped before input because the old asset manifest did not recognize the candidate and is not a passing comparison.

The candidate's private owned-bus subclass now observes the separate per-send Future discarded by dbus-next while preserving the request's error and unknown-delivery behavior. A focused test checks that a caller awaiting the same failed Future still receives its exception. Two subsequent Ubuntu 24 candidate cancellation runs and one Ubuntu 26 run showed no unhandled Future error; this limited observation does not establish that every disconnect race is fixed.

## Reproduction and limits

Run the relevant offline regression set with `pytest -q tests/test_owned_long_bounded.py tests/test_owned_bounded_protocol.py tests/test_owned_bounded_gate.py tests/test_owned_bounded_session.py tests/test_owned_bounded_installation.py tests/test_fcitx_owned_handoff.py`. The JS gate fixture covers both pending-request rejection and the microtask interval between inner completion and outer cleanup. The Session tests cover streaming and non-streaming task ceilings; the installer tests cover complete old sets without replacement. These tests use controlled fakes, not a desktop.

The desktop test requires disposable GNOME Wayland guests, a known old runtime, a source overlay and separately owned native controls. It does not validate Xorg, XWayland, Fcitx, physical shortcuts, microphone capture, cloud requests, arbitrary applications, pending cancellation at every possible instant, or the same final AppImage on both Ubuntu versions. Follow the existing packaging acceptance gate before presenting any artifact as a supported release.
