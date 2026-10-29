# Ubuntu 24 actual Pinyin preedit guard — 2026-10-30

## Scope and result

Ubuntu 24.04.5 X11, Fcitx5 5.1.7, official Noble fcitx5-pinyin 5.1.3-1build3 and LibIME 1.1.5-1, owned GTK3 Entry with actual im-fcitx5.so. Native candidate SHA-256 `acd896aae8ab38ecca2685c0dd8639f2910e841176eadccf59ee4943b158c4de`. This was isolated source/addon staging with an explicitly test-only SHA qualification override; it was not an AppImage or formal staging qualification.

Final r6 exit 0: default auto route delivered 甲乙 via Fcitx; engine query was pinyin; real XTest n/i created GTK preedit length 2. During this real composition, new output 戊 returned fcitx_composition_active with zero acknowledged attempts. The committed baseline and preedit length remained identical. Space then committed the original ni as 你, proving a real Pinyin composition survived; no delayed 戊 appeared. A new 己庚 task canceled after the first acknowledgement left only 己 after 1.2 seconds. Actor and private daemon exited 0, and exact prior systemd user IM hints were restored.

The frontend's first n sometimes committed literally after engine selection, even with 600ms settling. Final fixture checks the actual owned state: only if that first n was committed with no preedit does it send one additional n, then i. It requires exactly two preedit characters and the expected committed baseline before testing product output. That bounded fixture adjustment is not a product retry or fallback. XTest events are synthetic desktop events targeting only an independently verified owned X focus; no human physical-key claim is made.

## Reproduce and raw evidence

The source fixture run.py and actor.py require the candidate source/deps/private manifest layout used by the prior addon desktop experiment. Install only the eight exact packages in package-plan.json after verifying the signed official Noble InRelease and Packages index; their download hashes are in package-verification.json. Run the fixture as the isolated graphical guest user with its real user bus and GTK Fcitx frontend. No host desktop, clipboard, provider secrets, or external target is used.

Raw task-local records: /tmp/inkecho-fcitx-preedit-guard-20261030/pinyin24/guest-desktop-records.tar.gz (2,355,123 bytes), SHA-256 ba570b1598a1c3cdd9ff527bff4a4462f01d1dd62964f2d03e3d2bd51a8ce1b8. Full final receiver results are in results.json. All failed-run receipts and exact earlier fixture sources remain alongside this archive.

Failures retained: added package 9p device initially shifted NIC PCI position, causing configured enp0s4/enp0s5 mismatch and SSH timeouts, before installation or product input. Normal ACPI shutdown exit 0 preceded correcting only that share order. r1 fixture used a conflicting record keyword and wrong remote switch syntax; it stopped before input keys. r2/r3 strict baseline assertions stopped before candidate body because first n committed literally; r4 successfully protected real one-character i preedit but did not prove Chinese candidate selection. r5 observed all three generated n/n/i in preedit, failed strict expected length, and again sent no body. r6 observes first-key state explicitly and passed the ni-to-你 requirement. No failed sample is silently relabeled passed.

## Cleanup and limitations

Normal guest poweroff and container wait exit 0; no OOM. Full stopped child was gzip archived, stream-decompressed SHA checked, then its original disposable layer removed only after no live container/open FD/other qcow reference checks. cleanup.json identifies the preserved full archive and exact released allocation. Original backing/base disks, all source, official .deb packages, and raw evidence were preserved.

This covers one Ubuntu 24 X11 GTK3/Fcitx Pinyin sample. It does not establish Ubuntu 26 real Pinyin, Wayland-native GTK, other engines, browser/Electron clients, or hidden client-side composition states. It does not complete the same-AppImage dual-system release gate or promote the formal staging allowlist.
