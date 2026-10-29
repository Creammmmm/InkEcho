import assert from 'node:assert/strict';
import {DeliveryGateV2} from './gate.mjs';
let mode='none',calls=0,cap='ok';
const gate=new DeliveryGateV2(()=>{if(mode==='error')throw Error('resolve');if(mode==='none')return null;return ()=>{calls++;if(mode==='throw')throw Error('dispatch');};},token=>{if(token!==cap)return false;cap='';return true;});
assert.equal(gate.begin(':1','bad'),false);assert.equal(gate.begin(':1','ok'),true);
assert.equal(gate.commit(':2',0,'甲'),'rejected');assert.equal(gate.commit(':1',0,'甲'),'no_service');assert.equal(calls,0);assert.equal(gate.commit(':1',0,'甲'),'rejected');assert.equal(gate.cancel(':1'),true);
cap='next';mode='real';assert.equal(gate.begin(':2','next'),true);assert.equal(gate.commit(':2',0,'甲'),'attempted');mode='none';assert.equal(gate.commit(':2',1,'乙'),'unknown');assert.equal(calls,1);assert.equal(gate.cancel(':2'),true);
cap='last';mode='throw';assert.equal(gate.begin(':3','last'),true);assert.equal(gate.commit(':3',0,'丙'),'unknown');assert.equal(calls,2);assert.equal(gate.commit(':3',0,'丙'),'rejected');assert.equal(gate.cancel(':3'),true);assert.equal(gate.commit(':3',0,'丁'),'rejected');
console.log('gate pre-dispatch, authentication, partial prefix, exceptions, cancellation passed');
