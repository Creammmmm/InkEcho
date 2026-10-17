"""Audit a selected actual artifact before an existing generic offline probe."""

import argparse
import importlib
import json
import sys
from pathlib import Path

from artifact_scope import audit_package, selected_artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for name in ["artifact", "package-root", "frozen-source-root", "origins-output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument(
        "--tool",
        choices=["performance_package_probe"],
        required=True,
    )
    parser.add_argument("--run-local", action="store_true")
    args, remaining = parser.parse_known_args()
    if not args.run_local or args.origins_output.exists():
        raise SystemExit(2) from None
    selected = selected_artifact(args.artifact, args.expected_sha)
    audit = audit_package(
        args.package_root, args.frozen_source_root, args.expected_version
    )
    with args.origins_output.open("x") as output:
        json.dump({"artifact": selected, "runtime": audit}, output, indent=2)
    if remaining and remaining[0] == "--":
        remaining = remaining[1:]
    if any(argument.startswith("--owned-") for argument in remaining):
        raise ValueError("legacy_owned_cleanup_path_forbidden")
    tool = importlib.import_module(args.tool)
    if args.tool == "performance_package_probe":
        remaining = ["--package-root", str(args.package_root), *remaining]
    sys.argv = [str(tool.__file__), *remaining]
    tool.main()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "code": "acceptance_preflight_failed"}))
        raise SystemExit(2) from None
