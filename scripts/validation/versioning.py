"""Require an explicit, synchronized patch increment in each staged commit."""

import argparse
import ast
import re
import subprocess
import tomllib
from pathlib import Path

FILES = ("pyproject.toml", "src/inkecho/__init__.py", "uv.lock")
BOOTSTRAP_PARENT = "76d8d5591017820caafed55e3741ab998fc44de7"
SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def version(contents: list[str]) -> str:
    """Read the three application literals without importing application code."""
    project = tomllib.loads(contents[0])["project"]["version"]
    source = ast.parse(contents[1])
    values = [
        ast.literal_eval(node.value)
        for node in source.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        )
    ]
    locked = [
        entry["version"]
        for entry in tomllib.loads(contents[2])["package"]
        if entry.get("name") == "inkecho"
    ]
    if type(project) is not str or values != [project] or locked != [project]:
        raise ValueError("Application versions must match in all three metadata files.")
    return project


def next_version(parent: str, previous: str) -> str:
    """Allow exactly one reviewed transition, then only same-X.Y patch + 1."""
    if parent == BOOTSTRAP_PARENT and previous == "0.1.0a18":
        return "0.2.0"
    match = SEMVER.fullmatch(previous)
    if not match:
        raise ValueError("Parent version must be X.Y.Z; no prerelease bypass exists.")
    major, minor, patch = match.groups()
    return f"{major}.{minor}.{int(patch) + 1}"


def expected() -> tuple[str, str]:
    parent = git("rev-parse", "HEAD")
    previous = version([git("show", f"HEAD:{name}") for name in FILES])
    return previous, next_version(parent, previous)


def check_staged() -> None:
    """Inspect the index, never substitute unstaged working-tree values."""
    _previous, required = expected()
    for name in FILES:
        entries = git("ls-files", "--stage", "--", name).splitlines()
        if len(entries) != 1 or entries[0].split()[:3:2] != ["100644", "0"]:
            raise ValueError("Version metadata must be regular, merged index files.")
    staged = version([git("show", f":{name}") for name in FILES])
    if staged != required:
        raise ValueError(
            f"Every commit requires version {required}; staged version is {staged}. "
            "Run versioning.py bump, review and stage all three metadata files."
        )


def bump() -> None:
    """Change only three working files; never stage, commit or change a Git ref."""
    previous, required = expected()
    paths = [Path(name) for name in FILES]
    contents = [path.read_text(encoding="utf-8") for path in paths]
    current = version(contents)
    if current == required:
        return
    if current != previous:
        raise ValueError("Working metadata is neither the parent nor next version.")
    patterns = (
        rf'(?m)^(version\s*=\s*)"{re.escape(previous)}"$',
        rf'(?m)^(__version__\s*=\s*)"{re.escape(previous)}"$',
        rf'(?m)(^name = "inkecho"\nversion = )"{re.escape(previous)}"$',
    )
    updated = []
    for content, pattern in zip(contents, patterns, strict=True):
        value, count = re.subn(pattern, lambda m: f'{m[1]}"{required}"', content)
        if count != 1:
            raise ValueError(
                "Version literal layout is ambiguous; update it explicitly."
            )
        updated.append(value)
    if version(updated) != required:
        raise ValueError("Proposed versions do not match.")
    for path, value in zip(paths, updated, strict=True):
        path.write_text(value, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "bump"])
    args = parser.parse_args()
    try:
        check_staged() if args.action == "check" else bump()
    except (
        ValueError,
        KeyError,
        TypeError,
        SyntaxError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        parser.exit(1, f"Version check blocked: {error}\n")


if __name__ == "__main__":
    main()
