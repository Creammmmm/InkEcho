// SPDX-License-Identifier: MIT
// Isolated policy prototype; not registered on D-Bus and not a product backend.
// A caller must first authenticate the unique D-Bus sender and capability.
export class DeliveryGate {
    constructor(deliver, capabilityCheck) {
        this._deliver = deliver;
        this._capabilityCheck = capabilityCheck;
        this._session = null;
        this._usedTokens = new Set();
    }

    begin(sender, token) {
        if (this._session !== null || this._usedTokens.size >= 1024 ||
            this._usedTokens.has(token) || !this._capabilityCheck(sender, token))
            return false;
        this._usedTokens.add(token);
        this._session = {sender, token, next: 0, failed: false};
        return true;
    }

    cancel(sender, token) {
        if (!this._matches(sender, token)) return false;
        this._session = null;
        return true;
    }

    ownerLost(sender) {
        if (this._session?.sender === sender) this._session = null;
    }

    commit(sender, token, sequence, character) {
        if (!this._matches(sender, token) || this._session.failed ||
            !Number.isSafeInteger(sequence) || sequence !== this._session.next)
            return 'rejected';
        // LF and Tab are supported; all other controls remain rejected.
        if (typeof character !== 'string' || [...character].length !== 1)
            return 'rejected';
        const point = character.codePointAt(0);
        if ((point < 0x20 && point !== 9 && point !== 10) || (point >= 0x7f && point <= 0x9f) ||
            (point >= 0xd800 && point <= 0xdfff)) return 'rejected';
        // Mark before invoking a transport: any exception leaves delivery unknown.
        this._session.next++;
        try {
            if (!this._deliver(character)) {
                this._session.failed = true;
                return 'unknown';
            }
            return 'attempted'; // Never an acknowledgement from the target.
        } catch (_error) {
            this._session.failed = true;
            return 'unknown';
        }
    }

    _matches(sender, token) {
        return this._session !== null && this._session.sender === sender &&
            this._session.token === token && this._capabilityCheck(sender, token);
    }
}
