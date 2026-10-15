"""Prepare a separate a12 paced-arrival check using the frozen R1 procedure."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ubuntu24_vm import LAB, ROOT
from ubuntu24_vm_a12 import ARTIFACT_SHA, PRODUCT_COMMIT, digest
from ubuntu24_vm_a12 import GUEST as R1_GUEST

PROBE_SHA = "26ba7b1198846f9f1585d473aeee7c5767aebf20634c0d17627a105e4ae2bb0d"
R1_SHA = "e156849dbdeddec90cef2633e51c88dc1aec63fe9a086413a722d5934732349a"
SNAPSHOT = LAB / "input/a12-r2-paced"


def guest_payload():
    """Change only evidence names and the explicit fixed SSE profile/interval."""
    result = R1_GUEST
    replacements = [
        ("a12-r1", "a12-r2-paced"),
        ("one-character-fast-long", "one-character-paced-long"),
        (
            'and report.get("fixture_final_printable_codepoints") == 144',
            'and report.get("fixture_final_printable_codepoints") == 144\n'
            '                    and report.get("fixture_sse_delta_delay_seconds")\n'
            "                    == 0.07",
        ),
    ]
    for original, replacement in replacements:
        if original not in result:
            raise RuntimeError("frozen_r1_payload_shape_changed")
        result = result.replace(original, replacement)
    return result


def prepare():
    if SNAPSHOT.exists():
        raise RuntimeError("paced_snapshot_already_exists")
    previous = LAB / "input/a12-r1/manifest.json"
    if digest(previous) != R1_SHA:
        raise RuntimeError("historical_r1_manifest_changed")
    r1 = json.loads(previous.read_text())
    for relative, checksum in r1["source_files"].items():
        if digest(ROOT / relative) != checksum:
            raise RuntimeError("product_source_changed_since_r1")
    for relative, checksum in r1["tool_files"].items():
        if Path(relative).name != "performance_package_probe.py":
            if digest(ROOT / relative) != checksum:
                raise RuntimeError("historical_r1_tool_changed")
    fixture = "scripts/validation/performance_package_probe.py"
    if digest(ROOT / fixture) != PROBE_SHA:
        raise RuntimeError("paced_fixture_not_reviewed_revision")
    tools = [*r1["tool_files"], "scripts/validation/ubuntu24_vm_a12_paced.py"]
    artifact = ROOT / "dist/InkEcho-0.1.0a12-x86_64.AppImage"
    if digest(artifact) != ARTIFACT_SHA:
        raise RuntimeError("unexpected_a12_artifact")
    manifest = {
        "source_commit": PRODUCT_COMMIT,
        "artifact_sha256": ARTIFACT_SHA,
        "baseline_r1_manifest_sha256": R1_SHA,
        "fixture_sse_profile": "one-character-paced-long",
        "fixture_sse_configured_delay_seconds": 0.07,
        "source_files": r1["source_files"],
        "tool_files": {name: digest(ROOT / name) for name in tools},
    }
    with tempfile.TemporaryDirectory(prefix=".a12-r2-paced-", dir=SNAPSHOT.parent) as n:
        directory = Path(n)
        for relative in [*manifest["source_files"], *tools]:
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        shutil.copy2(artifact, directory / artifact.name)
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        os.rename(directory, SNAPSHOT)
    record = {
        "snapshot": str(SNAPSHOT),
        "manifest_sha256": digest(SNAPSHOT / "manifest.json"),
        "artifact_sha256": ARTIFACT_SHA,
        "source_commit": PRODUCT_COMMIT,
    }
    with (LAB / "output/a12-r2-paced-snapshot.json").open("x") as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps(record))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "preview", "run"])
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
        return
    definitions = (ROOT / "scripts/validation/ubuntu24_vm_guest.py").read_text()
    definitions = definitions.rsplit('if __name__ == "__main__":', 1)[0]
    record = json.loads((LAB / "output/a12-r2-paced-snapshot.json").read_text())
    snapshot_sha = record["manifest_sha256"]
    if digest(SNAPSHOT / "manifest.json") != snapshot_sha:
        raise RuntimeError("paced_manifest_changed")
    payload = (
        definitions
        + f"\nARTIFACT_SHA={ARTIFACT_SHA!r}\nPRODUCT_COMMIT={PRODUCT_COMMIT!r}\n"
        + f"SNAPSHOT_SHA={snapshot_sha!r}\n"
        + "SETTINGS={'mode': 'pipeline-long', "
        + "'fixture_sse_profile': 'one-character-paced-long'}\n"
        + guest_payload()
    )
    compile(payload, "isolated-a12-paced-package", "exec")
    suffix = "preview" if args.action == "preview" else "payload"
    path = LAB / f"output/a12-r2-paced-{suffix}.py"
    with path.open("x") as stream:
        stream.write(payload)
    with path.with_suffix(".manifest.json").open("x") as stream:
        json.dump({"payload_file": path.name, "sha256": digest(path)}, stream, indent=2)
    if args.action == "preview":
        print(json.dumps({"payload": str(path), "sha256": digest(path)}))
        return
    subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "scripts/validation/ubuntu24_vm.py"),
            "ssh",
            "--",
            "python3",
            "-",
        ],
        input=payload,
        text=True,
        check=True,
    )


if __name__ == "__main__":
    main()
