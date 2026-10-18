"""Exercise staged versions in disposable Git repositories, including real hooks."""

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "versioning", ROOT / "scripts/validation/versioning.py"
)
versioning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(versioning)


def git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(repo), *args], text=True, capture_output=True, check=check
    )


def metadata(repo, value):
    (repo / "src/inkecho").mkdir(parents=True, exist_ok=True)
    (repo / "pyproject.toml").write_text(f'[project]\nversion = "{value}"\n')
    (repo / "src/inkecho/__init__.py").write_text(f'__version__ = "{value}"\n')
    (repo / "uv.lock").write_text(
        f'[[package]]\nname = "inkecho"\nversion = "{value}"\n'
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    target = tmp_path / "repository"
    target.mkdir()
    git(target, "init", "-b", "main")
    git(target, "config", "user.name", "Version Test")
    git(target, "config", "user.email", "version@example.invalid")
    metadata(target, "1.2.3")
    git(target, "add", ".")
    git(target, "commit", "-m", "chore(versioning): initialize repository")
    folder = target / "scripts/validation"
    folder.mkdir(parents=True)
    shutil.copy(ROOT / "scripts/validation/versioning.py", folder)
    shutil.copytree(ROOT / ".githooks", target / ".githooks")
    shutil.copy(ROOT / "scripts/validation/workflow.py", folder)
    git(target, "config", "core.hooksPath", ".githooks")
    monkeypatch.chdir(target)
    return target


def test_bootstrap_has_exact_parent_and_old_version():
    assert versioning.next_version(versioning.BOOTSTRAP_PARENT, "0.1.0a18") == "0.2.0"
    for parent, old in [
        ("1" * 40, "0.1.0a18"),
        (versioning.BOOTSTRAP_PARENT, "0.1.0a17"),
    ]:
        with pytest.raises(ValueError):
            versioning.next_version(parent, old)
    assert versioning.next_version("1" * 40, "0.2.0") == "0.2.1"


@pytest.mark.parametrize(
    "value", ["1.2.3", "1.2.5", "1.3.0", "2.0.0", "1.2.4a1", "01.2.4"]
)
def test_staged_missing_skipped_or_other_version_is_rejected(repo, value):
    metadata(repo, value)
    git(repo, "add", *versioning.FILES)
    with pytest.raises(ValueError, match="requires version 1.2.4"):
        versioning.check_staged()


def test_index_is_authoritative_not_unstaged_working_files(repo):
    metadata(repo, "1.2.4")
    with pytest.raises(ValueError):
        versioning.check_staged()
    git(repo, "add", *versioning.FILES)
    metadata(repo, "9.9.9")
    versioning.check_staged()


def test_unsynchronized_index_versions_are_rejected(repo):
    (repo / "pyproject.toml").write_text('[project]\nversion = "1.2.4"\n')
    git(repo, "add", "pyproject.toml")
    with pytest.raises(ValueError, match="must match"):
        versioning.check_staged()


def test_metadata_must_be_regular_index_blobs(repo):
    metadata(repo, "1.2.4")
    git(repo, "add", *versioning.FILES)
    git(repo, "update-index", "--chmod=+x", "uv.lock")
    with pytest.raises(ValueError, match="regular"):
        versioning.check_staged()


def test_manual_bump_changes_only_working_metadata_without_staging_or_commit(repo):
    before = git(repo, "rev-parse", "HEAD").stdout
    versioning.bump()
    assert (
        versioning.version([Path(n).read_text() for n in versioning.FILES]) == "1.2.4"
    )
    assert git(repo, "diff", "--cached", "--name-only").stdout == ""
    assert git(repo, "rev-parse", "HEAD").stdout == before
    versioning.bump()  # Idempotent before the caller stages the prepared bump.
    assert set(git(repo, "diff", "--name-only").stdout.splitlines()) == set(
        versioning.FILES
    )


def test_docs_commit_requires_bump_and_unchanged_amend_is_not_exempt(repo):
    (repo / "notes.md").write_text("Reviewed documentation.\n")
    git(repo, "add", ".")
    rejected = git(repo, "commit", "-m", "docs(versioning): add notes", check=False)
    assert rejected.returncode and "requires version 1.2.4" in rejected.stderr
    versioning.bump()
    git(repo, "add", *versioning.FILES)
    git(repo, "commit", "-m", "docs(versioning): add notes")
    unchanged = git(repo, "commit", "--amend", "--no-edit", check=False)
    assert unchanged.returncode and "requires version 1.2.5" in unchanged.stderr


def test_empty_commit_is_not_exempt(repo):
    rejected = git(
        repo,
        "commit",
        "--allow-empty",
        "-m",
        "chore(versioning): empty change",
        check=False,
    )
    assert rejected.returncode and "requires version 1.2.4" in rejected.stderr
