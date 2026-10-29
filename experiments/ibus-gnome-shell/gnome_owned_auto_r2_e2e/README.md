# Owned automatic R2: actual26 + real zero-attempt keyboard fallback

2026-10-29 Ubuntu26 GNOME50.1 native virtual seat, independent network-none/QEMUrestrict-on overlay, stopped r2 backing+original backing readonly. No other docker containers running at preflight; no parallel24 write. Same revised candidate patch0ae16ce35bf772e29f3a25656b80e8173afd04ab38012174da9f3478567ddd43. Exact copied source-pins.json retained. No source/product changes during test, host desktop or credentials access, clipboard, default-auto activation.

## Real first-run results

actual.log, outer71132 natural0; self-owned actor2251. New version2 Shell extension, real authenticated Probe and exact-owner-bound client, proposed actual OutputRouter and systemdetector. HybridKeyboardInput was real; CountingHybrid only counts connect calls and awaits super(), no transport/ACK/floor/focus override. Fixture changes its OWN GTK field to create deterministic timing, never forces another application.

1. Deferredauto prepare, realProbe[ibus,:1.17], ownedbridge selected. Actual甲乙 across2fragments; keyboardconnect0. Submitted-unconfirmed scope diagnostic remains explicit.
2. Real known-zero bridge fallback: wrapper calls actualProbe twice. After second actualProof has been obtained, it changes self-owned focus native→simple before returning that unchangedproof, exercising the necessary freshCommit guard. ActualOwnedBridge insert reportsno_service/acknowledged_attempts0 (ObservedOwned records/rethrows unchanged). Actualrouter closes unsent bridge, selects actualHybrid and returns2; own simplefield actual丙丁. connect1. No fakekeyboard or fakeprobe result.
3. Same zeroattempt setup, actualHybrid emits戊; on_first_sent callback makesactivefalse. Cancel errorinput_cancelled; after1.3s field remains丙丁戊, no己/replay. Actualnative field remains甲乙. This is realfallback cancellation after firstkey, not pendingRPCcancel.
4. Detection-boundary cancellation: after real authenticatedprobe returns, activefalse. input_cancelled, keyboardconnect0, no newnativechar after1.3s.
5. Reallibpinyin fixedni, currentFocus/preedit[true,true]; actualProbe still selects guardedowned (not keyboard). auto insert refuses戊, ibus_delivery_unknown, keyboardconnect0. Closingrouter preservescomposition; fixedspace yieldsactualnative甲乙你. Actualsimple still丙丁戊. CLI exit1 recorded but actualengine libpinyin verified, as priorfixturefix.

## R2 differences and limitations

Earlier dac146 automatic evidence used the old unsafe error-to-none Probe and did not bind bridgeowner; do NOT substitute it for this revision. NewR2 service/UUID version2 is used here, no product defaults changed. Error/ownerABA/failclosed cases remain offline tested120Python+10JS, not livefault-injected. Per-Commit independent targetcheck is exercised by realno_service0. Same-windowwidget race duringpendingRPC/applicationenqueue remains a blindspot; this is not applicationreceiptACK. CancellationduringpendingRPC remains offlineonly.

Only26/Shell50/defaultnativeGTK3 and its simplewidget actualHybrid nativefallback validated.24/Shell46 not tested or advertised; noXWaylandfallback, arbitraryapps, packagedAppImage, physicalhotkeys/audio/cloud or productionautoenable claim. We did not independently snapshot nativevirtualkeyboardmap before/after; cleanup followed actual productionoutputsession/close and normal guestshutdown, without claiming a measured maprestore equality.

## Cleanup

Actor2251 natural0; engine restoredus. TemporaryV2candidate+fixture extensions deleted; enabled[],idle300,locktrue,sourcesxkb/us,actorabsent. Auxiliary pre-shutdownworkerps filter failed because guest lacksrg; cleanup.log preserves this, so no separate successful workerabsence audit claimed. Normalguestpoweroff/dockerwait0; finalcontainerexited0/Runningfalse/OOMfalse, so no guestworker remains after shutdown. All original logs retained; no extra sample run.
