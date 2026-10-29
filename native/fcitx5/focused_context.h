// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>

// Count at most two contexts; do not guess a seat or identify a target by name.
template <typename Context> struct InkEchoFocusSelection {
    Context *target = nullptr;
    bool ambiguous = false;
};
template <typename Context, typename Manager>
InkEchoFocusSelection<Context> inkecho_focus_selection(Manager &manager) {
    InkEchoFocusSelection<Context> selection;
    manager.foreachFocused([&](Context *candidate) {
        if (selection.target) {
            selection.ambiguous = true;
            return false;
        }
        selection.target = candidate;
        return true;
    });
    if (selection.ambiguous) selection.target = nullptr;
    return selection;
}
// Retain the original helper contract for existing callers.
template <typename Context, typename Manager>
Context *inkecho_unique_focus(Manager &manager) {
    return inkecho_focus_selection<Context>(manager).target;
}

// Only a Begin2 task receives the additive result. Legacy clients retain 3.
template <typename Context>
std::uint32_t inkecho_focus_rejection(const InkEchoFocusSelection<Context> &selection, bool detailed) {
    return detailed && selection.ambiguous ? 4 : 3;
}

// Do not inspect text, reset composition or flush queued frontend events.
// A non-empty panel includes client/server preedit, candidates and auxiliary UI.
template <typename Context>
bool inkecho_composition_blocked(Context &context) {
    return !context.inputPanel().empty() || context.hasPendingEvents();
}
