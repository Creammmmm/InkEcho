// Read-only identity scope; blocked means composition must NOT use fallback.
export async function probeOwned(snapshot, current, active) {
    try {
        const before = snapshot();
        if (!active()) return 'unknown';
        // Composition takes priority even when this is not an owned native target.
        if (before.preedit !== false) return 'blocked';
        if (!before.native || !before.focused || before.shellUi ||
            !before.shellPath) return 'none';
        const path = await current(before.im);
        const after = snapshot();
        if (!active() || before.im !== after.im || before.epoch !== after.epoch ||
            before.window !== after.window || before.shellPath !== after.shellPath ||
            !after.native || !after.focused || after.shellUi ||
            path !== after.shellPath) return 'unknown';
        return after.preedit === false ? 'ready' : 'blocked';
    } catch (_) { return 'unknown'; }
}
