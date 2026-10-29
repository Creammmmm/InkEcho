"""Offline state-machine experiments; not production authorization tests."""

import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).parents[1] / "experiments/fcitx-auth/task_policy.py"
spec = importlib.util.spec_from_file_location("experimental_task_policy", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TaskPolicy = module.TaskPolicy
TOKEN = b"x" * 32


def policy():
    return TaskPolicy(":1.8", TOKEN, 10, clock=lambda: 1)


def test_sender_token_and_sequence_required_without_closing_valid_task():
    task = policy()
    seen = []

    def send(sender, token, seq):
        return task.commit(sender, token, seq, "中", lambda c: seen.append(c) or True)

    assert not send(":1.9", TOKEN, 0)
    assert not send(":1.8", b"y" * 32, 0)
    assert not send(":1.8", TOKEN, 1)
    assert send(":1.8", TOKEN, 0)
    assert not send(":1.8", TOKEN, 0)
    assert seen == ["中"]


def test_cancellation_expiry_and_unknown_delivery_never_replay():
    task = policy()
    assert task.commit(":1.8", TOKEN, 0, "甲", lambda _: True)
    task.cancel()
    assert not task.commit(":1.8", TOKEN, 1, "乙", lambda _: True)
    expired = TaskPolicy(":1.8", TOKEN, 1, clock=lambda: 1)
    assert not expired.commit(":1.8", TOKEN, 0, "甲", lambda _: True)
    unknown = policy()

    def lost(_):
        raise RuntimeError("private text")

    assert not unknown.commit(":1.8", TOKEN, 0, "甲", lost)
    assert not unknown.commit(":1.8", TOKEN, 0, "甲", lambda _: True)
    assert not unknown.commit(":1.8", TOKEN, 1, "乙", lambda _: True)


def test_cancel_during_inflight_forbids_later_calls():
    task = policy()

    def delivery(_):
        task.cancel()
        assert not task.commit(":1.8", TOKEN, 1, "乙", lambda _: True)
        return True

    assert task.commit(":1.8", TOKEN, 0, "甲", delivery)
    assert not task.commit(":1.8", TOKEN, 1, "乙", lambda _: True)


@pytest.mark.parametrize("scalar", ["", "ab", "\r", "\x00", "\x85", "\ud800"])
def test_invalid_scalar_poisons_authorized_task(scalar):
    task = policy()
    assert not task.commit(":1.8", TOKEN, 0, scalar, lambda _: True)
    assert not task.commit(":1.8", TOKEN, 0, "a", lambda _: True)


def test_model_does_not_retain_delivered_text():
    task = policy()
    secret = "密"
    assert task.commit(":1.8", TOKEN, 0, secret, lambda _: True)
    assert secret not in repr(vars(task))


def test_private_capability_exclusive_and_owned_cleanup(tmp_path):
    cap_path = Path(__file__).parents[1] / "experiments/fcitx-auth/capability.py"
    cap_spec = importlib.util.spec_from_file_location(
        "experimental_capability", cap_path
    )
    cap_module = importlib.util.module_from_spec(cap_spec)
    cap_spec.loader.exec_module(cap_module)
    cap = cap_module.Capability(tmp_path)
    path = tmp_path / "inkecho-fcitx-candidate.cap"
    assert len(cap.token) == 64
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.read_text() == cap.token
    with pytest.raises(FileExistsError):
        cap_module.Capability(tmp_path)
    path.unlink()
    path.symlink_to("foreign")
    cap.close()
    assert path.is_symlink()
    assert cap.token == ""


def test_unsafe_runtime_rejected(tmp_path):
    cap_path = Path(__file__).parents[1] / "experiments/fcitx-auth/capability.py"
    cap_spec = importlib.util.spec_from_file_location(
        "experimental_capability2", cap_path
    )
    cap_module = importlib.util.module_from_spec(cap_spec)
    cap_spec.loader.exec_module(cap_module)
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match="unsafe runtime"):
        cap_module.Capability(tmp_path)
