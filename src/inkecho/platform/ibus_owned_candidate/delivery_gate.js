// Design-only model. It is not installed or used by the product extension.
// consume(token) must atomically consume and authenticate a one-use capability;
// this file does not implement that filesystem operation.
export class DeliveryGateV2 {
    constructor(resolve, consume, clockUs = null) {
        this.resolve = resolve;
        this.clockUs = clockUs;
        this.consume = consume;
        this.session = null;
        this.closedSenders = new Set();
    }

    begin(sender, token, batch = false) {
        if (this.session || this.closedSenders.has(sender) || !this.consume(token))
            return false;
        this.closedSenders.add(sender);
        this.session = {sender, next: 0, attempts: 0, characters: 0, batch, failed: false};
        return true;
    }

    beginBatch(sender, token, version) {
        return version === 1 && this.begin(sender, token, true);
    }

    beginBounded(sender, token, version, deadlineUs) {
        if (![1, 2].includes(version) || !this.clockUs || !Number.isSafeInteger(deadlineUs))
            return false;
        let now;
        try { now = this.clockUs(); } catch (_) { return false; }
        if (!Number.isSafeInteger(now) || deadlineUs <= now ||
            deadlineUs - now > (version === 2 ? 555_000_000 : 60_000_000)) return false;
        if (!this.begin(sender, token, true)) return false;
        this.session.deadlineUs = deadlineUs;
        this.session.version = version;
        return true;
    }
    unexpired() {
        const s = this.session;
        if (!s || s.deadlineUs === undefined) return true; // Legacy, no new guarantee.
        try {
            const now = this.clockUs();
            return Number.isSafeInteger(now) && now < s.deadlineUs &&
                (s.version !== 2 || (Number.isSafeInteger(s.requestDeadlineUs) &&
                    now < s.requestDeadlineUs));
        } catch (_) { return false; }
    }
    commit(sender, sequence, text) {
        return this._commit(sender, sequence, text, false);
    }

    commitBatch(sender, sequence, text) {
        return this._commit(sender, sequence, text, true);
    }

    _commit(sender, sequence, text, batch) {
        const s = this.session;
        if (!s || s.sender !== sender || s.failed ||
            (s.version === 2 && !Number.isSafeInteger(s.requestDeadlineUs))) return 'rejected';
        if (!this.unexpired()) { s.failed = true; return 'unknown'; }
        if (typeof text !== 'string' || text.length < 1 || text.length > (batch ? 6 : 2)) {
            s.failed = true; return 'rejected';
        }
        const points = [...text];
        if (sequence !== s.next || !Number.isSafeInteger(sequence) ||
            s.batch !== batch || points.length < 1 ||
            points.length > (batch ? 3 : 1) || text === '\n' ||
            points.some(character => {
                const point = character.codePointAt(0);
                return (point < 0x20 && point !== 9 && point !== 10) ||
                    (point >= 0x7f && point <= 0x9f) ||
                    (point >= 0xd800 && point <= 0xdfff);
            })) { s.failed = true; return 'rejected'; }
        let deliver;
        try { deliver = this.resolve(); } catch (_) {
            s.failed = true;
            return 'unknown';
        }
        if (!deliver) {
            s.failed = true;
            return s.attempts === 0 ? 'no_service' : 'unknown';
        }
        s.next++;
        s.attempts++;
        s.characters += points.length;
        try {
            // Final service-clock check immediately before synchronous dispatch.
            if (!this.unexpired()) { s.failed = true; return 'unknown'; }
            deliver(text); return 'attempted';
        }
        catch (_) { s.failed = true; return 'unknown'; }
    }

    cancel(sender) {
        if (!this.session || this.session.sender !== sender) return false;
        this.session = null;
        return true;
    }

    ownerLost(sender) {
        if (this.session?.sender === sender) this.session = null;
        this.closedSenders.delete(sender);
    }
}
