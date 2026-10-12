import importlib.util
from pathlib import Path

import pytest

import inkecho.config as configuration
from inkecho.config import ConfigStore, Settings

SPEC = importlib.util.spec_from_file_location(
    "native_cloud_probe",
    Path(__file__).resolve().parents[1]
    / "scripts/validation/native_cloud_workflow_probe.py",
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def snapshot(root):
    return {
        str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def test_legacy_read_is_rejected_without_backup_or_migration(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b'{"schema_version":0,"hotkey":"F14"}')
    before = snapshot(tmp_path)
    original_writer = configuration.atomic_write
    with probe.read_only_configuration():
        with pytest.raises(probe.ConfigurationWriteBlocked):
            ConfigStore(tmp_path).load_settings()
    assert snapshot(tmp_path) == before
    assert configuration.atomic_write is original_writer


def test_current_config_loads_but_save_cannot_change_it(tmp_path):
    store = ConfigStore(tmp_path)
    store.save_settings(Settings(shortcut="F14"))
    before = snapshot(tmp_path)
    with probe.read_only_configuration():
        assert store.load_settings().shortcut == "F14"
        with pytest.raises(probe.ConfigurationWriteBlocked):
            store.save_settings(Settings(shortcut="F13"))
    assert snapshot(tmp_path) == before


def test_write_guard_remains_active_when_file_changes_between_reads(tmp_path):
    store = ConfigStore(tmp_path)
    store.save_settings(Settings())
    path = tmp_path / "config.json"
    with probe.read_only_configuration():
        assert store.load_settings() == Settings()
        # Simulate an external replacement after the initial current-schema read.
        path.write_bytes(b'{"schema_version":0,"hotkey":"F14"}')
        before = snapshot(tmp_path)
        with pytest.raises(probe.ConfigurationWriteBlocked):
            store.load_settings()
        assert snapshot(tmp_path) == before


def test_guard_rejects_default_creation_without_creating_directories(tmp_path):
    before = snapshot(tmp_path)
    with probe.read_only_configuration():
        with pytest.raises(probe.ConfigurationWriteBlocked):
            ConfigStore(tmp_path / "not-created").save_settings(Settings())
    assert snapshot(tmp_path) == before
