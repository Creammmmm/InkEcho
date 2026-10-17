# Development conventions

Read [PROJECT_SPEC.md](PROJECT_SPEC.md) before choosing work. Its phase gates and
privacy rules remain mandatory. The root agent assigns work and reviews results;
subagents implement code. A passing unit test does not establish desktop support.

## Input semantics revised by the user on 2026-10-14

Recording starts independently of the current location or focus. Do not capture
or require an editable target before recording. Moving focus or the caret during
recording, transcription or polishing does not cancel the task. Output follows
keyboard semantics: send text to the cursor that has focus at delivery time. If
focus changes while text is being emitted, later characters may go to the new
focus; do not pin delivery to a previously captured object or window.

Use neither the clipboard nor a system input method. Transport availability and
Unicode behavior require fresh platform evidence; historical targeted AT-SPI
acceptance does not validate this revised behavior. Keep historical reports
intact and record new results in
[current cursor validation](current-cursor-input-validation.md).

Explicit cancellation, expired task IDs/epochs and replaced tasks still stop
unsent output at every asynchronous boundary and before each emission step.
Focus changes alone do not expire a task. Already dispatched events cannot be
retracted. Release owned held keys/resources during cleanup without dispatching
remaining text, and never replay ambiguous partial output automatically.

## Simple, consistent Python

- Use Python 3.12 or newer, four spaces, UTF-8 and an 88-character line limit.
- Let Ruff format code and check imports and ordinary Python mistakes. Keep one
  formatting configuration in `pyproject.toml`.
- Use `snake_case` for functions and variables, `PascalCase` for classes and
  `UPPER_CASE` for constants. Prefer descriptive, short English names.
- Use type hints on public functions and module boundaries. Prefer plain
  functions, small dataclasses and explicit conditionals to elaborate frameworks.
- Keep a function focused on one responsibility. Extract repeated behavior when
  it makes the caller easier to understand; do not create speculative layers.
- Use early returns to reduce nesting. Do not compress unrelated operations into
  one line or use clever expressions just to save lines.
- Explain non-obvious safety decisions in comments. Avoid comments that repeat
  the next statement. Document public behavior and errors, not implementation trivia.
- Keep provider HTTP details outside UI code and platform APIs behind adapters.
  Raise specific errors at boundaries; never silently swallow failures.
- Never log keys, audio, transcript text or user prompt contents. Never use the
  clipboard or a system input method as a delivery path or fallback. Treat explicit
  cancellation and stale tasks as hard stops, not focus changes.

## English commits with one purpose

Every commit message, including its optional body, must use English ASCII text.
Use this subject format, with a maximum of 72 characters and no trailing period:

```text
type(scope): imperative summary
```

Allowed types are `feat`, `fix`, `docs`, `test`, `refactor`, `build`, `ci` and
`chore`. Use a lowercase module scope such as `audio`, `injection`, `providers`,
`ui`, `packaging` or `workflow`. Start the summary with a lowercase imperative
verb, for example:

```text
feat(audio): capture microphone samples
fix(injection): stop output after task cancellation
docs(workflow): define local validation gates
```

Use the body when a change needs context: explain why it is needed, the observable
behavior, and relevant validation. Separate it from the subject with one blank
line and wrap body lines at 100 characters. Hooks enforce syntax and ASCII;
reviewers enforce actual English, meaningful verbs and a single clear purpose.

One commit should implement one module feature or one focused fix, with its
related tests and documentation. Do not mix unrelated modules, formatting sweeps
and behavior changes. Split dependencies into reviewable commits. Never rewrite
already pushed history merely to rename commits.

## Local verification before every push

Install the development dependencies documented in the project, then enable the
tracked hooks once in each checkout:

```sh
git config core.hooksPath .githooks
```

For each module change:

1. Implement the focused behavior and relevant tests. Run its tests while working.
2. Exercise the actual behavior locally. For desktop, audio, network and packaging
   work, record environment, commands or actions, observed results and limitations
   in a tracked Markdown report. Synthetic, mocked and headless checks must be
   labelled as such. Do not describe them as real microphone or desktop tests.
3. Review the diff, including safety boundaries, and make a focused English commit.
4. With a clean working tree, validate that exact commit:

   ```sh
   python scripts/validation/workflow.py run \
     --module workflow --evidence docs/DEVELOPMENT.md
   ```

   Choose the module name and actual evidence report for the change. The command
   runs Ruff lint, Ruff formatting checks and the complete pytest suite. It writes
   a local receipt under Git's `validation/` directory only after success. A
   failed rerun invalidates the previous receipt. No receipt is committed.
