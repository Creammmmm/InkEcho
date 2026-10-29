import assert from 'node:assert/strict';
import {Gate} from './gate.mjs';
let s, calls, g;
function reset() {
    s = {supported:true, owned:true, focused:true, preedit:false}; calls = 0;
    g = new Gate(() => s, () => calls++); assert(g.begin(':1.7'));
}
reset(); s.focused = false;
assert.equal(g.send(':1.7', 0), 'not_attempted');
assert(g.canFallback('not_attempted')); assert.equal(calls, 0);
reset(); s.preedit = true;
assert.equal(g.send(':1.7', 0), 'busy'); assert(!g.canFallback('busy'));
assert.equal(calls, 0); s.preedit = false;
assert.equal(g.send(':1.7', 0), 'attempted'); assert.equal(calls, 1);
assert.equal(g.send(':1.7', 0), 'stopped'); assert.equal(calls, 1);
s.focused = false; assert.equal(g.send(':1.7', 1), 'suffix_not_attempted');
assert(!g.canFallback('suffix_not_attempted'));
reset(); assert(g.cancel(':1.7')); assert.equal(g.send(':1.7',0),'stopped');
assert.equal(calls,0);
reset(); assert.equal(g.send(':1.8',0),'stopped'); assert.equal(calls,0);
reset(); s.supported = false; assert.equal(g.send(':1.7',0),'unsupported');
assert.equal(calls,0);
reset(); g.deliver=()=>{calls++;throw Error('after-side-effect');};
assert.equal(g.send(':1.7',0),'unknown'); assert.equal(calls,1);
assert(!g.canFallback('unknown')); assert.equal(g.send(':1.7',1),'stopped');
reset(); g.deliver=()=>{s.focused=false;};
// A focus switch after invocation cannot be retroactively called unsent.
assert.equal(g.send(':1.7',0),'attempted'); assert(!g.canFallback('attempted'));
reset(); s.preedit=undefined; assert.equal(g.send(':1.7',0),'busy');
assert.equal(calls,0);
console.log('10 policy scenarios passed; no desktop delivery tested');
