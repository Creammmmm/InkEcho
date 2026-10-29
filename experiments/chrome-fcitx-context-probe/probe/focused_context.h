// SPDX-License-Identifier: MIT
#pragma once

// Reject multiple active contexts because this bridge cannot identify a seat.
template <typename Context, typename Manager>
Context *inkecho_unique_focus(Manager &manager) {
    Context *target = nullptr;
    bool ambiguous = false;
    manager.foreachFocused([&](Context *candidate) {
        if (target) {
            ambiguous = true;
            return false;
        }
        target = candidate;
        return true;
    });
    return ambiguous ? nullptr : target;
}
