"""Per-task Linux capability files for the experimental IBus bridge.

The runtime directory is assumed private to cooperating same-UID processes. It is
not a security boundary against malicious code running as the same user.
"""

import fcntl
import os
import secrets
import stat
from pathlib import Path


class LifecycleError(RuntimeError):
    pass


def _directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o077:
            raise LifecycleError("unsafe_directory")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _matching_unlink(dirfd, name, identity):
    try:
        st = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
        if (st.st_dev, st.st_ino) == identity:
            os.unlink(name, dir_fd=dirfd)
    except FileNotFoundError:
        pass


class Capability:
    def __init__(self, directory):
        self._dir = _directory(directory)
        self.name = "cap-" + secrets.token_hex(16)
        self.path = Path(directory) / self.name
        self.token = secrets.token_hex(32)
        self._fd = None
        self._identity = None
        try:
            self._fd = os.open(
                self.name,
                os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=self._dir,
            )
            st = os.fstat(self._fd)
            self._identity = (st.st_dev, st.st_ino)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            data = self.token.encode("ascii")
            if os.write(self._fd, data) != len(data):
                raise LifecycleError("short_write")
            os.fsync(self._fd)
        except BaseException:
            if self._identity is not None:
                try:
                    _matching_unlink(self._dir, self.name, self._identity)
                except OSError:
                    # Preserve the original failure if safe cleanup fails.
                    pass
            if self._fd is not None:
                os.close(self._fd)
            os.close(self._dir)
            raise

    def close(self):
        if self._fd is None:
            return
        try:
            for name in (self.name, "used-" + self.name):
                _matching_unlink(self._dir, name, self._identity)
        finally:
            os.close(self._fd)
            os.close(self._dir)
            self._fd = None
            self.token = ""
