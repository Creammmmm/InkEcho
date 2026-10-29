// Design-only model. It is not installed or used by the product extension.
// consume(token) must atomically consume and authenticate a one-use capability;
// this file does not implement that filesystem operation.
export class DeliveryGateV2 {
    constructor(deliver, consume) {
        this.deliver = deliver;
        this.consume = consume;
        this.session = null;
        this.closedSenders = new Set();
    }

    begin(sender, token) {
        if (this.session || this.closedSenders.has(sender) || !this.consume(token))
            return false;
        this.closedSenders.add(sender);
        this.session = {sender, next: 0, failed: false};
        return true;
    }

    commit(sender, sequence, character) {
        const s = this.session;
        if (!s || s.sender !== sender || s.failed || sequence !== s.next ||
            !Number.isSafeInteger(sequence) || typeof character !== 'string' ||
            [...character].length !== 1) return 'rejected';
        const point = character.codePointAt(0);
        if ((point < 0x20 && point !== 9 && point !== 10) ||
            (point >= 0x7f && point <= 0x9f) ||
            (point >= 0xd800 && point <= 0xdfff)) return 'rejected';
        s.next++;
        try {
            if (this.deliver(character)) return 'attempted';
        } catch (_) { /* Treat attempted delivery as ambiguous. */ }
        s.failed = true;
        return 'unknown';
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
