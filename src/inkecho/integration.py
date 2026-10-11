"""Explicit user desktop integration; never remove configuration or credentials."""

import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

from inkecho.config import atomic_write

APP_ID = "io.github.Creammmmm.InkEcho"
MARKER = "X-InkEcho-Managed=true"
SIZES = (16, 24, 32, 48, 64, 128, 256)


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
        result = [(assets / "inkecho.svg", icons / "scalable/apps" / f"{APP_ID}.svg")]
        result.extend(
            (
                assets / f"inkecho-{size}.png",
                icons / f"{size}x{size}/apps" / f"{APP_ID}.png",
            )
            for size in SIZES
        )
        return result

    def install(self) -> None:
        entry = self._entry()
        for source, destination in self._icons():
            if destination.is_symlink() or (
                destination.exists() and destination.read_bytes() != source.read_bytes()
            ):
                raise IntegrationError(
                    "An unrelated icon occupies this path; preserve it."
                )
        self._write(self.launcher, entry)
        for source, destination in self._icons():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
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
