// SPDX-License-Identifier: MIT
// Offline candidate only: not connected to the existing Fcitx D-Bus object.
#pragma once
#include <array>
#include <chrono>
#include <cstdint>
#include <fcntl.h>
#include <set>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

#include "../../native/fcitx5/utf8_scalar.h"

namespace inkecho_experiment {
inline bool valid_token(const std::string &token) {
    if (token.size() != 64) return false;
    for (char c : token) if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

// The private runtime directory and file are opened with no symlink following.
// This prevents accidental misuse, not malicious access by the same UID.
inline bool capability_matches(const std::string &runtime, const std::string &token) {
    if (!valid_token(token)) return false;
    int dir = open(runtime.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (dir < 0) return false;
    struct stat st{};
    if (fstat(dir, &st) != 0 || !S_ISDIR(st.st_mode) || st.st_uid != getuid() || (st.st_mode & 0077)) {
        close(dir); return false;
    }
    int fd = openat(dir, "inkecho-fcitx-candidate.cap", O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    close(dir);
    if (fd < 0) return false;
    bool safe = fstat(fd, &st) == 0 && S_ISREG(st.st_mode) && st.st_uid == getuid() &&
                !(st.st_mode & 0077) && st.st_size == 64 && st.st_nlink == 1;
    std::array<char, 65> bytes{};
    ssize_t n = safe ? read(fd, bytes.data(), bytes.size()) : -1;
    close(fd);
    if (n != 64) return false;
    unsigned difference = 0;
    for (std::size_t i = 0; i < 64; ++i) difference |= static_cast<unsigned char>(bytes[i] ^ token[i]);
    return difference == 0;
}

// Caller must provide the D-Bus sender supplied by the bus, never a client field.
// Designed for one serialized event loop. Returns attempted, not display ack.
class Gate {
public:
    using Clock = std::chrono::steady_clock;
    explicit Gate(std::string runtime) : runtime_(std::move(runtime)) {}
    bool begin(const std::string &sender, const std::string &token, Clock::time_point deadline) {
        if (active_ || sender.empty() || sender[0] != ':' || used_.size() >= 1024 ||
            used_.count(token) || deadline <= Clock::now() || !capability_matches(runtime_, token)) return false;
        used_.insert(token); sender_ = sender; token_ = token; next_ = 0; deadline_ = deadline;
        active_ = true; return true;
    }
    bool cancel(const std::string &sender, const std::string &token) {
        if (!matches(sender, token)) return false;
        clear(); return true;
    }
    void owner_lost(const std::string &sender) { if (active_ && sender == sender_) clear(); }
    template<class Deliver>
    bool commit(const std::string &sender, const std::string &token, std::uint64_t seq,
                const std::string &text, Deliver deliver) {
        if (!matches(sender, token) || inflight_ || seq != next_) return false;
        if (!capability_matches(runtime_, token) || Clock::now() >= deadline_ || !inkecho_one_scalar(text)) { clear(); return false; }
        ++next_; inflight_ = true;
        bool delivered = false;
        try { delivered = deliver(text); } catch (...) { delivered = false; }
        inflight_ = false;
        if (!delivered) clear();
        return delivered;
    }
private:
    bool matches(const std::string &sender, const std::string &token) const {
        return active_ && sender == sender_ && token == token_;
    }
    void clear() { active_ = false; sender_.clear(); token_.clear(); }
    std::string runtime_, sender_, token_;
    std::set<std::string> used_;
    std::uint64_t next_ = 0;
    Clock::time_point deadline_{};
    bool active_ = false, inflight_ = false;
};
} // namespace inkecho_experiment
