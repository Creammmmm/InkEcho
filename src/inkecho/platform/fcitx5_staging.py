"""Explicit, user-scoped Fcitx candidate staging; never touches a running daemon.

Deactivation removes only the owned description. Native libraries remain on
disk because a running Fcitx may still have them mapped.
"""

import hashlib
import json
import os
import re
import stat
from contextlib import ExitStack
from pathlib import Path


class StagingError(RuntimeError):
    pass


def _directory(path: Path, *, allow_root=False):
    if not path.is_absolute() or any(part in (".", "..") for part in path.parts):
        raise StagingError("absolute_directory_required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if (
            info.st_uid not in ({os.getuid(), 0} if allow_root else {os.getuid()})
            or info.st_mode & 0o022
        ):
            raise StagingError("unsafe_directory")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _child(parent: int, name: str, *, create=True, allow_root=False):
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
        except FileExistsError:
            pass
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    info = os.fstat(fd)
    if (
        info.st_uid not in ({os.getuid(), 0} if allow_root else {os.getuid()})
        or info.st_mode & 0o022
    ):
        os.close(fd)
        raise StagingError("unsafe_directory")
    return fd


def _read(parent: int, name: str, limit: int, *, allow_root=False):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid not in ({os.getuid(), 0} if allow_root else {os.getuid()})
            or info.st_mode & 0o022
        ):
            raise StagingError("unsafe_file")
        if info.st_size > limit:
            raise StagingError("file_too_large")
        with os.fdopen(fd, "rb", closefd=False) as source:
            return source.read(limit + 1)
    finally:
        os.close(fd)


def _new_file(parent: int, name: str, content: bytes):
    # O_EXCL prevents replacing an existing file or following a final symlink.
    fd = os.open(
        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
    )
    try:
        with os.fdopen(fd, "wb", closefd=False) as output:
            output.write(content)
            output.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def _conf(library_without_suffix: str, core: str):
    return (
        "[Addon]\nName=InkEcho\nCategory=Module\nType=SharedLibrary\n"
        f"Library={library_without_suffix}\nVersion=1.0.0\nOnDemand=False\n"
        f"Configurable=False\n\n[Addon/Dependencies]\n0=core:{core}\n1=dbus\n"
    ).encode()


# These are empirical combinations for the pinned candidate, not guarantees
# inferred from the user-editable manifest. Staging qualification covers the
# exact ABI pairs below; desktop scope is recorded in
# docs/fcitx-preedit-guard-validation.md, not inferred for every session/client.
TESTED_CANDIDATE_SHA256 = (
    "acd896aae8ab38ecca2685c0dd8639f2910e841176eadccf59ee4943b158c4de"
)
# Only for safely removing a description installed by a previous candidate.
RETIRED_CANDIDATE_SHA256 = (
    "3a3c80fb464bbfce465b52cb73e998a00705998a768c45400416daf29e89a497",
    "532ef632385bfe9ae3b76312b74874a7cc562c58435bb07f430e704179ebd139",
    "f5c280c980359abfb29d676b5afb65aaae33968a3877a19545661decf2ad6b1d",
)
TESTED_SYSTEMS = frozenset(
    {
        ("ubuntu", "24.04", "x86_64", "5.1.7"),
        ("ubuntu", "26.04", "x86_64", "5.1.19"),
    }
)
BUILD_SYSTEM = ("ubuntu", "24.04", "x86_64", "5.1.7")


