"""Keep commits readable and require local validation before a push."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

SUBJECT = re.compile(
    r"(feat|fix|docs|test|refactor|build|ci|chore)"
    r"\([a-z][a-z0-9-]*\): [a-z][A-Za-z0-9 ,.'()/:+_-]*"
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def require_clean() -> None:
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Commit or remove pending changes before validation or push.")


def check_message(path: Path) -> None:
    message = path.read_text(encoding="utf-8").rstrip("\n")
    lines = message.splitlines()
    if not message.isascii() or not lines:
        raise ValueError("Commit messages must contain English ASCII text.")
    if not SUBJECT.fullmatch(lines[0]) or len(lines[0]) > 72:
        raise ValueError("Use type(scope): imperative summary, at most 72 characters.")
    if lines[0].endswith("."):
        raise ValueError("Do not end the commit subject with a period.")
    if len(lines) > 1 and lines[1]:
        raise ValueError("Separate the subject and body with a blank line.")
    if any(len(line) > 100 for line in lines[2:]):
        raise ValueError("Wrap commit body lines at 100 characters.")


def receipt_path(head: str) -> Path:
    return Path(git("rev-parse", "--git-path", "validation")) / f"{head}.json"


def evidence_hash(path: str) -> str:
    if Path(path).suffix != ".md" or Path(path).is_absolute():
        raise ValueError("Evidence must be a tracked Markdown path in this repository.")
    git("ls-files", "--error-unmatch", "--", path)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def commands() -> list[list[str]]:
    return [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "pytest", "-q"],
    ]


def validate(module: str, evidence: str) -> None:
    require_clean()
    head = git("rev-parse", "HEAD")
    receipt = receipt_path(head)
    # A failed rerun must invalidate any earlier successful receipt.
    receipt.unlink(missing_ok=True)
    digest = evidence_hash(evidence)
    checks = commands()
    for command in checks:
        subprocess.run(command, check=True)
    require_clean()
    if head != git("rev-parse", "HEAD"):
        raise ValueError("HEAD changed during validation; rerun on the new commit.")
    if digest != evidence_hash(evidence):
        raise ValueError("Validation evidence changed during validation.")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        json.dumps(
            {
                "head": head,
                "module": module,
                "evidence": evidence,
                "evidence_sha256": digest,
                "commands": checks,
                "validated_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Local checks passed for {module} at {head[:12]}.")


def check_push(updates: str) -> None:
    require_clean()
    head = git("rev-parse", "HEAD")
    rows = [line.split() for line in updates.splitlines() if line.strip()]
    if not rows:
        return
    branch = git("symbolic-ref", "HEAD")
    for row in rows:
        if (
            len(row) != 4
            or row[0] != branch
            or row[1] != head
            or not row[2].startswith("refs/heads/")
        ):
            raise ValueError(
                "Push only the current branch at validated current HEAD; "
                "tags and deletion are blocked."
            )
    path = receipt_path(head)
    if not path.exists():
        raise ValueError("Run local validation on this exact commit before pushing.")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if (
        receipt.get("head") != head
        or not receipt.get("module")
        or not receipt.get("validated_at")
        or receipt.get("evidence_sha256") != evidence_hash(receipt["evidence"])
        or [command[1:] for command in receipt.get("commands", [])]
        != [command[1:] for command in commands()]
    ):
        raise ValueError("The validation receipt is invalid; rerun local validation.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    message = subparsers.add_parser("commit-msg")
    message.add_argument("path", type=Path)
    subparsers.add_parser("pre-push")
    run = subparsers.add_parser("run")
    run.add_argument("--module", required=True)
    run.add_argument("--evidence", required=True)
    args = parser.parse_args()
    try:
        if args.action == "commit-msg":
            check_message(args.path)
        elif args.action == "pre-push":
            check_push(sys.stdin.read())
        else:
            validate(args.module, args.evidence)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Validation blocked: {error}\n")


if __name__ == "__main__":
    main()
