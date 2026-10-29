// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import {DeliveryGate} from './delivery_gate.js';
let delivered = [];
const gate = new DeliveryGate(c => { delivered.push(c); return true; },
    (sender, token) => sender === ':1.10' && ['fresh-a', 'fresh-b'].includes(token));
assert.equal(gate.begin(':1.2', 'fresh-a'), false);
assert.equal(gate.begin(':1.10', 'fresh-a'), true);
assert.equal(gate.commit(':1.10', 'fresh-a', 0, '甲'), 'attempted');
assert.equal(gate.commit(':1.10', 'fresh-a', 0, '甲'), 'rejected');
assert.equal(gate.cancel(':1.2', 'fresh-a'), false);
assert.equal(gate.cancel(':1.10', 'fresh-a'), true);
assert.equal(gate.begin(':1.10', 'fresh-a'), false); // Token cannot be reused.
assert.equal(gate.begin(':1.10', 'fresh-b'), true);
assert.equal(gate.commit(':1.10', 'fresh-a', 1, '乙'), 'rejected');
assert.equal(gate.commit(':1.10', 'fresh-b', 0, '乙'), 'attempted');
gate.ownerLost(':1.10');
assert.equal(gate.commit(':1.10', 'fresh-b', 1, '丙'), 'rejected');
assert.deepEqual(delivered, ['甲', '乙']);
console.log('candidate gate checks passed');
