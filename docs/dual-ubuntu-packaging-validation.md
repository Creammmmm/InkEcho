# Same-artifact Ubuntu 24.04 / 26.04 packaging gate — 2026-10-17

This module makes the user's continuing dual-system packaging requirement
persistent. It changes instructions and small local preflight checks, **not an
application version, artifact or deployment**. No AppImage was built, no real
Docker/container/GUI process was started, and no microphone, keyring or network
was used for this module.

## Persistent delivery requirement

- `AGENTS.md` adds one entry pointing to the project specification's packaging
  and acceptance requirements; all previous constraints remain unchanged.
- `docs/PROJECT_SPEC.md` sections 18 and 24.3 require the same versioned AppImage
  and SHA-256 to pass actual-package checks on both Ubuntu 24.04 and 26.04 before
  a packaging task finishes, a stable entry is replaced or the package is
  published. A build may first produce a separate candidate; missing or failed
  required checks keep it a candidate.
- `docs/DEVELOPMENT.md` defines the report/review/clean-HEAD order and preserves
  the existing ordinary source-push workflow. No new generic receipt system or
  compulsory GUI build for every source change is introduced.
- `docs/packaging.md` gives explicit artifact-selection commands and one
  per-artifact two-system checklist, separating actual package origins/UI,
  provider protocols including Qwen realtime/local WSS, Unicode/current-cursor
  delivery, partial cancellation and cleanup from microphone, physical shortcuts,
  overlay, integration, FUSE and cloud capability checks.

Both systems use the same image, not unnecessary distro-specific branches or
packages. Record actual Xorg, XWayland and native Wayland separately. In
particular, the observed GNOME 46 missing native keyboard API cannot become a
passing result by relabelling Xorg or container evidence. Unsupported/untested
features and cloud state must remain explicit. A local fixed-service flow does
not prove microphone capture, real recognition or accuracy. No instruction
automatically authorizes credential access, cloud requests or release actions.

The existing clean-HEAD receipt still verifies source checks and the report's
identity. Root-agent inspection of the actual two-system artifact evidence is
the delivery gate; a unit test cannot establish the truth of a desktop run.
The new rules do not retroactively turn existing limited a13 results into full
dual-system acceptance, repair GNOME's API, or replace the deployed a9 entry.

## Local preflight changes

`scripts/packaging/build_appimage.py` now reads the project version in
`pyproject.toml`, a literal `__version__` assignment in
`src/inkecho/__init__.py`, and the single `inkecho` entry in `uv.lock`.
The three nonempty versions must agree. Source metadata is parsed with AST and
never imported or executed. Missing, malformed, duplicate or inconsistent
metadata fails with a fixed diagnostic **before** runtime directory creation,
downloads or removal of an existing AppDir. The verified version is then reused
for the package inventory and filename. This module did not change those three
version files; the existing a13 values are left for the separate version decision.

`scripts/packaging/check_ubuntu24.sh` now requires exactly one explicit executable
`.AppImage` file path. It resolves that chosen path and rejects absent, missing,
wrong-extension or non-executable selections before Docker or QA-directory
creation. The container command mounts only that selected file read-only at
`/input/InkEcho.AppImage`, not the whole artifact directory. The smoke still uses
network none, nonroot/read-only userspace and nine-page offscreen checks; it is
not a real Ubuntu24 desktop acceptance entry. The implicit a8 selection is gone.

A repository search for `check_ubuntu24.sh` found the current guide and historical
transcripts in `provider-repair-release.md`, `repair-validation.md`,
`listening-repair-release.md`, `packaging-stage0.md`, `focus-repair-release.md`
and `performance-package-validation.md`. The current guide now passes the
explicit selected path. Historical reports and their old actual commands were
preserved; the current guide warns not to rerun their former default invocation.

## Reproduce the completed local checks

```sh
.venv/bin/python -m pytest -q tests/test_dual_ubuntu_packaging.py tests/test_packaging.py --tb=short
/bin/sh -n scripts/packaging/check_ubuntu24.sh
.venv/bin/ruff check scripts/packaging/build_appimage.py tests/test_dual_ubuntu_packaging.py
.venv/bin/ruff format --check scripts/packaging/build_appimage.py tests/test_dual_ubuntu_packaging.py
```

Observed result: **20 passed in 0.20 seconds**,
`build/dual-ubuntu-packaging-tests.log`; shell syntax, Ruff lint and formatting
checks passed. Tests cover:

- Three-way metadata agreement without executing application code; every
  mismatching source, malformed/duplicate lock entry, missing version and
  dynamic source version is rejected.
- Rejection through the actual build `main()` before download, runtime directory
  creation or existing-AppDir deletion; an old-build marker remains byte-exact.
- No artifact argument, missing path, wrong extension and non-executable file
  reject before a Docker call or output directory.
- An explicit executable marker with spaces in its path is the sole selected
  read-only image in the shell entry's actual argv. A local Docker **test double**
  records its arguments and creates nine synthetic file markers. Neither those
  markers nor this shell-control test establish screenshots, a real image launch
  or Ubuntu compatibility.
- Existing atomic-image tests continue to verify an old open image's bytes and
  failed-build preservation.

No current package, old raw desktop/cloud evidence, README, compatibility matrix,
UI/provider implementation or stable launcher was edited by this module.

## Remaining work

Root review, a focused local commit and the usual complete clean-HEAD workflow
remain necessary for this module. The separate planned a14 version change,
build, same-hash two-system actual-package checks and any authorized deployment
are not performed or presumed here. Their report must establish the new artifact's
actual behavior, including the user's current Ubuntu26 realtime setup; these
preflight tests cannot establish that repair.
