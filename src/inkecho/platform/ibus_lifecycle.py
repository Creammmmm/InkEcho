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


class LifecycleCleanupError(LifecycleError, OSError):
    """A capability or descriptor could not be cleaned with certainty."""


def _directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o077:
            raise LifecycleError("unsafe_directory")
        return fd
    except BaseException as error:
        try:
            os.close(fd)
        except OSError:
            if not isinstance(error, Exception):
                error.cleanup_failed = True
                raise error from None
            raise LifecycleCleanupError("cleanup_failed") from None
        raise


def _matching_unlink(dirfd, name, identity):
    try:
        st = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
        if (st.st_dev, st.st_ino) == identity:
            os.unlink(name, dir_fd=dirfd)
            return True
        return False
    except FileNotFoundError:
        return True


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
        except BaseException as error:
            cleanup_failed = self._fd is not None and self._identity is None
            if self._identity is not None:
                try:
                    cleanup_failed |= not _matching_unlink(
                        self._dir, self.name, self._identity
                    )
                except OSError:
                    cleanup_failed = True
            for fd in (self._fd, self._dir):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        cleanup_failed = True
            self._fd = None
            self.token = ""
            if cleanup_failed:
                # No object is returned to the caller, so propagate uncertainty
                # explicitly. Preserve task cancellation without hiding cleanup.
                if isinstance(error, BaseException) and not isinstance(
                    error, Exception
                ):
                    error.cleanup_failed = True
                    raise
                raise LifecycleCleanupError("cleanup_failed") from None
            raise

    def close(self):
        if self._fd is None:
            return
        cleanup_failed = False
        try:
            for name in (self.name, "used-" + self.name):
                try:
                    if not _matching_unlink(self._dir, name, self._identity):
                        cleanup_failed = True
                except OSError:
                    cleanup_failed = True
            try:
                # The server only renames our inode to used-<name>. A linked
                # inode after checking both names may have been moved elsewhere.
                info = os.fstat(self._fd)
                if (info.st_dev, info.st_ino) != self._identity or info.st_nlink:
                    cleanup_failed = True
            except OSError:
                cleanup_failed = True
        finally:
            for fd in (self._fd, self._dir):
                try:
                    os.close(fd)
                except OSError:
                    cleanup_failed = True
            self._fd = None
            self.token = ""
        if cleanup_failed:
            raise LifecycleCleanupError("cleanup_failed") from None
