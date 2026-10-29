# GNOME owned automatic Probe→Router: bounded actual acceptance

2026-10-29. Ubuntu26 GNOME50.1 native virtual seat. Root confirmed24 stopped; docker ps startup inventory empty. Started only this independent network-none/QEMUrestrict-on overlay with old r2 backing+original backing readonly. New overlay74MiB, no quota errors. Same proposed auto patch dac1468c1596b0dfe70aa6b67f86b9a5cfd33aa075f4c117720329ca8f43e6b2. Full local source snapshot plus candidate files pinned source-pins.json. No shared worktree writes, app default activation, host desktop/bus/IBus, credentials or clipboard.

## Actual first-run outcomes

actual.log outer5701 natural0; self-owned actor2252, real authenticated standard session bus/Shell unique owner:1.17. Existing real system detector used, not stubbed. Actual proposed Probe extension and PythonOwnedAutoOutputRouter/Client loaded from private source. No fixture substitutes for Probe, commit, Shell owner authentication or real IBus.

- prepare_task(auto) remains deferredkeyboard. At output, real Probe returns[ibus,:1.17], router selectsibus. Separate甲/乙 fragments actually appear甲乙; keyboardconnect0. End scope retains submitted-unconfirmed diagnosticibus_delivery_unknown, caught explicitly by harness. This does not acknowledge application receipt as a protocol.
- Button focus: actual Probe returnsNone. Router attempts existing keyboard fallback; deliberately non-sending keyboard fixture raisesunsupported_target onconnect, connectcount1. No丙 emitted. This validates absence of IBus selection and no accidental IBus output, NOT actual physical/simulated keyboard fallback capability.
- Cancellation after a real authenticated detection: wrapper sets activefalse immediately after actual probe returns. Router raisesinput_cancelled beforeconnect/Commit, keyboard0;1.3s own text remains甲乙. This is a deterministic cancellation boundary after real detection, not cancellation duringpending D-Bus RPC.
- Real libpinyinni composition: fixture reportscurrentFocus/preedit[true,true], actualProbe still selects owned. The blocked status does not leak into keyboard fallback: auto insert戊 yieldsibus_delivery_unknown and keyboardconnect0. After bridge/router close, real preedit remains; fixedspace producesactual甲乙你. No戊, composition preserved. CLI switch exit1 recorded while actualengine libpinyin verified (known fixture pitfall).

## Cleanup and limits

Actor2252 naturalexit0; engine restoredxkb:us::eng. Temporaryextensions deleted,enabled[],idle300,locktrue,sourcesxkb/us,actorabsent. Normalguestpoweroff/dockerwait0; finalcontainerexited0/Runningfalse/OOMfalse. No further samples. Shared/userdesktop untouched.

This is one default nativeGTK3 own receiver onUbuntu26/Shell50, notGTK-ownedIBus,24/Shell46,arbitraryapps,samewindowpendingfocusrace,appreceiptACK,pendingRPCcancel,realkeyboardfallbackdelivery,packagedintegration or defaultautoactivation. OriginalV2 explicitpath remains structurally preserved and offline tested, not exercised here. No auto default should be enabled beyond reviewed explicit scoped activation; sameartifact dualUbuntu package gate remains. Root may review and integrate candidate separately.