def stage(
    candidate_dir: Path,
    data_home: Path,
    *,
    os_id: str,
    os_version: str,
    architecture: str,
    fcitx_version: str,
):
    """Stage verified files, but do not refresh, install system files, or restart."""
    if any(char in str(data_home) for char in "\\\r\n;\x00") or str(
        data_home
    ).strip() != str(data_home):
        raise StagingError("unsafe_path")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", fcitx_version):
        raise StagingError("invalid_fcitx_version")
    with ExitStack() as stack:
        source = _directory(candidate_dir, allow_root=True)
        stack.callback(os.close, source)
        data = _directory(data_home)
        stack.callback(os.close, data)
        manifest = json.loads(_read(source, "manifest.json", 65536, allow_root=True))
        if not isinstance(manifest, dict):
            raise StagingError("invalid_manifest")
        if (
            manifest.get("status") != "uninstalled-candidate"
            or (
                manifest.get("os_id"),
                manifest.get("os_version"),
                manifest.get("architecture"),
                manifest.get("fcitx5_core_version"),
            )
            != BUILD_SYSTEM
            or (os_id, os_version, architecture, fcitx_version) not in TESTED_SYSTEMS
        ):
            raise StagingError("incompatible_candidate")
        output = _child(source, "candidate", create=False, allow_root=True)
        stack.callback(os.close, output)
        binary = _read(output, "libinkecho.so", 16 * 1024 * 1024, allow_root=True)
        candidate_conf = _read(output, "inkecho.conf", 65536, allow_root=True)
        machine = {"x86_64": 62, "aarch64": 183}.get(architecture)
        if (
            machine is None
            or len(binary) < 64
            or binary[:6] != b"\x7fELF\x02\x01"
            or int.from_bytes(binary[16:18], "little") != 3
            or int.from_bytes(binary[18:20], "little") != machine
        ):
            raise StagingError("invalid_library_architecture")
        digest = hashlib.sha256(binary).hexdigest()
        hashes = manifest.get("files_sha256", {})
        if not isinstance(hashes, dict):
            raise StagingError("invalid_manifest")
        if (
            hashes.get("libinkecho.so") != digest
            or hashes.get("inkecho.conf") != hashlib.sha256(candidate_conf).hexdigest()
        ):
            raise StagingError("candidate_hash_mismatch")
        if digest != TESTED_CANDIDATE_SHA256:
            raise StagingError("unverified_candidate")
        if candidate_conf != _conf("libinkecho", BUILD_SYSTEM[3]):
            raise StagingError("invalid_candidate_description")
        addon_parent = _child(data, "fcitx5")
        stack.callback(os.close, addon_parent)
        addon = _child(addon_parent, "addon")
        stack.callback(os.close, addon)
        # Check before writing the library, and still use O_EXCL at publication.
        try:
            os.stat("inkecho.conf", dir_fd=addon, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise StagingError("description_exists")
        owned = _child(data, "inkecho")
        stack.callback(os.close, owned)
        versions = _child(owned, "fcitx5")
        stack.callback(os.close, versions)
        version = _child(versions, digest)
        stack.callback(os.close, version)
        # Publish only a fully written and fsynced library. A crashed writer
        # may leave a private temporary file, but never a partial final library.
        library_temp = f".inkecho-lib-{os.getpid()}-{os.urandom(8).hex()}"
        try:
            _new_file(version, library_temp, binary)
        except FileExistsError:
            # O_EXCL means this name belongs to somebody else: do not remove it.
            raise
        except BaseException:
            try:
                os.unlink(library_temp, dir_fd=version)
            except FileNotFoundError:
                pass
            raise
        try:
            try:
                os.link(
                    library_temp,
                    "libinkecho.so",
                    src_dir_fd=version,
                    dst_dir_fd=version,
                    follow_symlinks=False,
                )
                os.fsync(version)
            except FileExistsError:
                if (
                    hashlib.sha256(
                        _read(version, "libinkecho.so", 16 * 1024 * 1024)
                    ).hexdigest()
                    != digest
                ):
                    raise StagingError("library_conflict") from None
        finally:
            os.unlink(library_temp, dir_fd=version)
        libpath = str(data_home / "inkecho" / "fcitx5" / digest / "libinkecho")
        description = _conf(libpath, fcitx_version)
        # Publishing via hard link makes the complete description visible at once.
        temp = f".inkecho-{os.getpid()}-{os.urandom(8).hex()}"
        _new_file(addon, temp, description)
        try:
            os.link(
                temp,
                "inkecho.conf",
                src_dir_fd=addon,
                dst_dir_fd=addon,
                follow_symlinks=False,
            )
            os.fsync(addon)
        finally:
            os.unlink(temp, dir_fd=addon)
        return digest


def deactivate(data_home: Path, *, digest: str, fcitx_version: str | None = None):
    """Remove only our exact description; keep the immutable library forever."""
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise StagingError("invalid_digest")
    if fcitx_version is not None and not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+", fcitx_version
    ):
        raise StagingError("invalid_fcitx_version")
    with ExitStack() as stack:
        data = _directory(data_home)
        stack.callback(os.close, data)
        addon_parent = _child(data, "fcitx5", create=False)
        stack.callback(os.close, addon_parent)
        addon = _child(addon_parent, "addon", create=False)
        stack.callback(os.close, addon)
        libpath = str(data_home / "inkecho" / "fcitx5" / digest / "libinkecho")
        versions = (
            {fcitx_version}
            if fcitx_version is not None
            else {system[3] for system in TESTED_SYSTEMS}
        )
        description = _read(addon, "inkecho.conf", 65536)
        if description not in {_conf(libpath, version) for version in versions}:
            raise StagingError("description_changed")
        tombstone = f".inkecho-disabled-{os.getpid()}-{os.urandom(8).hex()}"
        os.rename("inkecho.conf", tombstone, src_dir_fd=addon, dst_dir_fd=addon)
        try:
            if _read(addon, tombstone, 65536) != description:
                try:
                    os.link(
                        tombstone,
                        "inkecho.conf",
                        src_dir_fd=addon,
                        dst_dir_fd=addon,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    # Preserve the renamed file if another writer owns the name.
                    raise StagingError("description_raced_preserved") from None
                os.unlink(tombstone, dir_fd=addon)
                raise StagingError("description_changed")
            os.unlink(tombstone, dir_fd=addon)
        except BaseException:
            os.fsync(addon)
            raise
        os.fsync(addon)
