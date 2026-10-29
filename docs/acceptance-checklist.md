# Current acceptance checklist

当前验收只执行与交付有关的必要检查；同一份结果可以覆盖多个要求。
每次打包仍须由同一 SHA 的包在 Ubuntu 24.04 和 26.04 分别完成实际验收。

Use [PROJECT_SPEC](PROJECT_SPEC.md), [DEVELOPMENT](DEVELOPMENT.md) and
[packaging](packaging.md) for binding requirements. The
[2026-10-12 checklist](acceptance-checklist-2026-10-12.md) preserves historical
results, including superseded target capture, AT-SPI and keyring behavior; it is
not a current execution plan.

## Source changes

During development run focused tests and the local behavior checks relevant to
the change. Before pushing, run the complete clean-HEAD workflow once for the
reviewed final source, with evidence for each changed module. Do not repeat the
full suite after an unchanged successful run. New commits require new receipts.
Source changes alone do not require building an AppImage.

Keep regressions for explicit cancellation, stale/replaced tasks and late replies;
current-cursor delivery; cleanup of held keys and mappings; bounded protocol
handling; credential isolation and atomic owner-only files; and actual startup/IPC.
Neither focus changes nor an uneditable initial location cancel recording.
Never substitute the clipboard, replay uncertain input, or hide failing tests
with selection/skip changes. System input methods are an authorized optional
output path; retain keyboard output, select by actual capability, and do not
claim untested input-method paths as supported.

## Every package or release: four required categories

Record **the same version and SHA-256 AppImage** on actual Ubuntu 24.04 and 26.04.
Until both systems pass and the root agent reviews the evidence, it remains a
candidate: no stable replacement or publication. One run may satisfy several
requirements; do not restart probes solely to populate separate report sections.

| Category | Required evidence for each artifact |
|---|---|
| 1. Identity and integrity | Frozen product commit/version, artifact SHA-256, packaged inventory and application source/origin binding. Preserve existing stable files and user configuration. |
| 2. Packaged entry and UI | Actual bundled entry with a private profile: show, normal quit and owned-process exit; after exit, cold toggle/cancel/quit must not revive it. Never toggle the live default instance to test lifecycle; recording belongs only to a local fixture that explicitly requires it. Open the five current pages (overview, model configuration, polishing styles, settings, help), confirm version and readable navigation. Exercise changed UI behavior. |
| 3. Audio and provider pipeline | Isolated configuration and disposable credentials; representative complete local HTTP/WebSocket/SSE pipelines, including Qwen realtime manual/VAD where claimed; streaming/final-success ordering, failure/cancel/stale handling and resource cleanup. Expand the protocol matrix for new or changed adapters; do not repeat every vendor adapter on each package. Keep parameter-safety coverage in the full unit suite. Local fixtures establish protocol behavior, not real vendor accuracy or account access. |
| 4. Desktop delivery and cleanup | Actual declared session/backend, mixed Unicode at the output-time cursor, focus switching and partial cancellation; exact owned-target results, balanced held-key release, restored mapping and cleanup, overlay/control focus behavior. Record native Wayland, XWayland and Xorg separately. |

For a formal AppImage, verify at least one actual FUSE mount and bind its runtime
identity to the same inventory. A guest using extraction must state that path and
its FUSE limitation; multiple mount rounds on every system are not required.
A changed image invalidates previous artifact-hash acceptances on both systems.
Container/headless/source runs do not replace actual package/session acceptance.
GNOME 46 Xorg evidence does not establish native Wayland support.

## Extend only for a changed feature or a support claim

- UI layout/style changes: inspect relevant dimensions, long content, expanded
  details and affected overlay styles. Metadata-only packages still open all five
  pages but need not repeat every UI interaction or size/style combination.
- Audio/hotkey/integration changes: test the affected physical microphone,
  activation, permissions, desktop entry or autostart behavior in the relevant
  environment. Synthetic tone and injected adapters must be labelled accordingly.
- Provider changes or real-service claims: distinguish local protocol fixtures
  from explicitly authorized live authentication/model/recognition checks. Never
  read real credentials merely to complete a checklist.
- Input/transport/performance changes: exercise the affected backends and
  cancellation boundaries; measure the relevant latency with a defined sample
  and report limitations. Old comparative experiments are not standing gates.

List untested physical devices, real cloud requests and session scopes explicitly;
do not turn missing evidence into a compatibility claim. Reuse one isolated run
when it covers the needed contracts; do not duplicate all historical probes.

## Evidence and review

Each report records source/artifact identity, OS and desktop/session/backend,
commands or actions, isolated fixtures, original process completion status,
observed results and unresolved limitations. Screenshots require visual review;
file counts or dimensions alone are insufficient. Keep generated raw evidence in
its reported location and summarize the actual scope in tracked documentation.
Never log credentials, recorded audio, transcript contents from real users or
account balances. Review the evidence, then run the existing full clean-HEAD
workflow for the final source/report commit; keep hooks unchanged.
