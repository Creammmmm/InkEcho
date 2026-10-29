import assert from 'node:assert/strict';
import {DeliveryGateV2} from './delivery_gate_v2.js';

const outstanding = new Set();
let sent = [];
const gate = new DeliveryGateV2(c => { sent.push(c); return true; },
    token => outstanding.delete(token));
for (let i = 0; i < 2048; i++) {
    const token = `token-${i}`, owner = `:1.${i + 1}`;
    outstanding.add(token);
    assert.equal(gate.begin(owner, token), true);
    assert.equal(gate.commit(owner, 0, '甲'), 'attempted');
    assert.equal(gate.commit(owner, 0, '乙'), 'rejected');
    assert.equal(gate.cancel(owner), true);
    assert.equal(gate.begin(owner, token), false);
    assert.equal(gate.begin(`:2.${i}`, token), false);
    gate.ownerLost(owner);
}
assert.equal(gate.closedSenders.size, 0);
assert.equal(sent.length, 2048);
outstanding.add('active'); outstanding.add('second');
assert.equal(gate.begin(':3.1', 'active'), true);
assert.equal(gate.begin(':3.2', 'second'), false);
assert.equal(gate.commit(':3.2', 0, '甲'), 'rejected');
assert.equal(gate.commit(':3.1', 0, '\n'), 'attempted');
gate.ownerLost(':3.1');
assert.equal(gate.commit(':3.1', 1, '乙'), 'rejected');
assert.equal(gate.begin(':3.2', 'second'), true);
console.log('design-only sender and consumed-token model passed');
