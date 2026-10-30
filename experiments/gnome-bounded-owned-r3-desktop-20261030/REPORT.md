# Bounded owned-context R3: isolated Ubuntu24 / Ubuntu26 desktop evidence

## Identity and scope

Frozen candidate patch: dist/gnome-bounded-owned-r3-20261030/gnome-bounded-owned-r3-candidate.patch SHA6f39fbe88e6f4ae3bf2db85613bbb70a2496341e3c2ea8ad005fb5e350e2a982. Both guests used the identical full85-file source manifest and exact seven candidate extension assets. This is SOURCE-OVERLAY research, not unchanged AppImage or release qualification. Published0.12.0 AppImage SHA7488566c708d3fc12de665d35dfc7c26a1902908c9fec63e3c905b1446757a78 supplied only interpreter/dependencies and the actual old-client negative probe.

Only one no-network guest ran at a time with read-only parents and independent RAM leaf disks. Ubuntu24.04.5 GNOME46 and Ubuntu26.04.1 GNOME50.1 used stock packaged Mutter. No host desktop, input method, libraries or configuration changed. Chrome154 used normal sandbox, fresh profile/password-store=basic, native Wayland text-input-v3, actual process/executable/profile and owned OS/DOM focus checks. Only fixed public fixture text was sent; protocol logs retain event metadata and lengths, never payload bodies. Synthetic GTK composition values are intentionally retained as owned fixture proof. No cloud, physical microphone or real global hotkey test is claimed.

## Actual results on BOTH systems

New strict client to old published V5: protocol negotiation refused before input, and actual default auto reported ibus_upgrade_required with both fields empty. After explicit candidate installation and normal GNOME reload, the actual old published Python client was refused by new Begin with authorization_failed, before input.

New authenticated task plus old Commit/CommitBatch requests: both rejected; independent foreign Cancel returnedfalse; the valid new request then delivered exactly one different public character, proving old requests did not mutate the current task. This did not replay an unknown request. Server-expired CommitBounded returnedunknown with zero DOM input. Two mixed Chinese/Unicode/newline tasks each delivered exact22/22. Same-window editable control switch delivered1+21. Explicit cancellation stopped after1; pending planner cancellation emitted0. Actual no-late observation was1.3seconds. Source API, identity, counts and per-case raw metadata are retained.

Real native GTK/libpinyin composition remained unchanged on both: fixed public n/i created nonempty preedit with empty committed text; auto output returned ibus_delivery_unknown, and the same preedit/empty committed value survived. The select command returned1, but independently queried engine was libpinyin and was the checked condition. The fixture actor was deliberately terminated (-15), not natural exit. Actual xkb:us::eng/input sources were restored.

## Protocol and remaining limits

New service hard-refuses legacy Begin/BeginBatch and Commit/CommitBatch without accessing or modifying current gate. The client strictly negotiates full BeginBounded(ssut), CommitBounded(ust), Cancel()->b signatures and authenticated unique Shell owner. Known complete old schema gives an upgrade diagnosis; partial/malformed schema is unavailable. The legacy explicit IBus V2 output mode remains its existing separate route; this candidate does not give V2 the new deadline guarantees.

Server same-machine monotonic microsecond deadline is fixed and can only tighten; each asynchronous boundary and final dispatch checks it. Expiry is unknown, never authorization for fallback/replay. Cancel authenticates current owner before invalidation and producer-wait abort. In-flight dispatch can precede observation of local cancellation; it remains unconfirmed and cannot be recalled or replayed.

Direct public Clutter commit plus stage-after-update/priority2 idle is an experimental PRODUCER ordering boundary, not receiving-client ACK or display completion. A750ms timeout is failure only. Successful fixed samples do not establish universal focus-reset immunity or arbitrary nested-loop correctness. Only owned Chrome textarea and real GTK composition are covered here; same-window control switch is not cross-window ABA or all applications. No generic compatibility promise or shared default change is made.

## Deployment, failures and restoration

The isolated staging helper verifies and backs up the complete old seven assets, disables and explicitly moves the old directory aside, then calls the actual installer into an empty directory. This is not proof of an automatic in-place upgrader. A normal GNOME reload occurred before new tests. An already-running old service is accurately diagnosed; the user must install matching files and reload/relogin, not merely trust a staged hash.

26 initial prepare failed before input because /mnt/input was not mounted after fresh boot. The failure receipt is preserved. Only the predefined private9p input/output shares were mounted; no product guard was relaxed. No other failing test was discarded. Original r1/r2 experiments remain separate and are not relabeled R3.

Both guests restored all seven original assets and three Shell settings plus actual input source/engine.24 additionally checked original stock Mutter library hashes. FUSE cleanup and owned resource checks passed. Both normal poweroffs and original waits are recorded (24:27172;26:21030); final container PID0/Exit0/OOMfalse and whole-stream archive digests are independently checked. Full archives and owned screenshots remain outside Git and are hash-pinned. All evidence bytes, including empty/trailing-whitespace logs, are preserved via reversible bytes.json wrappers where needed. Shared tracked code, version, commit and release were not changed.

## Preserved fixture metadata defects

The actual runner has a Python loop-variable collision: outer `method` begins as `auto`, but the legacy-during-new negative-protocol loop reuses it for `Commit` and `CommitBatch`. From that loop onward, printed method labels, later rows' method fields and screenshot prefixes may therefore say CommitBatch. These labels do not identify the positive delivery API. The ordinary cases still instantiate DefaultAutoOutputRouter and invoke the actual Session probe with output_method=auto; the explicitly isolated legacy-during-new case uses authenticated Client.begin/insert, negotiating BeginBounded/CommitBounded. Its two legacy requests are intentionally negative probes only. The exact source and raw outputs are retained unchanged; counts and labels must be interpreted together with this source, not taken as evidence that normal cases used legacy CommitBatch.

The raw report's static test_scope string also incorrectly retains “candidate R2 source overlay and JS”. That inherited fixture string is not a source identity. The actual85-file manifests and all seven installed asset digests identify the frozen R3 candidate; this report and complete source describe that scope accurately. No raw JSON, screenshot names or prior evidence bytes were rewritten to conceal either defect. These defects reduce metadata clarity, not the independently preserved source/asset identity or the actual DOM and cancellation observations. Future fixture runs should use distinct protocol_member and output_method variables and a checked candidate identity string.
