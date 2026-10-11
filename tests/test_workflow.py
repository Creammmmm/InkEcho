"""Exercise repository gates in disposable repositories, never the working tree."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "workflow", ROOT / "scripts/validation/workflow.py"
)
workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow)


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.name", "Workflow Test")
    git(repository, "config", "user.email", "workflow@example.invalid")
    shutil.copytree(ROOT / ".githooks", repository / ".githooks")
    target = repository / "scripts/validation"
    target.mkdir(parents=True)
    shutil.copy(ROOT / "scripts/validation/workflow.py", target)
    (repository / "evidence.md").write_text("Verified hook behavior locally.\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "chore(workflow): initialize test repository")
    git(repository, "config", "core.hooksPath", ".githooks")
    monkeypatch.chdir(repository)
    return repository


@pytest.mark.parametrize(
    "message",
    [
        "feat(audio): record microphone input",
        "fix(injection): reject stale tasks\n\nKeep cancelled results out of targets.",
    ],
)
def test_valid_commit_message(tmp_path, message):
    path = tmp_path / "message"
    path.write_text(message)
    workflow.check_message(path)


@pytest.mark.parametrize(
    "message",
    [
        "",
        "feat(audio): 支持录音",
        "Add audio",
        "feat: record audio",
        "feat(audio): Record audio",
        "feat(audio): record audio.",
        "feat(audio): " + "a" * 70,
        "feat(audio): record audio\nMissing blank line",
    ],
)
def test_invalid_commit_message(tmp_path, message):
    path = tmp_path / "message"
    path.write_text(message)
    with pytest.raises(ValueError):
        workflow.check_message(path)


def test_git_invokes_commit_hook(repo):
    result = git(repo, "commit", "--allow-empty", "-m", "bad message", check=False)
    assert result.returncode != 0
    assert "type(scope)" in result.stderr
    git(repo, "commit", "--allow-empty", "-m", "test(workflow): verify commit hook")


def write_receipt(repo):
    """Create a fixture receipt; production receipts come only from validate()."""
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    path = workflow.receipt_path(head)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "head": head,
                "module": "workflow",
                "validated_at": "2026-10-12T00:00:00+00:00",
                "evidence": "evidence.md",
                "evidence_sha256": workflow.evidence_hash("evidence.md"),
                "commands": workflow.commands(),
            }
        )
    )
    return path


def test_git_push_requires_exact_validated_head(repo, tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    result = git(repo, "push", "origin", "main", check=False)
    assert result.returncode != 0
    assert "exact commit" in result.stderr
    write_receipt(repo)
    git(repo, "push", "origin", "main")
    git(repo, "commit", "--allow-empty", "-m", "test(workflow): change commit")
    result = git(repo, "push", "origin", "main", check=False)
    assert result.returncode != 0
    assert "exact commit" in result.stderr


def test_push_rejects_dirty_tree_and_other_commits(repo):
    write_receipt(repo)
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    update = f"refs/heads/main {head} refs/heads/main {'0' * 40}"
    workflow.check_push(update)
    with pytest.raises(ValueError, match="current HEAD"):
        workflow.check_push(f"refs/heads/old {'1' * 40} refs/heads/old {'0' * 40}")
    (repo / "untracked.py").write_text("# Pending work\n")
    with pytest.raises(ValueError, match="pending changes"):
        workflow.check_push(update)


@pytest.mark.parametrize(
    "local_ref, remote_ref, delete",
    [
        ("refs/heads/other", "refs/heads/other", False),
        ("refs/tags/v1", "refs/tags/v1", False),
        ("refs/heads/main", "refs/tags/v1", False),
        ("(delete)", "refs/heads/main", True),
    ],
)
def test_push_rejects_other_refs_tags_and_deletion(repo, local_ref, remote_ref, delete):
    write_receipt(repo)
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    local_sha = "0" * 40 if delete else head
    with pytest.raises(ValueError, match="current branch"):
        workflow.check_push(f"{local_ref} {local_sha} {remote_ref} {head}")


def test_failed_validation_removes_receipt(repo, monkeypatch):
    path = write_receipt(repo)
    monkeypatch.setattr(workflow, "commands", lambda: [["false"]])
    with pytest.raises(subprocess.CalledProcessError):
        workflow.validate("workflow", "evidence.md")
    assert not path.exists()


def test_successful_validation_records_evidence(repo, monkeypatch):
    monkeypatch.setattr(workflow, "commands", lambda: [["true"]])
    workflow.validate("workflow", "evidence.md")
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    receipt = json.loads(workflow.receipt_path(head).read_text())
    assert receipt["head"] == head
    assert receipt["module"] == "workflow"
    assert receipt["evidence_sha256"] == workflow.evidence_hash("evidence.md")
    assert receipt["commands"] == [["true"]]


def test_validation_rejects_changes_made_by_checks(repo, monkeypatch):
    path = write_receipt(repo)
    monkeypatch.setattr(
        workflow, "commands", lambda: [["touch", str(repo / "new-file")]]
    )
    with pytest.raises(ValueError, match="pending changes"):
        workflow.validate("workflow", "evidence.md")
    assert not path.exists()


def test_changed_evidence_invalidates_receipt(repo):
    path = write_receipt(repo)
    data = json.loads(path.read_text())
    data["evidence_sha256"] = "wrong"
    path.write_text(json.dumps(data))
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    with pytest.raises(ValueError, match="invalid"):
        workflow.check_push(f"refs/heads/main {head} refs/heads/main {'0' * 40}")
