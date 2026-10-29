import {verdict} from './identity.js';

// One pending query per session. Never retries or credits target receipt.
export class OwnedGate {
    constructor(delivery, snapshot, current) {
        this.delivery = delivery;
        this.snapshot = snapshot;
        this.current = current;
        this.generation = 0;
        this.pending = false;
        this.closed = false;
    }
    begin(sender, token) {
        if (this.closed || this.pending) return false;
        const ok = this.delivery.begin(sender, token);
        if (ok) this.generation++;
        return ok;
    }
    reject() {
        const s = this.delivery.session;
        if (!s) return 'rejected';
        s.failed = true;
        return s.attempts === 0 ? 'no_service' : 'unknown';
    }
    async commit(sender, sequence, text) {
        const s = this.delivery.session;
        if (this.closed || this.pending || !s || s.sender !== sender ||
            s.failed || sequence !== s.next) return 'rejected';
        const generation = this.generation;
        this.pending = true;
        try {
            const before = this.snapshot();
            // Composition is never a reason to fall back to keyboard output.
            if (before.preedit !== false) { s.failed = true; return 'unknown'; }
            if (verdict(before, before.shellPath) !== 'gnome_owned_native_candidate')
                return this.reject();
            const path = await this.current(before.im);
            if (this.closed || generation !== this.generation ||
                this.delivery.session !== s) return 'rejected';
            const after = this.snapshot();
            if (after.preedit !== false) { s.failed = true; return 'unknown'; }
            if (before.im !== after.im || before.epoch !== after.epoch ||
                before.window !== after.window || before.shellPath !== after.shellPath ||
                verdict(after, path) !== 'gnome_owned_native_candidate')
                return this.reject();
            // No await between final identity guard and panel dispatch attempt.
            return this.delivery.commit(sender, sequence, text);
        } catch (_) {
            // A failed query/snapshot cannot prove absence of composition or target.
            if (generation !== this.generation || this.delivery.session !== s)
                return 'rejected';
            s.failed = true;
            return 'unknown';
        } finally { this.pending = false; }
    }
    cancel(sender) {
        const ok = this.delivery.cancel(sender);
        if (ok) this.generation++;
        return ok;
    }
    ownerLost(sender) {
        if (this.delivery.session?.sender === sender) this.generation++;
        this.delivery.ownerLost(sender);
    }
    close() {
        this.closed = true;
        this.generation++;
        if (this.delivery.session) this.delivery.cancel(this.delivery.session.sender);
    }
}
