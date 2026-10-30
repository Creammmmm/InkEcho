"""Offline Fcitx candidate capability; not used by the product."""

import os
import secrets
import stat


class Capability:
    def __init__(self, runtime_dir):
        self.fd = None
        self.identity = None
        self.cap_fd = None
        self.token = ""
        self.fd = os.open(runtime_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(self.fd)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise ValueError("unsafe runtime")
            self.token = secrets.token_hex(32)
            fd = self.cap_fd = os.open(
                "inkecho-fcitx-candidate.cap",
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                0o600,
                dir_fd=self.fd,
            )
            # Keep the original inode alive until cleanup. Otherwise a
            # replaced entry can immediately reuse its inode number.
            info = os.fstat(fd)
            self.identity = (info.st_dev, info.st_ino)
            if os.write(fd, self.token.encode("ascii")) != 64:
                raise OSError("short write")
            os.fsync(fd)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.fd is not None and self.identity is not None:
            try:
                info = os.stat(
                    "inkecho-fcitx-candidate.cap", dir_fd=self.fd, follow_symlinks=False
                )
                if (
                    stat.S_ISREG(info.st_mode)
                    and (info.st_dev, info.st_ino) == self.identity
                ):
                    os.unlink("inkecho-fcitx-candidate.cap", dir_fd=self.fd)
            except FileNotFoundError:
                pass
            self.identity = None
        if self.cap_fd is not None:
            os.close(self.cap_fd)
            self.cap_fd = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.token = ""
