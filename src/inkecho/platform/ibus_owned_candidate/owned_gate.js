import {verdict} from './identity.js';
const BOUNDED = Symbol('bounded');

// One pending query per session. Never retries or credits target receipt.
export class OwnedGate {
    constructor(delivery, snapshot, current, boundary) {
        this.delivery = delivery;
        this.boundary = boundary;
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
    beginBatch(sender, token, version) {
        if (this.closed || this.pending) return false;
        const ok = this.delivery.beginBatch(sender, token, version);
        if (ok) this.generation++;
        return ok;
    }
    beginBounded(sender, token, version, deadlineUs) {
        if (this.closed || this.pending) return false;
        const ok = this.delivery.beginBounded(sender, token, version, deadlineUs);
        if (ok) this.generation++;
        return ok;
    }
    async commitBounded(sender, sequence, text, deadlineUs) {
        const s = this.delivery.session;
        if (this.closed || this.pending || !s || s.sender !== sender ||
            s.failed || sequence !== s.next || s.deadlineUs === undefined)
            return 'rejected';
        if (!Number.isSafeInteger(deadlineUs) || deadlineUs <= 0 ||
            deadlineUs > s.deadlineUs) { s.failed = true; return 'unknown'; }
        let requestToken;
        if (s.version === 2) {
            let now;
            try { now = this.delivery.clockUs(); } catch (_) { s.failed = true; return 'unknown'; }
            if (!Number.isSafeInteger(now) || deadlineUs <= now || deadlineUs - now > 3_000_000) {
                s.failed = true; return 'unknown';
            }
            requestToken = Symbol('request');
            s.requestToken = requestToken;
            s.requestDeadlineUs = deadlineUs;
        } else {
            s.deadlineUs = deadlineUs; // Legacy contract never extends.
        }
        try {
            return await this.commit(sender, sequence, text, true, BOUNDED);
        } finally {
            if (s.version === 2 && s.requestToken === requestToken) {
                delete s.requestDeadlineUs;
                delete s.requestToken;
            }
        }
    }
    reject() {
        const s = this.delivery.session;
        if (!s) return 'rejected';
        s.failed = true;
        return s.attempts === 0 ? 'no_service' : 'unknown';
    }
    async commit(sender, sequence, text, batch = false, authorization = null) {
        const s = this.delivery.session;
        if (this.closed || this.pending || !s || s.sender !== sender ||
            s.failed || sequence !== s.next ||
            (s.version === 2 && authorization !== BOUNDED)) return 'rejected';
        if (!this.delivery.unexpired()) { s.failed = true; return 'unknown'; }
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
            if (!this.delivery.unexpired()) { s.failed = true; return 'unknown'; }
            const after = this.snapshot();
            if (after.preedit !== false) { s.failed = true; return 'unknown'; }
            if (before.im !== after.im || before.epoch !== after.epoch ||
                before.window !== after.window || before.shellPath !== after.shellPath ||
                verdict(after, path) !== 'gnome_owned_native_candidate')
                return this.reject();
            // No await between final identity guard and panel dispatch attempt.
            const result = batch ? this.delivery.commitBatch(sender, sequence, text) :
                this.delivery.commit(sender, sequence, text);
            if (result !== 'attempted') return result;
            const completed = await this.boundary();
            if (!completed || this.closed || generation !== this.generation ||
                this.delivery.session !== s) { s.failed = true; return 'unknown'; }
            if (!this.delivery.unexpired()) { s.failed = true; return 'unknown'; }
            return result;
        } catch (_) {
            // A failed query/snapshot cannot prove absence of composition or target.
            if (generation !== this.generation || this.delivery.session !== s)
                return 'rejected';
            s.failed = true;
            return 'unknown';
        } finally { this.pending = false; }
    }
    cancel(sender, abort = () => {}) {
        const ok = this.delivery.cancel(sender);
        if (ok) {
            this.generation++;
            abort(); // Only the authenticated current sender may abort its boundary.
        }
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
