"""Fcitx task capability; same-UID processes are not isolated."""

import ctypes
import errno
import fcntl
import os
import secrets
import stat


class Capability:
    def __init__(self, runtime_dir):
        self.fd = None
        self.lock_fd = None
        self.identity = None
        self.token = ""
        self.fd = os.open(runtime_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(self.fd)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise ValueError("unsafe runtime")
            self.lock_fd = os.open(
                "inkecho-fcitx-candidate.lock",
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                0o600,
                dir_fd=self.fd,
            )
            lock_info = os.fstat(self.lock_fd)
            entry = os.stat(
                "inkecho-fcitx-candidate.lock", dir_fd=self.fd, follow_symlinks=False
            )
            if (
                not stat.S_ISREG(lock_info.st_mode)
                or lock_info.st_uid != os.getuid()
                or stat.S_IMODE(lock_info.st_mode) & 0o077
                or lock_info.st_nlink != 1
                or (lock_info.st_dev, lock_info.st_ino) != (entry.st_dev, entry.st_ino)
            ):
                raise ValueError("unsafe lock")
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            previous = os.read(self.lock_fd, 65)
            name = "inkecho-fcitx-candidate.cap"
            try:
                oldfd = os.open(
                    name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd
                )
            except FileNotFoundError:
                oldfd = None
            if oldfd is not None:
                try:
                    old = os.fstat(oldfd)
                    old_entry = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
                    if (
                        not stat.S_ISREG(old.st_mode)
                        or old.st_uid != os.getuid()
                        or stat.S_IMODE(old.st_mode) & 0o077
                        or old.st_nlink != 1
                        or len(previous) != 64
                        or os.read(oldfd, 65) != previous
                        or (old.st_dev, old.st_ino)
                        != (old_entry.st_dev, old_entry.st_ino)
                    ):
                        raise ValueError("foreign capability")
                    os.unlink(name, dir_fd=self.fd)
                finally:
                    os.close(oldfd)
            self.token = secrets.token_hex(32)
            os.lseek(self.lock_fd, 0, os.SEEK_SET)
            os.ftruncate(self.lock_fd, 0)
            if os.write(self.lock_fd, self.token.encode("ascii")) != 64:
                raise OSError("short lock write")
            os.fsync(self.lock_fd)
            # An unnamed inode avoids a partial published token if the process
            # dies during creation. Unsupported filesystems fail closed.
            capfd = os.open(".", os.O_TMPFILE | os.O_RDWR, 0o600, dir_fd=self.fd)
            try:
                info = os.fstat(capfd)
                if os.write(capfd, self.token.encode("ascii")) != 64:
                    raise OSError("short write")
                os.fsync(capfd)
                libc = ctypes.CDLL(None, use_errno=True)
                linkat = libc.linkat
                linkat.argtypes = [
                    ctypes.c_int,
                    ctypes.c_char_p,
                    ctypes.c_int,
                    ctypes.c_char_p,
                    ctypes.c_int,
                ]
                linkat.restype = ctypes.c_int
                result = linkat(capfd, b"", self.fd, name.encode("ascii"), 0x1000)
                if result != 0 and ctypes.get_errno() == errno.ENOENT:
                    # Some kernels require the procfs descriptor path rather
                    # than AT_EMPTY_PATH for an unprivileged caller.
                    source = f"/proc/self/fd/{capfd}".encode("ascii")
                    result = linkat(-100, source, self.fd, name.encode("ascii"), 0x400)
                if result != 0:
                    error = ctypes.get_errno()
                    raise OSError(error, os.strerror(error))
                self.identity = (info.st_dev, info.st_ino)
            finally:
                os.close(capfd)
        except BaseException:
            self.close()
            raise

    def close(self):
        try:
            if self.fd is not None and self.identity is not None:
                try:
                    info = os.stat(
                        "inkecho-fcitx-candidate.cap",
                        dir_fd=self.fd,
                        follow_symlinks=False,
                    )
                    if (info.st_dev, info.st_ino) == self.identity:
                        os.unlink("inkecho-fcitx-candidate.cap", dir_fd=self.fd)
                except FileNotFoundError:
                    pass
        finally:
            self.identity = None
            try:
                if self.lock_fd is not None:
                    os.close(self.lock_fd)
            finally:
                self.lock_fd = None
                try:
                    if self.fd is not None:
                        os.close(self.fd)
                finally:
                    self.fd = None
                    self.token = ""
