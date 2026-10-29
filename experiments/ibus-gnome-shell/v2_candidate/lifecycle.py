"""Independent Linux lifecycle prototype. Not connected to the product or D-Bus.

The runtime directory is assumed private to cooperating same-UID processes. It is
not a security boundary against malicious code running as the same user.
"""

import ctypes
import errno
import fcntl
import hmac
import os
import re
import secrets
import stat
import threading

_NAME = re.compile(r"cap-[0-9a-f]{32}\Z")
_LIBC = ctypes.CDLL(None, use_errno=True)
_LIBC.renameat2.argtypes = (
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_uint,
)
_LIBC.renameat2.restype = ctypes.c_int
_RENAME_NOREPLACE = 1


class LifecycleError(RuntimeError):
    pass


def _directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    st = os.fstat(fd)
    if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o077:
        os.close(fd)
        raise LifecycleError("unsafe_directory")
    return fd


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
        self.token = secrets.token_hex(32)
        self._fd = None
        try:
            self._fd = os.open(
                self.name,
                os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=self._dir,
            )
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            st = os.fstat(self._fd)
            self._identity = (st.st_dev, st.st_ino)
            data = self.token.encode("ascii")
            if os.write(self._fd, data) != len(data):
                raise LifecycleError("short_write")
            os.fsync(self._fd)
        except BaseException:
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


class Receiver:
    def __init__(self, directory):
        self._dir = _directory(directory)
        self._lock = threading.Lock()
        self._senders = set()
        self._session = None

    def begin(self, sender, name, token):
        with self._lock:
            if self._session is not None or sender in self._senders:
                return False
            if not isinstance(sender, str) or not sender.startswith(":"):
                return False
            if not isinstance(name, str) or not _NAME.fullmatch(name):
                return False
            if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{64}", token):
                return False
            try:
                fd = os.open(
                    name,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                    dir_fd=self._dir,
                )
            except OSError:
                return False
            try:
                st = os.fstat(fd)
                if (
                    not stat.S_ISREG(st.st_mode)
                    or st.st_uid != os.getuid()
                    or stat.S_IMODE(st.st_mode) != 0o600
                    or st.st_nlink != 1
                    or st.st_size != 64
                    or not hmac.compare_digest(os.read(fd, 65), token.encode("ascii"))
                ):
                    return False
                # Uniqueness is enforced by the kernel, not an existence check.
                result = _LIBC.renameat2(
                    self._dir,
                    name.encode(),
                    self._dir,
                    ("used-" + name).encode(),
                    _RENAME_NOREPLACE,
                )
                if result:
                    error = ctypes.get_errno()
                    if error in (errno.ENOENT, errno.EEXIST):
                        return False
                    raise OSError(error, os.strerror(error))
                moved = os.stat("used-" + name, dir_fd=self._dir, follow_symlinks=False)
                if (moved.st_dev, moved.st_ino) != (st.st_dev, st.st_ino):
                    # Preserve the moved file for inspection; never claim success.
                    return False
                self._senders.add(sender)
                self._session = {"sender": sender, "sequence": 0}
                return True
            finally:
                os.close(fd)

    def commit(self, sender, sequence):
        with self._lock:
            session = self._session
            if (
                not session
                or session["sender"] != sender
                or sequence != session["sequence"]
            ):
                return False
            session["sequence"] += 1
            return True

    def cancel(self, sender):
        with self._lock:
            if not self._session or self._session["sender"] != sender:
                return False
            self._session = None
            return True

    def owner_lost(self, sender):
        with self._lock:
            if self._session and self._session["sender"] == sender:
                self._session = None
            self._senders.discard(sender)

    def close(self):
        os.close(self._dir)
