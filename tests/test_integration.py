import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from inkecho.integration import DesktopIntegration, IntegrationError


@pytest.fixture
def integration(tmp_path):
    executable = tmp_path / "App folder" / "InkEcho app.AppImage"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    return DesktopIntegration(
        executable, data_home=tmp_path / "data", config_home=tmp_path / "config"
    )


def test_install_validate_icons_and_opt_in_autostart(integration):
    integration.install()
    status = integration.status()
    assert status["installed"] and status["current"] and not status["autostart"]
    assert not integration.autostart.exists()
    assert (
        f'Exec=/usr/bin/env -- "{integration.executable}"\n'
        in integration.launcher.read_text()
    )
    assert len(list(integration.data_home.glob("icons/hicolor/*/apps/*"))) == 8
    if shutil.which("desktop-file-validate"):
        subprocess.run(["desktop-file-validate", str(integration.launcher)], check=True)
    integration.set_autostart(True)
    assert " --background" in integration.autostart.read_text()
    if shutil.which("desktop-file-validate"):
        subprocess.run(
            ["desktop-file-validate", str(integration.autostart)], check=True
        )
    integration.set_autostart(False)
    assert not integration.autostart.exists()


def test_repair_path_and_remove_preserve_user_data(integration):
    integration.install()
    integration.set_autostart(True)
    config = integration.config_home / "inkecho" / "config.json"
    config.parent.mkdir()
    config.write_text("keep user config")
    moved = integration.executable.with_name("Moved App.AppImage")
    integration.executable.rename(moved)
    repaired = DesktopIntegration(
        moved, data_home=integration.data_home, config_home=integration.config_home
    )
    assert not repaired.status()["current"]
    repaired.repair()
    assert repaired.status()["current"] and repaired.status()["autostart"]
    assert str(moved) in repaired.autostart.read_text()
    repaired.remove()
    assert not repaired.launcher.exists() and not repaired.autostart.exists()
    assert config.read_text() == "keep user config"
    assert not list(repaired.data_home.glob("icons/hicolor/*/apps/*"))


def test_unrelated_files_and_dangling_symlinks_are_preserved(integration, tmp_path):
    integration.launcher.parent.mkdir(parents=True)
    integration.launcher.write_text("unrelated launcher")
    with pytest.raises(IntegrationError):
        integration.install()
    integration.remove()
    assert integration.launcher.read_text() == "unrelated launcher"
    integration.launcher.unlink()
    integration.launcher.symlink_to(tmp_path / "missing-target")
    with pytest.raises(IntegrationError):
        integration.install()
    integration.launcher.unlink()
    destination = integration._icons()[0][1]
    destination.parent.mkdir(parents=True)
    destination.symlink_to(tmp_path / "missing-icon")
    with pytest.raises(IntegrationError):
        integration.install()
    assert not (tmp_path / "missing-icon").exists()


def test_existing_modified_icon_not_removed(integration):
    integration.install()
    icon = integration._icons()[0][1]
    icon.write_text("user replacement")
    integration.remove()
    assert icon.read_text() == "user replacement"


def test_repair_upgrades_known_managed_icons_and_removes_old_svg(integration):
    integration.install()
    fixtures = Path(__file__).parent / "fixtures"
    old_png = integration._icons()[0][1]
    old_png.write_bytes((fixtures / "legacy-inkecho-16.png").read_bytes())
    old_svg = integration._legacy_svg()
    old_svg.parent.mkdir(parents=True)
    old_svg.write_bytes((fixtures / "legacy-inkecho.svg").read_bytes())
    integration.repair()
    assert old_png.read_bytes() == integration._icons()[0][0].read_bytes()
    assert not old_svg.exists()
    assert len(list(integration.data_home.glob("icons/hicolor/*/apps/*"))) == 8


def test_repair_upgrades_previous_blue_icon(integration):
    integration.install()
    source, destination = integration._icons()[0]
    fixture = Path(__file__).parent / "fixtures/blue-inkecho-16.png"
    destination.write_bytes(fixture.read_bytes())
    integration.repair()
    assert destination.read_bytes() == source.read_bytes()


def test_previous_blue_icon_requires_managed_launcher(integration):
    destination = integration._icons()[0][1]
    fixture = Path(__file__).parent / "fixtures/blue-inkecho-16.png"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(fixture.read_bytes())
    with pytest.raises(IntegrationError):
        integration.install()
    assert destination.read_bytes() == fixture.read_bytes()


def test_repair_preserves_unknown_scalable_icon(integration):
    integration.install()
    old_svg = integration._legacy_svg()
    old_svg.parent.mkdir(parents=True)
    old_svg.write_text("user supplied icon")
    with pytest.raises(IntegrationError):
        integration.repair()
    assert old_svg.read_text() == "user supplied icon"


def test_legacy_icon_requires_managed_launcher_before_replacement(integration):
    old_png = integration._icons()[0][1]
    old_png.parent.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures/legacy-inkecho-16.png"
    old_png.write_bytes(fixture.read_bytes())
    with pytest.raises(IntegrationError):
        integration.install()
    assert old_png.read_bytes() == fixture.read_bytes()


@pytest.mark.parametrize("path", [Path("relative"), Path("/tmp/path=bad")])
def test_invalid_executable_path(path):
    with pytest.raises(IntegrationError):
        DesktopIntegration(path)


@pytest.mark.skipif(
    shutil.which("gio") is None or shutil.which("desktop-file-validate") is None,
    reason="GIO or desktop-file-validate is unavailable",
)
def test_real_launcher_preserves_quoted_arguments(integration, tmp_path):
    executable = integration.executable.with_name(
        'Ink Echo $ "quoted" 100% back\\slash.AppImage'
    )
    output = tmp_path / "launch-result.json"
    executable.write_text(
        "#!/usr/bin/python3\nimport json, pathlib, sys\n"
        f"pathlib.Path({str(output)!r}).write_text(json.dumps(sys.argv[1:]))\n"
    )
    executable.chmod(0o755)
    arguments = ("two words", "$literal", "100%", 'a"b', "back\\slash")
    app = DesktopIntegration(
        executable,
        args=arguments,
        data_home=integration.data_home,
        config_home=integration.config_home,
    )
    app.install()
    subprocess.run(["desktop-file-validate", str(app.launcher)], check=True)
    subprocess.run(
        ["gio", "launch", str(app.launcher)], check=True, capture_output=True
    )
    for _ in range(100):
        if output.exists():
            break
        time.sleep(0.01)
    assert json.loads(output.read_text()) == list(arguments)
