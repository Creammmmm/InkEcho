// Experiment policy only: attempted never means delivered.
export class Gate {
    constructor(snapshot, commit) {
        this.snapshot = snapshot;
        this.deliver = commit;
        this.owner = null;
        this.attempts = 0;
        this.next = 0;
        this.closed = true;
    }
    begin(owner) {
        if (this.owner !== null || !owner?.startsWith(':')) return false;
        this.owner = owner;
        this.closed = false;
        return true;
    }
    cancel(owner) {
        if (owner !== this.owner) return false;
        this.closed = true;
        return true;
    }
    send(owner, seq) {
        if (owner !== this.owner || this.closed || seq !== this.next)
            return 'stopped';
        let s;
        try { s = this.snapshot(); } catch (_) { return 'unsupported'; }
        if (s.supported !== true) return 'unsupported';
        if (s.owned !== true || s.focused !== true)
            return this.attempts === 0 ? 'not_attempted' : 'suffix_not_attempted';
        // Never feed the keyboard into an existing composition either.
        if (s.preedit !== false) return 'busy';
        // Increment BEFORE invoking any code that may have side effects.
        this.attempts++;
        this.next++;
        try { this.deliver(); } catch (_) {
            this.closed = true;
            return 'unknown';
        }
        return 'attempted';
    }
    canFallback(status) {
        return status === 'not_attempted' && this.attempts === 0;
    }
}
