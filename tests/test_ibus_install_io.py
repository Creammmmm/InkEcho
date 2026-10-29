import pytest

from inkecho.platform import ibus_extension as module


@pytest.mark.parametrize("stage", ["directory", "archive"])
def test_install_reports_local_io_failure_and_never_runs_extension_command(
    monkeypatch, stage
):
    commands = []
    manager = module.ExtensionManager(
        runner=lambda *args, **kwargs: commands.append(args)
    )

    def fail(*args, **kwargs):
        raise OSError("private path and OS error details")

    if stage == "directory":
        monkeypatch.setattr(module.tempfile, "TemporaryDirectory", fail)
    else:
        monkeypatch.setattr(module.zipfile, "ZipFile", fail)
    with pytest.raises(module.ExtensionError) as error:
        manager.install()
    assert "private path" not in str(error.value)
    assert commands == []
