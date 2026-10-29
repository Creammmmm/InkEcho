# Ubuntu24/GNOME46: isolated owned-auto R5 test-copy acceptance

2026-10-29, real Ubuntu24.04.5LTS / GNOME Shell46.0, machine-id5f18d1e571c14b3ab94646a8664e7595, virtualseat. Original24 disk/base/seed/key readonly, newoverlay only; Docker networknone and QEMUrestrict-on. No simultaneous26/24VM. Host desktop/inputmethod/systemconfig untouched. No sharedworktree/defaultauto/package/release changes.

## Version and dependency differences (mandatory scope)

Original R5 patchfd163786bfcdefd3894d8cac7687fe71a27525326663562bf5a8e267df617db4 still advertisesShell50 only. Only the disposable testcopy candidate metadata now46; Python/JS runtime logic unchanged. Fixturemetadata also46. GNOME46 lacks PanelService.forward_process_key_event used by50fixture; only testfixture uses Shell's own IBus.InputContext.process_key_event(key,0,0) instead, still PID/title/focus-gated and restricted fixedni/space. This is not a productcandidate runtime change or originalAppImage acceptance.

Originalguest defaultsXorg viaWaylandEnablefalse and no pinyin. TestsavedGDM/AccountsService/gsettings, enabledWayland only inoverlay, installed6official24 packages15.2MB: ibus-libpinyin1.15.7-1build2,libpinyin15+data2.8.1-1build3,libopencc1.1+data1.1.7+ds1-1ubuntu0.1,libmarisa0 0.2.6-14ubuntu4. Host downloaded officialarchiveUbuntuHTTPS exactAPTURLs and checked size/SHA256 fromguestAPTmetadata; pinsretained. Guestnever gainedexternalnetwork. Python3.12 usedlocalpurePython dbus-next stagedfromexistingvenv, nothostinstalled. Testonlydependencies were removed afterward.

## Environment failures retained

Earlier two26-derived24 launch attempts are separate evidence under /tmp/inkecho-owned-auto-r5-ubuntu24/. Newrun restores successful24exactPCIdevice order including2private9pdevices,defaultMAC,4GiB RAM. SerialNICnowdirectenp0s4; SSH initiallytimedout while networkwait~120s, but latercloudinitcompleted and SSHworked. Prior successful24serial showed same120s wait, so MACalone was not establishedrootcause. No claim to have fixed24systemnetwork; launcherlayout+waiting overcame testfixtureobstacle.

native.log preserves an earlySSHtimeout afterreboot, zeroactor/input. native-r2.log: actor2179 natural0, fixtureoutofdate50 rejectedArm beforeanytext; dynamic actualsessionID1 (hardcoded2 read failed) noted. extension-diagnostic confirms realWayland and candidateACTIVE. Afterfixturemetadata46/GDMreload, native-r3.log passedinput/cancel but failedfixedni because50-onlyPanelService methodabsent; actor3395 natural0. Separatepreedit-only fixturefixtest below passed. Do not labelentireoriginalnative-r3 run successful.

## Actual necessary samples

- Native-r3: actualauthenticatedProbeibus/:1.24→ownedauto selection. Twofragments甲/乙 actual甲乙, keyboardconnect0. Detection-boundarycancel afterrealProbe raisedinput_cancelled, keyboard0, no丁 after1.3s. Actor3395 natural0, restoredusengine.
- X11.log: freshselfowned GTK3XWayland window, GDKx11 and simpleIM. ActualProbeNone; actualOwnedAutoRouter→realHybridKeyboardInput xonlytrue, selectedkeyboard/connect1. Actual丙丁. Onnexttaskfirst戊 callbackactivefalse causesinput_cancelled;1.3s tailactual丙丁戊/no己. Actor3660 natural0. This proves confirmed-negativepreflightfallback on24XWayland, NOT bridgeCommitno_service0 fallback on24native. Actual26Commitzero-to-nativefallback remains separateevidence.
- Preedit.log: freshselfownednative GTK3, realinstalledlibpinyin and fixedni processedbyShell's owncontext; actualcurrentFocus/preedit[true,true], actualProbeibus/:1.24. Autooutputrefused戊 withibus_delivery_unknown andkeyboard0. Closingrouterpreservedcomposition; fixedspaceactual你, no戊. Actor4671 natural0; usenginerestored. CLIengineexit1 recorded whileactualengineverifiedlibpinyin, knownfixturequirk.

## Cleanup and limits

cleanup.json/rawrestored: GNOME46.0/sessiontestedwayland, exactmoduleworkerPIDs[],allactorsabsent. Restoredoriginalgsettings exactly: extensions[],idleuint320,lockfalse (these are original24testlabvalues, NOT26's300/true). GDMrestoredbyteidentical, AccountsServiceunchanged, engineus. Removedexact6newpackages exit0, temporarycandidate+fixtureextensionsdeleted. NormalSSHsystempoweroff and originaldockerwait0; finalcontainerexited0/Runningfalse/OOMfalse. No additionalstart/inputtest.

This is testcopysourceacceptance ondefaultnativeGTK3 andGTK3XWaylandsimple only, not original50metadata, AppImage, arbitraryapps/GTK-ownedIBus, widgetpendingfocusrace, appreceiptACK, physicaldevices/cloud or productionautomaticactivation. Snapshot/identityfault/concurrency/ownerABA remainofflineonly. Generic24nativekeyboardfallback is still unsupportedbyMutter46UnicodeAPI; that was NOT silentlymarkedpass. No compatibilityclaim outside explicittestedscope. OriginalR5metadata/defaultapp remain unchanged.
