"""Read-only opt-in state for the separately installed owned-context extension."""

import ast
import asyncio
import hashlib
import os
import stat
from pathlib import Path

from inkecho.platform.framework_detection import _command
from inkecho.platform.output_router import OutputRouterError

UUID = "inkecho-ibus-owned-v5-prototype@local.invalid"
LEGACY_FILES = {
    "capability.js": {
        "sha256": "fcbaf3e7fd0184ca3141f3c4d811f7496ef753fd6282714ec128a26151a1c881",
        "size": 2784,
    },
    "delivery_gate.js": {
        "sha256": "6900065ef4996dced1e451b7a0f14d744862e1da089e8474caf8d1789b9b9e6d",
        "size": 1938,
    },
    "extension.js": {
        "sha256": "132e1b6d414863bc93191c649b7cac587709fc7dd83fd8551c59b5833ff3accd",
        "size": 5144,
    },
    "identity.js": {
        "sha256": "5a50a88cc6f08619b4742e2f1c269a2dce7a517ece32176270ad69f3ffc8e9ac",
        "size": 404,
    },
    "metadata.json": {
        "sha256": "3affc5dde73c67f8e6638d8dd115b3f7b9504b86ac29af147365675d28824549",
        "size": 235,
    },
    "owned_gate.js": {
        "sha256": "55980b3f06324b79dcfd58d1a69f9ee8e08466e6bf68b1a1916c0afa012561bd",
        "size": 2892,
    },
    "probe.js": {
        "sha256": "39adc6ccc1109bf7d9cae419314781164dccbf0a2f6d6a778888a15755a12dc4",
        "size": 951,
    },
}
FILES = {
    "capability.js": {
        "sha256": "fcbaf3e7fd0184ca3141f3c4d811f7496ef753fd6282714ec128a26151a1c881",
        "size": 2784,
    },
    "owned_gate.js": {
        "sha256": "35a9c94ec1ddf283dfdb976bd5b59d92003527b76682d5fbe96514836f9548ba",
        "size": 4757,
    },
    "metadata.json": {
        "sha256": "3affc5dde73c67f8e6638d8dd115b3f7b9504b86ac29af147365675d28824549",
        "size": 235,
    },
    "delivery_gate.js": {
        "sha256": "fd8181e9d87aa50502db75536dce2999b8df3f3b063026e67db1a609be1d5e76",
        "size": 3770,
    },
    "identity.js": {
        "sha256": "5a50a88cc6f08619b4742e2f1c269a2dce7a517ece32176270ad69f3ffc8e9ac",
        "size": 404,
    },
    "extension.js": {
        "sha256": "aa1704833d67be51e95fa96173971cfb4653baa592232ef3858fe174a201c3f4",
        "size": 8140,
    },
    "probe.js": {
        "sha256": "39adc6ccc1109bf7d9cae419314781164dccbf0a2f6d6a778888a15755a12dc4",
        "size": 951,
    },
}


def installed_directory():
    data = os.environ.get("XDG_DATA_HOME", "")
    base = (
        Path(data)
        if data and Path(data).is_absolute()
        else Path.home() / ".local/share"
    )
    return base / "gnome-shell/extensions" / UUID


def verified_installation(root=None):
    """False only for absent directory; malformed installed assets fail closed."""
    root = installed_directory() if root is None else Path(root)
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return False
    except OSError:
        raise OutputRouterError("input_capability_unknown") from None
    try:
        info = os.fstat(directory)
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise ValueError
        observed = {}
        for name in FILES:
            maximum = max(FILES[name]["size"], LEGACY_FILES[name]["size"])
            fd = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            try:
                info = os.fstat(fd)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_mode & 0o022
                    or info.st_size > maximum
                ):
                    raise ValueError
                with os.fdopen(fd, "rb", closefd=False) as stream:
                    data = stream.read(maximum + 1)
                observed[name] = {
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }
            finally:
                os.close(fd)
        # Accept complete old V5 or complete current bounded bridge, never a mixed set.
        if observed not in (FILES, LEGACY_FILES):
            raise ValueError
        return True
    except (OSError, ValueError):
        raise OutputRouterError("input_capability_unknown") from None
    finally:
        os.close(directory)


def _extension_list(value):
    value = value.strip()
    if value.startswith("@as "):
        value = value[4:]
    entries = ast.literal_eval(value)
    if not isinstance(entries, list) or any(
        not isinstance(item, str) or not item for item in entries
    ):
        raise ValueError
    return entries


async def installation_state(*, root=None, command=_command):
    if not await asyncio.to_thread(verified_installation, root):
        return "absent"
    try:

        async def selection():
            values = []
            for key in ("enabled-extensions", "disabled-extensions"):
                raw = await command("/usr/bin/gsettings", "get", "org.gnome.shell", key)
                values.append(_extension_list(raw))
            raw = (
                await command(
                    "/usr/bin/gsettings",
                    "get",
                    "org.gnome.shell",
                    "disable-user-extensions",
                )
            ).strip()
            if raw not in {"true", "false"}:
                raise ValueError
            return (*values, raw == "true")

        first = await selection()
        second = await selection()
        # These are consistency checks, not an atomic lock on GNOME state.
        if first != second or not await asyncio.to_thread(verified_installation, root):
            raise ValueError
        enabled, disabled, globally_disabled = second
        return (
            "enabled"
            if UUID in enabled and UUID not in disabled and not globally_disabled
            else "disabled"
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        raise OutputRouterError("input_capability_unknown") from None
