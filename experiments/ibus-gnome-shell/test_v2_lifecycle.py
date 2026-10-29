import concurrent.futures
import os
import subprocess
import sys
from pathlib import Path

import pytest
from v2_lifecycle import Capability, LifecycleError, Receiver


def test_2048_tasks_consume_once_and_cleanup(tmp_path):
    tmp_path.chmod(0o700)
    receiver = Receiver(tmp_path)
    for i in range(2048):
        cap = Capability(tmp_path)
        owner = f":1.{i + 1}"
        assert receiver.begin(owner, cap.name, cap.token)
        assert not receiver.begin(":2.1", cap.name, cap.token)
        assert receiver.commit(owner, 0)
        assert not receiver.commit(owner, 0)
        assert receiver.cancel(owner)
        assert not receiver.begin(owner, cap.name, cap.token)
        assert not receiver.begin(":2.1", cap.name, cap.token)
        receiver.owner_lost(owner)
        cap.close()
    assert list(tmp_path.iterdir()) == []
    receiver.close()


def test_crashed_client_leaves_unique_file_that_does_not_block_next(tmp_path):
    tmp_path.chmod(0o700)
    script = (
        "import os,sys; from v2_lifecycle import Capability; "
        "c=Capability(sys.argv[1]); os._exit(0)"
    )
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).parent))
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], env=env, check=True)
    stale = list(tmp_path.iterdir())
    assert len(stale) == 1
    cap = Capability(tmp_path)
    receiver = Receiver(tmp_path)
    assert receiver.begin(":1.1", cap.name, cap.token)
    cap.close()
    receiver.owner_lost(":1.1")
    receiver.close()
    assert stale[0].exists()  # never deletes another task's unverified file


def test_concurrent_begin_has_only_one_winner_and_no_replay(tmp_path):
    tmp_path.chmod(0o700)
    cap = Capability(tmp_path)
    receiver = Receiver(tmp_path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda sender: receiver.begin(sender, cap.name, cap.token),
                (":1.1", ":1.2"),
            )
        )
    assert sorted(results) == [False, True]
    winner = ":1.1" if results[0] else ":1.2"
    receiver.owner_lost(winner)
    assert not receiver.begin(":1.3", cap.name, cap.token)
    cap.close()
    receiver.close()


def test_receiver_restart_cannot_reuse_consumed_capability(tmp_path):
    tmp_path.chmod(0o700)
    cap = Capability(tmp_path)
    first = Receiver(tmp_path)
    assert first.begin(":1.1", cap.name, cap.token)
    first.close()
    restarted = Receiver(tmp_path)
    assert not restarted.begin(":1.2", cap.name, cap.token)
    new_cap = Capability(tmp_path)
    assert restarted.begin(":1.2", new_cap.name, new_cap.token)
    restarted.owner_lost(":1.2")
    new_cap.close()
    cap.close()
    restarted.close()


def test_rename_refuses_existing_destination_and_symlink(tmp_path):
    tmp_path.chmod(0o700)
    cap = Capability(tmp_path)
    receiver = Receiver(tmp_path)
    used = tmp_path / ("used-" + cap.name)
    used.write_text("unrelated")
    assert not receiver.begin(":1.1", cap.name, cap.token)
    assert used.read_text() == "unrelated"
    used.unlink()
    original = tmp_path / cap.name
    original.unlink()
    original.symlink_to("foreign")
    assert not receiver.begin(":1.1", cap.name, cap.token)
    cap.close()
    assert original.is_symlink()
    receiver.close()


def test_unsafe_runtime_rejected(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(LifecycleError):
        Capability(tmp_path)
