# Private Mutter 46 done-boundary experiment

This is a source-overlay experiment, not an AppImage acceptance or supported system modification. All execution occurred in the independent Ubuntu 24 GNOME 46 guest `inkecho-mutter46-done-boundary-20261030`; no host desktop, input method or system library was changed.

## Reproduction and provenance

Official signed Ubuntu noble-updates/security Sources and Packages selected Mutter 46.2-1ubuntu0.24.04.18 matching the guest. SHA-256 of the upstream source archive is 009baa77f8362612caa2e18c338a1b3c8aad3b5fe2964c2fef7824d321228983. The source/deb manifests, command receipts and complete build outputs remain under `dist/mutter46-done-boundary-20261030`. 207 official dependency packages were independently hash checked before installation in this disposable guest only. Meson configured without network downloads; 782 control targets and the candidate incremental build completed. Upstream tests were disabled and are not claimed passed.

Control core ELF SHA: 488c4044c0888b204506291d35186708ee38386961417c2b55a41fdc0ff4e820.
Candidate core ELF SHA: 452112510fcd84903093d87f4bedc3a69a1fc4ea1a26f6e13d76cdfd9a1a5a93.
343 installed regular files per build were inventoried; only this core library differs. The candidate flushes pending text-input done before a new commit_text. This intentionally minimal root-cause prototype can split other pending preedit/delete transactions and is NOT a deployable fix.

Environment-only private startup initially failed because GNOME Shell prepends hardcoded system typelib/library paths, loading duplicate Clutter types and falling back to X11. No experimental text was sent in that failed session. The successful approach used an isolated guest mount namespace with a read-only private mutter-14 bind, then dropped back to the real test UID and executed the unmodified /usr/bin/gnome-shell. Private library hashes and actual Wayland session were checked before both cases. Global guest library bytes and mounts remained unchanged.

## Actual results and limits

Identical control and candidate runs each used three fresh mixed-text tasks (22 codepoints) and two same-window editable-control switches (1+21 codepoints). All ten tasks delivered exact public fixture content. Protocol diagnostics retain only event type, direction, object, timestamp, serial and length; report text is replaced by lengths.

The control did not reproduce the prior same-done overwrite in this run. Consequently candidate success is a negative control, NOT proof that the prior data-loss bug is fixed. The previous stock-compositor collision and separate reset-boundary loss remain valid independent failures. This patch does not prevent focus reset, provide client receipt ACK, guarantee arbitrary frontend behavior, or justify replay. No fixed sleep was introduced as confirmation. This run did not test composition safety of the private Mutter change, physical hotkeys, cloud providers, Ubuntu 26 or unchanged package qualification.

## Restoration

The seven original extension assets and all three original extension settings were restored. The private user-unit dropin and active symlink were removed. Stock Wayland Shell loaded the five original system libraries, with original core SHA a66cbe9b4409c17c83b88d355ea0fd360eb8f792be068245017ffac720cecc77; no private global mount remained. FUSE cleanup and owned-resource checks passed. Normal poweroff completed, original docker wait returned 0, container exited with PID 0, ExitCode 0 and OOMKilled false. The stopped child archive and full-stream verification receipt are preserved; independent full decompression was also verified. Guest-only SDK packages remain in the archived disposable guest, not the parent snapshot or host.

The original C patch is represented by `input/mutter-change.patch.bytes.json`: base64 decoding its data field reconstructs the exact original bytes, verified by its byte count and SHA-256. This avoids altering original diff context whitespace in a nested evidence patch. The original file remains unchanged in the persistent experiment input directory.

### Wait-handle provenance clarification

The current Mutter experiment container is `inkecho-mutter46-done-boundary-20261030`; its original tool wait session was **13970**, retrieved after normal poweroff with tool exit code 0 and output `0`. Session **84796** belongs to the earlier, separate `inkecho-ibus-r2-protocol-24-20261030` protocol-diagnostic guest, not this Mutter build. Earlier diagnostic results are background evidence and must not be used as this experiment's shutdown receipt. The current report originally stated only that the original docker wait returned 0, without a numeric handle. The structured final-state receipt below now makes this distinction explicit. Tool session numbers are agent execution metadata, not guest PIDs or durable docker identifiers; the final docker state and archive verification are independently preserved.