5. Push only after both module behavior and all automated checks pass. The
   pre-push hook requires a clean tree, the exact current HEAD, and its successful
   receipt with matching evidence. A new commit requires new validation.

A final complete-suite run may cover several independently reviewed commits in
one push only when every module has already passed its own local behavior checks
and the referenced evidence report records each module's results. Generic pytest
success alone does not satisfy the per-module functional gate.

The evidence parameter records the report; it cannot judge the truth of a manual
test. Reviewers must inspect its steps and results before allowing a push. For
documentation-only changes, review links and commands and use the changed document
as evidence; do not invent an application test. Never hand-edit receipts, disable
hooks, use `--no-verify`, or change tests simply to bypass a failed gate. Hooks are
local guardrails, not a security boundary against deliberate modification.

Push the current branch explicitly, for example `git push origin main`. The hook
blocks tags, branch deletion and pushing another commit because those actions cannot be
covered by the current HEAD receipt. Avoid bulk pushes with unrelated refs.

## Real-world acceptance gates

- Phase 0 must have reproducible Chinese/Unicode injection evidence before full
  application development proceeds. Record unsupported sessions honestly.
- Test explicit cancellation, expired/replaced tasks and late replies at every
  asynchronous boundary: none may dispatch further text. Test that recording
  starts without an editable target, focus changes during recording/processing
  do not cancel, output follows the current cursor, and switching focus during
  emission permits subsequent characters to reach the new focus. Do not weaken
  task-ID/epoch checks to achieve the focus behavior.
- Verify keyboard transport and mixed Unicode in the actual desktop, with neither
  clipboard nor system input method. Separately label synthetic/headless evidence,
  owned test targets and measured application support. Record cancellation during
  partial output, held-key cleanup and unavailable/denied transport behavior.
- Test global shortcuts, F13/F14, microphone input, Unicode insertion and overlay
  focus in the actual target desktop session. Maintain the compatibility matrix.
- For a provider, separate response parsing tests from an authenticated live
  request. Never commit credentials. Mark unavailable live validation as pending.
- Build the AppImage, launch that built artifact and exercise its pages and the
  working voice-input path. Test desktop integration, path repair and autostart.
  Source launches and offscreen screenshots alone do not validate the package.
- Validate on the Ubuntu versions and desktop sessions claimed as supported,
  including a relatively clean target environment. A developer machine test does
  not prove portability.
- Record each stage's actual results, reproducible steps and unresolved problems.
  Incomplete requirements remain incomplete even when the automated suite passes.

## Every AppImage: Ubuntu 24.04 and 26.04

A packaging task finishes only after the **same versioned AppImage and SHA-256**
passes actual-package acceptance on both Ubuntu 24.04 and 26.04. Building may
produce a separate candidate first. Until both checks and root-agent review are
complete, keep that candidate distinct; do not replace the stable entry, update
autostart or publish it. Do not create separate distro branches/packages without
a demonstrated technical need. See PROJECT_SPEC sections 18 and 24.3 and the
[packaging procedure](packaging.md).

One per-artifact report must bind the product source, artifact hash, packaged
version/inventory/origins and both environments' actual results. In each system,
exercise packaged startup/UI, the declared provider protocol including Qwen
realtime configuration/local WebSocket flow, mixed Unicode/current-cursor output,
partial cancellation and cleanup. Reuse the existing owned-target/local-TLS
probes where applicable; do not use a source launch or container smoke as desktop
acceptance. Keep all mutable test configuration isolated.

Identify actual Xorg, XWayland and native Wayland scopes separately. Record
microphone, physical shortcuts, overlay, integration/autostart and authenticated
cloud checks individually, including untested or unavailable cases. In
particular, GNOME 46's measured missing native-keyboard API is not a pass;
a separately verified Xorg path does not establish native Wayland support.
No packaging check automatically authorizes keyring access or cloud requests.
If the image changes, both previous artifact-hash acceptances become historical.

After the report is reviewed, run the existing complete clean-HEAD workflow
using that report as evidence. Its receipt verifies source checks and report
identity, not the truth of manual desktop tests; the root agent reviews those.
This additional product-delivery gate does not require every ordinary source
push to build an image or open a GUI. Existing hook requirements remain unchanged.
