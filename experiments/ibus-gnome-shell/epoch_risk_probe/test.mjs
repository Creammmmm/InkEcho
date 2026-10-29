import assert from 'node:assert/strict';
import {EpochPolicy} from './policy.mjs';
let p,t;
function fresh(){p=new EpochPolicy();t=p.begin();assert(t);}
fresh();assert(p.attempted(t));assert.equal(p.finish(t),'attempted_unconfirmed');
fresh();assert(p.attempted(t));p.focusChanged();assert.equal(p.finish(t),'unknown_focus_changed');assert.equal(p.begin(),null);
fresh();const finalSameTarget=true;assert(p.attempted(t));p.focusChanged();p.focusChanged();assert(finalSameTarget);assert.equal(p.finish(t),'unknown_focus_changed');
fresh();p.cancel();assert(!p.attempted(t));assert.equal(p.attempts,0);assert.equal(p.finish(t),'not_attempted');assert.equal(p.begin(),null);
fresh();assert(p.attempted(t));p.cancel();assert.equal(p.finish(t),'unknown_cancelled');assert.equal(p.attempts,1);
fresh();assert.equal(p.begin(),null);assert.equal(p.finish({}),'stale');assert.strictEqual(p.pending,t);
fresh();assert(p.attempted(t));assert.equal(p.finish(t),'attempted_unconfirmed');const next=p.begin();assert(next);assert.equal(p.finish(t),'stale');assert.strictEqual(p.pending,next);
// Conservative false positive: a focus event does not prove the character lost.
fresh();assert(p.attempted(t));const actualReceived=true;p.focusChanged();assert(actualReceived);assert.equal(p.finish(t),'unknown_focus_changed');
console.log('8 epoch policy cases passed; no compositor delivery tested');
