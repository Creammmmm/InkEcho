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

## Feature branches and release ancestry

Prefer an independent branch for each feature. After acceptance, merge completed
work back into the repository's default main branch (currently `main`). Before
any release, its source commit must already be merged into and reachable from
that main branch. Verify the current remote state before merging or publishing.

A fast-forward merge is sufficient; do not require an extra `--no-ff` merge
commit. If a merge does create a new commit, it still follows the version
increment, validation and Git hook rules. Branches do not bypass the complete
checks required before pushing or the same-artifact dual-Ubuntu release gate.

## Local verification before every push

Install the development dependencies documented in the project, then enable the
tracked hooks once in each checkout:

```sh
git config core.hooksPath .githooks
```

For each module change (see the
[current acceptance checklist](acceptance-checklist.md)):

1. Implement the focused behavior and relevant tests. Run focused tests while working;
   do not repeatedly run the complete suite for unchanged modules.
2. Exercise the actual behavior locally. For desktop, audio, network and packaging
   work, record environment, commands or actions, observed results and limitations
   in a tracked Markdown report. Synthetic, mocked and headless checks must be
   labelled as such. Do not describe them as real microphone or desktop tests.
3. Review the diff, including safety boundaries, and make a focused English commit.
4. With a clean working tree, validate the final reviewed commit once:

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

Do not repeat a successful complete run without changed source, evidence or an
unresolved failure. A final complete-suite run may cover several independently
reviewed commits in
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

## Per-commit application versions

The release-preparation commit moves the exact reviewed parent
`76d8d5591017820caafed55e3741ab998fc44de7` from `0.1.0a18` to `0.2.0` once.
Afterward ordinary commits, including documentation and empty commits, keep X.Y
and increment Z by exactly one: X.Y.Z becomes X.Y.(Z+1). A release-preparation
commit is the explicit exception: keep X, increment Y by one and reset Z to zero
(X.(Y+1).0). For example, 0.2.2 becomes 0.2.3 for an ordinary commit or 0.3.0
for the next release preparation. X changes only when the user explicitly
specifies it; there is no automatic major bump. Such a user-directed change must
synchronize the three metadata fields and deliberately adjust the validation
rule; the current gate rejects major changes. No skipped patch/minor or
prerelease transition is accepted.

Before staging a commit, run:

```sh
python3 scripts/validation/versioning.py bump
```

For an explicitly requested release, prepare its source commit with:

```sh
python3 scripts/validation/versioning.py bump --release
```

This prepares the next minor version with patch zero; it does not build, tag,
create a GitHub release or publish anything. Release publication still requires
the normal actual-package acceptance and authorization.

Either explicit helper modifies only the working copies of `pyproject.toml`,
`src/inkecho/__init__.py` and the local `inkecho` package entry in `uv.lock`.
It neither stages files nor creates a commit. Review and stage all three version
changes with the focused feature or documentation. The executable pre-commit
hook checks those three **index blobs**, not unstaged working files; omissions,
unsynchronized versions and transitions other than the next patch or next
minor.0 reject the commit. The hook validates numbers, not whether a release is
actually being published; agents must use the minor exception only for an
explicitly requested release-preparation commit. Hooks never
silently edit files. Do not use `--no-verify`.

There is no special amend detection or exemption. A bare `git commit --amend`
that retains the current version fails the same next-patch check. Do not amend
published history; use the next explicit commit/version. The gate is a local
workflow guard, not protection against deliberately replacing hooks.

A release tag binds the exact validated release-source commit, not a later
report-only development successor. For v0.2.0, build and validate the 0.2.0
commit on both Ubuntu systems, then record the results in the next 0.2.1 commit.
The latter also synchronizes all three version fields but does not require
rebuilding or pretending its source is the released 0.2.0 artifact. Final source
checks run on that exact clean successor HEAD. Preserve the frozen 0.2.0 source,
its earlier receipt, actual artifact SHA and dual-OS evidence. The authorized
GitHub Release API targets the exact 0.2.0 commit; ordinary branch pushes retain
the existing pre-push hook, which still rejects tag pushes.

## Real-world acceptance gates

Use the [current checklist](acceptance-checklist.md) to choose the required checks.
One isolated run may cover several requirements; historical probes are not a
standing execution list. Source-only changes do not automatically require a new
package. Apply additional UI sizes/styles, physical devices and performance
matrices when the changed behavior or a support claim requires them.

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
No packaging check automatically authorizes real credential-file access or cloud requests.
If the image changes, both previous artifact-hash acceptances become historical.

After the report is reviewed, run the existing complete clean-HEAD workflow
using that report as evidence. Its receipt verifies source checks and report
identity, not the truth of manual desktop tests; the root agent reviews those.
This additional product-delivery gate does not require every ordinary source
push to build an image or open a GUI. Existing hook requirements remain unchanged.


## Plaintext credentials revised by the user on 2026-10-19

Use the selected ConfigStore root's dedicated credentials.json for all supplier
authentication fields. It is intentionally plaintext, not encrypted. Provider
records retain key_ref; do not relax provider-parameter secret rejection. Bind
FileCredentialStore explicitly to that root, including --config-dir and probes.
Never read/import/delete old system-keyring entries automatically. Existing
references without a local value require re-entry. Keep directory0700/file0600,
owned regular files, no symbolic links, atomic writes and sanitized errors.
Never commit real credentials or log their content. Historical package reports
retain their original storage facts; only a newly validated package changes the
installed runtime behavior.
