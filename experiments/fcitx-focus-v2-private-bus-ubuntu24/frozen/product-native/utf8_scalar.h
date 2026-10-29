// SPDX-License-Identifier: MIT
#pragma once
#include <string_view>

inline bool inkecho_one_scalar(std::string_view text) {
    if (text.empty() || text.size() > 4) return false;
    const auto first = static_cast<unsigned char>(text[0]);
    const auto size = text.size();
    if (first == 0x09 || first == 0x0a || (first >= 0x20 && first <= 0x7e))
        return size == 1;
    if (first >= 0xc2 && first <= 0xdf) {
        if (size != 2) return false;
    } else if (first >= 0xe0 && first <= 0xef) {
        if (size != 3) return false;
    } else if (first >= 0xf0 && first <= 0xf4) {
        if (size != 4) return false;
    } else {
        return false;
    }
    for (std::size_t i = 1; i < size; ++i) {
        const auto c = static_cast<unsigned char>(text[i]);
        if (c < 0x80 || c > 0xbf) return false;
    }
    const auto second = static_cast<unsigned char>(text[1]);
    return !(first == 0xc2 && second < 0xa0) &&
           !(first == 0xe0 && second < 0xa0) &&
           !(first == 0xed && second >= 0xa0) &&
           !(first == 0xf0 && second < 0x90) &&
           !(first == 0xf4 && second >= 0x90);
}
