import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from inkecho.integration import DesktopIntegration, IntegrationError, desktop_argument


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


def test_direct_appimage_identity_registers_matching_icons_without_autostart(
    integration, monkeypatch
):
    monkeypatch.setattr(
        integration, "_refresh", lambda: pytest.fail("startup must not wait for caches")
    )
    integration.ensure_running_identity()
    entry = integration.launcher.read_text()
    assert integration.launcher.name == "io.github.Creammmmm.InkEcho.desktop"
    assert "StartupWMClass=InkEcho\n" in entry
    assert (
        f"Icon={integration.data_home}/icons/hicolor/256x256/apps/io.github.Creammmmm.InkEcho.png\n"
        in entry
    )
    assert not integration.autostart.exists()
    before = integration.launcher.stat().st_mtime_ns
    integration.ensure_running_identity()
    assert integration.launcher.stat().st_mtime_ns == before
    moved = integration.executable.with_name("new image.AppImage")
    integration.executable.rename(moved)
    integration.executable = moved
    integration.ensure_running_identity()
    assert str(moved) in integration.launcher.read_text()
    assert not integration.autostart.exists()


def test_direct_appimage_identity_preserves_unrelated_launcher(integration):
    integration.launcher.parent.mkdir(parents=True)
    integration.launcher.write_text("[Desktop Entry]\nName=User override\n")
    with pytest.raises(IntegrationError):
        integration.ensure_running_identity()
    assert integration.launcher.read_text() == "[Desktop Entry]\nName=User override\n"
    assert not integration.autostart.exists()


def test_direct_appimage_identity_preserves_symlink_launcher(integration, tmp_path):
    target = tmp_path / "user.desktop"
    target.write_text("user launcher")
    integration.launcher.parent.mkdir(parents=True)
    integration.launcher.symlink_to(target)
    with pytest.raises(IntegrationError):
        integration.ensure_running_identity()
    assert target.read_text() == "user launcher"
    assert integration.launcher.is_symlink()


def test_running_identity_publishes_desktop_after_atomic_icons(
    integration, monkeypatch
):
    from inkecho.config import atomic_write

    written = []

    def record(path, content):
        atomic_write(path, content)
        written.append(path)

    monkeypatch.setattr("inkecho.integration.atomic_write", record)
    integration.ensure_running_identity()
    assert written == [
        *(destination for _, destination in integration._icons()),
        integration.launcher,
    ]


def test_old_managed_theme_entry_migrates_once(integration, monkeypatch):
    integration.install(refresh=False)
    entry = integration.launcher.read_text()
    old = "\n".join(
        "Icon=io.github.Creammmmm.InkEcho" if line.startswith("Icon=") else line
        for line in entry.split("\n")
    )
    integration.launcher.write_text(old)
    monkeypatch.setattr(integration, "_refresh", lambda: pytest.fail("no cache wait"))
    assert not integration.status()["current"]
    integration.ensure_running_identity()
    assert integration.launcher.read_text() == entry
    before = integration.launcher.stat().st_mtime_ns
    integration.ensure_running_identity()
    assert integration.launcher.stat().st_mtime_ns == before


@pytest.mark.parametrize("character", ["\n", "\r", "\t", "\0", "\x1f", "\x7f"])
def test_icon_path_control_characters_rejected_before_writes(
    integration, tmp_path, character
):
    app = DesktopIntegration(
        integration.executable, data_home=tmp_path / ("bad" + character + "path")
    )
    with pytest.raises(IntegrationError):
        app.ensure_running_identity()
    assert not app.data_home.exists()


def test_relative_icon_data_home_becomes_absolute(integration, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = DesktopIntegration(integration.executable, data_home=Path("relative data"))
    app.ensure_running_identity()
    assert f"Icon={tmp_path}/relative data/icons/" in app.launcher.read_text()


def test_gio_parses_persistent_icon_with_special_path(integration, tmp_path):
    probe = subprocess.run(
        ["/usr/bin/python3", "-I", "-c", "from gi.repository import Gio"],
        capture_output=True,
    )
    if probe.returncode:
        pytest.skip("system Python GIO is unavailable")
    data_home = tmp_path / 'persistent space back\\slash $ 100% "quoted"'
    app = DesktopIntegration(integration.executable, data_home=data_home)
    app.ensure_running_identity()
    result = subprocess.run(
        [
            "/usr/bin/python3",
            "-I",
            "-c",
            "import json,sys; from gi.repository import Gio; "
            "app=Gio.DesktopAppInfo.new_from_filename(sys.argv[1]); "
            "print(json.dumps(app.get_icon().get_file().get_path()))",
            str(app.launcher),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    expected = data_home / "icons/hicolor/256x256/apps/io.github.Creammmmm.InkEcho.png"
    assert json.loads(result.stdout) == str(expected)
    assert (
        expected.read_bytes()
        == dict((destination, source) for source, destination in app._icons())[
            expected
        ].read_bytes()
    )


def test_running_image_updates_enabled_autostart_preserving_profile_args(integration):
    integration.args = (
        "--config-dir",
        "/private/profile space",
        "--data-dir",
        "/private/data",
    )
    integration.install(refresh=False)
    integration.set_autostart(True)
    before = integration.autostart.read_text()
    moved = integration.executable.with_name('new "image.AppImage')
    integration.executable.rename(moved)
    current = DesktopIntegration(
        moved, data_home=integration.data_home, config_home=integration.config_home
    )
    current.ensure_running_identity()
    expected = before.replace(
        desktop_argument(str(integration.executable)), desktop_argument(str(moved)), 1
    )
    assert current.autostart.read_text() == expected
    assert "--config-dir" in expected and "/private/profile space" in expected
    before_mtime = current.autostart.stat().st_mtime_ns
    current.ensure_running_identity()
    assert current.autostart.stat().st_mtime_ns == before_mtime


def test_running_identity_preserves_unrelated_autostart(integration):
    integration.autostart.parent.mkdir(parents=True)
    original = "[Desktop Entry]\nExec=/custom/start --background\n"
    integration.autostart.write_text(original)
    integration.ensure_running_identity()
    assert integration.autostart.read_text() == original


@pytest.mark.parametrize(
    "command",
    [
        "Exec=/custom/managed --background\n",
        'Exec=/usr/bin/env -- "/old.AppImage" --background\nExec=/custom/other\n',
        (
            'Exec=/usr/bin/env -- "/old.AppImage" --background\n'
            'Exec=/usr/bin/env -- "/second.AppImage" --background\n'
        ),
    ],
)
def test_running_identity_preserves_unfamiliar_managed_autostart(integration, command):
    integration.autostart.parent.mkdir(parents=True)
    original = "[Desktop Entry]\nX-InkEcho-Managed=true\n" + command
    integration.autostart.write_text(original)
    integration.ensure_running_identity()
    assert integration.autostart.read_text() == original
