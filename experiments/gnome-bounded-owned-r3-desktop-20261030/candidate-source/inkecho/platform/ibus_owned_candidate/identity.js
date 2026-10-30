// Identity scope only: this NEVER acknowledges target receipt.
export function verdict(s, current) {
    if (!s.native || !s.focused || s.shellUi || !s.shellPath)
        return 'not_applicable';
    if (s.preedit !== false)
        return 'busy_or_unknown';
    if (typeof current !== 'string' || current !== s.shellPath)
        return 'context_mismatch';
    return 'gnome_owned_native_candidate';
}
