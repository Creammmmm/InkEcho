"""Explicit user desktop integration; never remove configuration or credentials."""

import hashlib
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

from inkecho.config import atomic_write

APP_ID = "io.github.Creammmmm.InkEcho"
MARKER = "X-InkEcho-Managed=true"
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
# Exact assets shipped before the blue branding. Never replace unknown artwork.
LEGACY_ICON_SHA256 = {
    "inkecho-16.png": (
        "d26847979e9f027f02d5c46849875c5c47382878b24fe787229184a4a43637ed"
    ),
    "inkecho-24.png": (
        "baed2993f14d0a86468d1d0a613a66be1876765bb06c585c9eed3e4a9a6140d7"
    ),
    "inkecho-32.png": (
        "76603488559747258c0c6db66b2b52c3b7f08a2d560530d0ed6e624563b717b7"
    ),
    "inkecho-48.png": (
        "2fc2dc8d1d7d8eb9abd333c9497ac33cbdb939d7a929fe6e2d4fce1c5b58bd95"
    ),
    "inkecho-64.png": (
        "12927cb4d56f781f8335295f954936c6ce61290fd7f748e87e94ae80eb46113e"
    ),
    "inkecho-128.png": (
        "f2cb2a058835b86d7e165c392714ab2cf05e55a0e0fdd36204469b5ccd3cefc5"
    ),
    "inkecho-256.png": (
        "3e40b7eb151d90b9176f9799573d2ee7fe27f15e292d2eb663b790aab9d1b1c2"
    ),
    "inkecho.svg": "df9f4e49cbfe80a6754ff133b2548968550ba74965b69388c6ccdf0ce64a5cc6",
}


class IntegrationError(ValueError):
    """An executable or desktop integration path needs attention."""


def xdg_directory(variable: str, default: str) -> Path:
    path = Path(os.environ.get(variable, ""))
    return path if path.is_absolute() else Path.home() / default


def desktop_argument(value: str) -> str:
    if any(char in value for char in "\n\r\0"):
        raise IntegrationError("Launcher arguments cannot contain control characters.")
    # Desktop Exec is not shell syntax. Quote reserved characters at both layers.
    value = value.replace("%", "%%").replace("\\", "\\\\\\\\")
    for char in ('"', "`", "$"):
        value = value.replace(char, "\\\\" + char)
    return f'"{value}"'


class DesktopIntegration:
    def __init__(
        self,
        executable: Path,
        *,
        args: tuple[str, ...] = (),
        data_home: Path | None = None,
        config_home: Path | None = None,
    ) -> None:
        self.executable = Path(executable)
        if not self.executable.is_absolute() or "=" in str(self.executable):
            raise IntegrationError(
                "Use an absolute executable path without an equal sign."
            )
        self.args = args
        self.data_home = (
            data_home
            if data_home is not None
            else xdg_directory("XDG_DATA_HOME", ".local/share")
        )
        self.config_home = (
            config_home
            if config_home is not None
            else xdg_directory("XDG_CONFIG_HOME", ".config")
        )
        self.launcher = self.data_home / "applications" / f"{APP_ID}.desktop"
        self.autostart = self.config_home / "autostart" / f"{APP_ID}.desktop"

    def _entry(self, *, autostart: bool = False) -> str:
        if not self.executable.is_file() or not os.access(self.executable, os.X_OK):
            raise IntegrationError("Select an existing executable application path.")
        command = " ".join(
            desktop_argument(str(value)) for value in (self.executable, *self.args)
        )
        return (
            "[Desktop Entry]\nType=Application\nName=InkEcho\n"
            "Comment=Private desktop voice input\n"
            # GIO checks the executable before expanding %% in its filename.
            f"Exec=/usr/bin/env -- {command}{' --background' if autostart else ''}\n"
            f"Icon={APP_ID}\nTerminal=false\nCategories=AudioVideo;Audio;\n"
            f"StartupWMClass=InkEcho\n{MARKER}\n"
        )

    @staticmethod
    def _owned(path: Path) -> bool:
        return (
            path.is_file()
            and not path.is_symlink()
            and MARKER in path.read_text().splitlines()
        )

    def _write(self, path: Path, content: str) -> None:
        if path.is_symlink() or (path.exists() and not self._owned(path)):
            raise IntegrationError(
                "An unrelated launcher occupies this path; preserve it."
            )
        atomic_write(path, content.encode())

    def _icons(self) -> list[tuple[Path, Path]]:
        assets = Path(str(files("inkecho").joinpath("assets")))
        icons = self.data_home / "icons/hicolor"
        return [
            (
                assets / f"inkecho-{size}.png",
                icons / f"{size}x{size}/apps" / f"{APP_ID}.png",
            )
            for size in SIZES
        ]

    def _legacy_svg(self) -> Path:
        return self.data_home / "icons/hicolor/scalable/apps" / f"{APP_ID}.svg"

    @staticmethod
    def _legacy_asset(path: Path, name: str) -> bool:
        return (
            path.is_file()
            and not path.is_symlink()
            and hashlib.sha256(path.read_bytes()).hexdigest()
            == LEGACY_ICON_SHA256.get(name)
        )

    def install(self) -> None:
        entry = self._entry()
        managed = self._owned(self.launcher)
        for source, destination in self._icons():
            if destination.is_symlink() or (
                destination.exists()
                and destination.read_bytes() != source.read_bytes()
                and not (managed and self._legacy_asset(destination, source.name))
            ):
                raise IntegrationError(
                    "An unrelated icon occupies this path; preserve it."
                )
        old_svg = self._legacy_svg()
        if old_svg.is_symlink() or (
            old_svg.exists()
            and not (managed and self._legacy_asset(old_svg, "inkecho.svg"))
        ):
            raise IntegrationError(
                "An unrelated scalable icon occupies this path; preserve it."
            )
        self._write(self.launcher, entry)
        for source, destination in self._icons():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        if old_svg.exists():
            old_svg.unlink()
        self._refresh()

    def _refresh(self) -> None:
        for program, arguments in (
            ("update-desktop-database", [str(self.launcher.parent)]),
            (
                "gtk-update-icon-cache",
                ["-f", "-t", str(self.data_home / "icons/hicolor")],
            ),
        ):
            if shutil.which(program):
                try:
                    subprocess.run(
                        [program, *arguments], timeout=3, capture_output=True
                    )
                except (OSError, subprocess.TimeoutExpired):
                    pass  # Optional caches must not block installation or removal.

    def repair(self) -> None:
        enabled = self._owned(self.autostart)
        self.install()
        if enabled:
            self.set_autostart(True)

    def set_autostart(self, enabled: bool) -> None:
        if enabled:
            self._write(self.autostart, self._entry(autostart=True))
        elif self._owned(self.autostart):
            self.autostart.unlink()

    def status(self) -> dict:
        installed = self._owned(self.launcher)
        try:
            current = installed and self.launcher.read_text() == self._entry()
        except IntegrationError:
            current = False
        return {
            "installed": installed,
            "current": current,
            "autostart": self._owned(self.autostart),
            "executable": str(self.executable),
        }

    def remove(self) -> None:
        old_svg = self._legacy_svg()
        if self._owned(self.launcher) and self._legacy_asset(old_svg, "inkecho.svg"):
            old_svg.unlink()
        for path in (self.launcher, self.autostart):
            if self._owned(path):
                path.unlink()
        for source, destination in self._icons():
            if (
                destination.is_file()
                and not destination.is_symlink()
                and destination.read_bytes() == source.read_bytes()
            ):
                destination.unlink()
        self._refresh()
