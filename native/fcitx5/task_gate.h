// SPDX-License-Identifier: MIT
// One-task gate; same-UID processes are not a security boundary.
#pragma once
#include <array>
#include <cstdint>
#include <cstdlib>
#include <fcntl.h>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include "utf8_scalar.h"

namespace inkecho {
inline bool consume_capability(const std::string &token) {
    if (token.size() != 64) return false;
    for (char c : token) if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    const char *runtime = std::getenv("XDG_RUNTIME_DIR");
    if (!runtime || !*runtime) return false;
    int dir = open(runtime, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (dir < 0) return false;
    struct stat d{}, st{}, entry{};
    if (fstat(dir, &d) || !S_ISDIR(d.st_mode) || d.st_uid != getuid() || (d.st_mode & 0077)) { close(dir); return false; }
    const char *name = "inkecho-fcitx-candidate.cap";
    int fd = openat(dir, name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0) { close(dir); return false; }
    bool safe = fstat(fd, &st) == 0 && S_ISREG(st.st_mode) && st.st_uid == getuid() &&
                !(st.st_mode & 0077) && st.st_size == 64 && st.st_nlink == 1;
    std::array<char, 65> bytes{};
    ssize_t n = safe ? read(fd, bytes.data(), bytes.size()) : -1;
    unsigned diff = 0;
    if (n == 64) for (std::size_t i=0; i<64; ++i) diff |= static_cast<unsigned char>(bytes[i] ^ token[i]);
    safe = n == 64 && diff == 0 && fstatat(dir, name, &entry, AT_SYMLINK_NOFOLLOW) == 0 &&
           entry.st_dev == st.st_dev && entry.st_ino == st.st_ino && unlinkat(dir, name, 0) == 0;
    close(fd); close(dir); return safe;
}
class TaskGate {
public:
    bool begin(const std::string &sender, const std::string &token) {
        if (active_ || sender.empty() || sender[0] != ':' || !consume_capability(token)) return false;
        sender_=sender; token_=token; next_=0; active_=true;
        return true;
    }
    bool cancel(const std::string &sender, const std::string &token) {
        if (!matches(sender, token)) return false;
        clear(); return true;
    }
    void owner_lost(const std::string &sender, const std::string &token) {
        if (matches(sender, token)) clear();
    }
    template<typename Deliver>
    std::uint32_t commit(const std::string &sender, const std::string &token, std::uint32_t sequence,
                const std::string &scalar, Deliver deliver) {
        if (!matches(sender, token) || sequence != next_) return 0;
        if (!inkecho_one_scalar(scalar)) { clear(); return 0; }
        bool ok=false;
        try { ok=deliver(scalar); } catch (...) { clear(); return 2; }
        // 3 means no commitString call was made and this sequence remains
        // valid. Protocol errors remain 0; exceptions are ambiguous (2).
        if (!ok) return 3;
        ++next_;
        return 1;
    }
private:
    bool matches(const std::string &sender,const std::string &token) const { return active_ && sender == sender_ && token == token_; }
    void clear() { active_=false; sender_.clear(); token_.clear(); }
    std::string sender_, token_;
    std::uint32_t next_=0;
    bool active_=false;
};
}
