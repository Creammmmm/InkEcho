# Ubuntu 26 real Pinyin attempt — inconclusive, 2026-10-30

## Actual scope

Ubuntu 26.04.1 Wayland session, owned GTK3 Entry explicitly using GDK_BACKEND=x11 (XWayland), actual GTK im-fcitx5.so, Fcitx5 5.1.19, official Resolute fcitx5-pinyin 5.1.12-1 / LibIME 1.1.14-1. Same native addon SHA-256 as the Ubuntu 24 Pinyin experiment: acd896aae8ab38ecca2685c0dd8639f2910e841176eadccf59ee4943b158c4de. The source/addon staging qualification override was test-only; no formal allowlist was changed and no AppImage was built.

Seven exact official packages were downloaded after signed Resolute InRelease/Packages verification and individually matched signed metadata hashes. Their combined download was 39,580,568 bytes and Installed-Size 48,189,440 bytes. dpkg installation succeeded within an independent guest child with all original backing/base disks read-only. No host user desktop or provider data was mounted.

## Results and strict failure

Both attempts successfully used default auto Fcitx routing to deliver the exact normal fixture 甲乙. The queried active engine was pinyin, the owned window was active/focused, and XTest input focus ancestry was verified against that owned window. However, n (r1) and n/n/i with one-second settling per event (r2) produced neither GTK preedit nor new committed text. Final preedit_length remained 0. The strict fixture stopped before attempting any candidate body during alleged composition. Therefore these attempts do not verify real Pinyin protection, cancellation during Pinyin, or Chinese candidate selection on Ubuntu 26. XTest calls succeeding and window focus being reported are insufficient to claim an application received keys. The responsible layer has not been isolated; no product fault or environment-only explanation is asserted.

The engine loaded official Pinyin and punctuation; the fresh private Pinyin history load warning is retained in the raw daemon logs. It is not established as the cause of absent preedit. No switch to fake IM events, synthetic server composition, clipboard, other target, or relaxed acceptance assertion was used to turn this into a pass.

Actor and private daemon exited 0 in both runs, and the exact prior systemd user IM hints were restored. Normal guest poweroff and container wait exit 0; no OOM. Raw final archive: /tmp/inkecho-fcitx-preedit-guard-20261030/pinyin26/guest-desktop-records.tar.gz, 1,871,903 bytes, SHA-256 6a98871392b1ff81eed6dd3f41ece876c56ecd3530539ab2b962221d7f7d910f. First-attempt archive and receipt remain separately preserved. run.py/actor.py and final results.json reproduce the strict check, not a passed guard sample.

## Resource preservation and remaining gate

The first full gzip archive attempt stopped at its explicit 50 MB output budget, preserving the complete child and removing only the incomplete archive. archive-budget-stop.json records this retained failure. Both task-local signed APT index directories were then losslessly archived, every original file hash checked against extracted archive bytes, and only duplicate original index files removed after no-open-FD checks. This recovered enough headroom for a complete child archive: 58,083,813 bytes, SHA-256 c6d8e730fe3dc19557efcde269795f8c453b8e96981d0fadc3df05a307c50f7b. Full-stream decompression matches original disk SHA-256 2a7362638cba33c2bcef787e342ddc7cbc82063758c212a7afc0a7ea858038ab. After no live guest, open FD, or other qcow backing reference was found, only the original stopped child was removed, releasing 144,904,192 allocated bytes. All full archives, original raw records, source, official dependency packages, and parent disks remain. cleanup.json and apt-lists-cleanup.json identify all files and hashes. Final user quota remaining was 179,795,968 bytes; filesystem free space is not the user quota.

Ubuntu 24 real ni-to-你 preedit protection passed in its separate experiment, but that result cannot be extrapolated to this Ubuntu 26 attempt or native Wayland applications. The same-AppImage dual-system release gate and formal staging qualification remain incomplete. No publication, deployment, commit, or push was performed.
