# Ubuntu24 owned-auto R5 compatibility attempt: environment blocked

2026-10-29. Independent overlays over stopped Ubuntu24 perf VM parent, original state/base/seed/secrets mounted readonly, Docker networknone and QEMU restricted usernetwork; no host desktop/IBus/network configuration changes. All prior26 guests stopped before start. Candidate copy only: extension metadata shell-version changed from original50 to46, descriptions mark testcopy; original /tmp/inkecho-owned-auto/experiment-r5.patch unchanged. This is NOT original candidate/package acceptance.

## Actual results

No SSH connection completed, no extension deployed, no input/engine/text or GUI operations occurred. Thus normal/realpreedit/fallback/cancel all remain NOT RUN on24. Failure does not establish unsupportedGNOME46 APIs or product failure.

- First independentguest: reused26 launcher fixedMAC. SSH timedout; serial repeatedly networkd-wait-online. SuspectedMAC mismatch with known24 launcher (which uses defaultMAC), not proven. QMPsystem_powerdown sent and POWERDOWN event recorded, original60s wait timedout. AuthorizedpreciseQMPquit then originalwait0; failed-container.json preservesexit0 while log explicitly shows abnormalshutdown. Never call this normalguestshutdown.
- Secondnew independentoverlay uses known24 defaultMAC, firstoverlay untouched. SSH stilltimedout, networkd-wait-online repeated. Serial NICenp0s2 renamedenp0s4; knownworking24 launcher also provides two9p devices absent in this26-derived layout. Possiblepersistentnetwork/PCI-layout mismatch remains hypothesis, not a rootcause claim. No thirdstart or unbounded retries. Root instructed stop on repeatedenvironmentfailure; obeyed.

## Limits and next step

Metadata46-only candidate copy prepared but never deployed. No actualguestOS/Shell version query succeeded; parent/provenance indicate24 but containerstartup logs cannot substitute actualdesktop46 acceptance. Inputmethods/module/version availability uninspected; no compatibility assertions. Reuse exactknownworking24 launchlayout in a separately reviewed futuretask if needed; don't change originalhost/parentconfig. PurePythondbus-next source dependency staged from existinglocalvenv, no download or installation, not exercised. Sharedworktree unchanged and defaults not activated. Existing26 R5 actualevidence remains separate.

Cleanup status is recorded in network-r2-poweroff.log/final-container-r2.json/forced-r2-quit.log as applicable; anyQMPquit is abnormal notnormal. Bothcandidateoverlaydisks andoriginalfailurelogs retained as evidence, notpackagedoruploaded.


## Final stopped state
Firstguest ACPIwait60 failed; preciseauthorizedQMPquit completed, originalwait0, failed-container.json exited0/Runningfalse (abnormalshutdownexplicit). Secondguest ACPIpowerdown succeeded: serialreaches systemd-poweroff/poweroff.target and reboot:Powerdown, originaldockerwait0; final-container-r2.json exited0/Runningfalse/OOMfalse. No QMPquit used on secondguest. Finaldockerps empty. No additional starts.
