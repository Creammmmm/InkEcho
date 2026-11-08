import assert from 'node:assert/strict';
import {OwnedGate} from '../../src/inkecho/platform/ibus_owned_candidate/owned_gate.js';
import {DeliveryGateV2} from '../../src/inkecho/platform/ibus_owned_candidate/delivery_gate.js';

function setup() {
    const snapshot = {
        native: true, focused: true, shellUi: false, shellPath: '/A',
        preedit: false, epoch: 1, window: 1, im: {},
    };
    const sent = [];
    let now = 1000, boundaries = 0;
    const delivery = new DeliveryGateV2(
        () => text => sent.push([snapshot.window, text]),
        () => true, () => now);
    const gate = new OwnedGate(delivery, () => ({...snapshot}),
        async () => snapshot.shellPath,
        async () => { boundaries++; return true; });
    assert(gate.beginBounded(':a', [], 2, 100000));
    return {
        snapshot, gate, sent,
        get boundaries() { return boundaries; },
        set now(value) { now = value; },
    };
}

for (const aba of [false, true]) {
    const t = setup();
    let queries = 0;
    t.gate.current = async () => {
        queries++;
        const oldPath = t.snapshot.shellPath;
        if (queries === 1) {
            t.snapshot.epoch += aba ? 2 : 1;
            if (!aba) {
                t.snapshot.window = 2;
                t.snapshot.shellPath = '/B';
            }
        }
        return oldPath;
    };
    assert.equal(await t.gate.commitBounded(':a', 0, '甲', 90000), 'attempted');
    assert.equal(queries, 2);
    assert.equal(t.boundaries, 2); // Pre-send settling and post-send boundary.
    assert.deepEqual(t.sent, [[aba ? 1 : 2, '甲']]);

    // A completed unit never pins the next unit's recipient.
    t.snapshot.window = 3;
    t.snapshot.shellPath = '/C';
    t.snapshot.epoch++;
    assert.equal(await t.gate.commitBounded(':a', 1, '乙', 90000), 'attempted');
    assert.deepEqual(t.sent[1], [3, '乙']);
}

for (const mode of [
    'cancel', 'owner', 'expiry', 'busy', 'unknown', 'unsupported',
    'boundary-fail', 'unstable', 'query-error', 'mismatch',
]) {
    const t = setup();
    let queries = 0, boundaries = 0;
    t.gate.current = async () => {
        queries++;
        if (mode === 'query-error') throw Error('synthetic');
        if (mode === 'mismatch') return '/other';
        t.snapshot.epoch++;
        return t.snapshot.shellPath;
    };
    t.gate.boundary = async () => {
        boundaries++;
        if (mode === 'cancel') t.gate.cancel(':a');
        if (mode === 'owner') t.gate.ownerLost(':a');
        if (mode === 'expiry') t.now = 100000;
        if (mode === 'busy') t.snapshot.preedit = true;
        if (mode === 'unknown') t.snapshot.preedit = null;
        if (mode === 'unsupported') t.snapshot.native = false;
        return mode !== 'boundary-fail';
    };
    const result = await t.gate.commitBounded(':a', 0, '甲', 90000);
    assert.notEqual(result, 'attempted', mode);
    assert.deepEqual(t.sent, [], mode);
    assert(queries <= 2 && boundaries <= 1, mode);
    if (mode === 'unstable') {
        assert.equal(queries, 2);
        assert.equal(boundaries, 1);
    }
    if (mode === 'query-error' || mode === 'mismatch')
        assert.equal(boundaries, 0);
}

{
    const t = setup();
    t.gate.boundary = async () => {
        t.snapshot.epoch++;
        return false;
    };
    assert.equal(await t.gate.commitBounded(':a', 0, '甲', 90000), 'unknown');
    assert.equal(t.sent.length, 1);
    assert.equal(await t.gate.commitBounded(':a', 0, '甲', 90000), 'rejected');
    assert.equal(t.sent.length, 1);
}
console.log('focus recheck tests passed');
