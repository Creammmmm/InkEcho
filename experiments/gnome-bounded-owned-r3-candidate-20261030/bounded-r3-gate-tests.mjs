import assert from 'node:assert/strict';
import fs from 'node:fs';
import {OwnedGate} from '/home/lth/github/InkEcho/dist/gnome-bounded-owned-r3-20261030/candidate-src/inkecho/platform/ibus_owned_candidate/owned_gate.js';
import {DeliveryGateV2} from '/home/lth/github/InkEcho/dist/gnome-bounded-owned-r3-20261030/candidate-src/inkecho/platform/ibus_owned_candidate/delivery_gate.js';
let count=0;
function setup({current=async()=>'/owned',boundary=async()=>true,preedit=false}={}) {
 let now=1000,sent=0;const snap={native:true,focused:true,shellUi:false,shellPath:'/owned',preedit,epoch:1,window:1,im:{}};
 const d=new DeliveryGateV2(()=>()=>sent++,()=>true,()=>now);const g=new OwnedGate(d,()=>({...snap}),current,boundary);
 return{g,d,snap,set now(v){now=v},get sent(){return sent}};
}
{
 const t=setup();assert(t.g.beginBounded(':a',[],1,2000));assert.equal(await t.g.commitBounded(':a',0,'A',2000),'attempted');assert.equal(t.sent,1);count++;
}
{
 let resolve;const t=setup({current:()=>new Promise(r=>resolve=r)});assert(t.g.beginBounded(':a',[],1,2000));const p=t.g.commitBounded(':a',0,'A',2000);t.now=2000;resolve('/owned');assert.equal(await p,'unknown');assert.equal(t.sent,0);count++;
}
{
 let resolve;const t=setup({current:()=>new Promise(r=>resolve=r)});assert(t.g.beginBounded(':a',[],1,2000));const p=t.g.commitBounded(':a',0,'A',2000);t.g.cancel(':a');resolve('/owned');assert.equal(await p,'rejected');assert.equal(t.sent,0);count++;
}
{
 const t=setup({preedit:true});assert(t.g.beginBounded(':a',[],1,2000));assert.equal(await t.g.commitBounded(':a',0,'A',2000),'unknown');assert.equal(t.sent,0);count++;
}
{
 const t=setup();assert(t.g.beginBounded(':a',[],1,3000));assert.equal(await t.g.commitBounded(':a',0,'A',2000),'attempted');assert.equal(await t.g.commitBounded(':a',1,'B',2500),'unknown');assert.equal(t.sent,1);count++;
}
{
 const t=setup();for(const x of [NaN,Infinity,1.5,Number.MAX_SAFE_INTEGER+1,-1,1000,60_001_001])assert.equal(t.g.beginBounded(':a',[],1,x),false);assert.equal(t.sent,0);count++;
}
{
 let resolve;const t=setup({boundary:()=>new Promise(r=>resolve=r)});assert(t.g.beginBounded(':a',[],1,2000));const p=t.g.commitBounded(':a',0,'A',2000);while(!resolve)await Promise.resolve();t.now=2000;resolve(true);assert.equal(await p,'unknown');assert.equal(t.sent,1);assert.equal(await t.g.commitBounded(':a',1,'B',2000),'rejected');count++;
}
{
 // Local cancellation that the peer has not received cannot become a guarantee.
 let resolve;const t=setup({current:()=>new Promise(r=>resolve=r)});assert(t.g.beginBounded(':a',[],1,2000));const p=t.g.commitBounded(':a',0,'A',2000);const localCancelled=true;resolve('/owned');assert.equal(await p,'attempted');assert(localCancelled);assert.equal(t.sent,1);count++;
}
{
 const source=fs.readFileSync('/home/lth/github/InkEcho/dist/gnome-bounded-owned-r3-20261030/candidate-src/inkecho/platform/ibus_owned_candidate/extension.js','utf8');
 const method=source.slice(source.indexOf('    CancelAsync('),source.indexOf('    disable()'));
 const Handler=new Function('GLib','return class {'+method+'}')( {Variant:class {constructor(_type,value){this.value=value;}}} );
 let resolve;let aborts=0;const t=setup({boundary:()=>new Promise(r=>resolve=r)});
 assert(t.g.beginBounded(':a',[],1,2000));const p=t.g.commitBounded(':a',0,'A',2000);while(!resolve)await Promise.resolve();
 const h=new Handler();h._gate=t.g;h._boundaryAbort=()=>{aborts++;resolve(false)};
 function cancel(sender){let value;h.CancelAsync([], {get_sender:()=>sender,return_value:x=>value=x.value[0]});return value;}
 assert.equal(cancel(':foreign'),false);assert.equal(aborts,0);assert.equal(t.sent,1);
 resolve(true);assert.equal(await p,'attempted');t.g.ownerLost(':a');
 assert(t.g.beginBounded(':b',[],1,2000));resolve=null;const p2=t.g.commitBounded(':b',0,'B',2000);while(!resolve)await Promise.resolve();
 assert.equal(cancel(':a'),false);assert.equal(aborts,0);assert.equal(cancel(':b'),true);assert.equal(aborts,1);assert.equal(await p2,'unknown');
 assert.equal(await t.g.commitBounded(':b',1,'C',2000),'rejected');assert.equal(t.sent,2);count++;
}
{
 const source=fs.readFileSync('/home/lth/github/InkEcho/dist/gnome-bounded-owned-r3-20261030/candidate-src/inkecho/platform/ibus_owned_candidate/extension.js','utf8');
 const start=source.indexOf('    BeginAsync('),end=source.indexOf('    BeginBoundedAsync(');
 const methods=source.slice(start,end);
 const Handler=new Function('GLib','return class {'+methods+'}')( {Variant:class {constructor(_type,value){this.value=value;}}} );
 const h=new Handler();h._gate=new Proxy({}, {get(){throw new Error('legacy mutated current gate')}});
 let replies=[];const invocation={get_sender:()=>':old',return_value:x=>replies.push(x.value[0])};
 h.BeginAsync(['public-name','public-token'],invocation);h.BeginBatchAsync(['n','t',1],invocation);await h.CommitAsync([0,'A'],invocation);await h.CommitBatchAsync([0,'AB'],invocation);
 assert.deepEqual(replies,[false,false,'rejected','rejected']);count++;
}
{
 let resolve;const t=setup({current:()=>new Promise(r=>resolve=r)});assert(t.g.beginBounded(':a',[],1,2000));const p=t.g.commitBounded(':a',0,'A',2000);t.g.ownerLost(':a');resolve('/owned');assert.equal(await p,'rejected');assert.equal(t.sent,0);count++;
}
{
 let resolve;const t=setup({current:()=>new Promise(r=>resolve=r)});assert(t.g.beginBounded(':a',[],1,2000));const p=t.g.commitBounded(':a',0,'A',2000);t.g.ownerLost(':foreign');resolve('/owned');assert.equal(await p,'attempted');assert.equal(t.sent,1);count++;
}
{
 const source=fs.readFileSync('/home/lth/github/InkEcho/dist/gnome-bounded-owned-r3-20261030/candidate-src/inkecho/platform/ibus_owned_candidate/extension.js','utf8');
 const method=source.slice(source.indexOf('    disable()'),source.lastIndexOf('}'));
 const Handler=new Function('return class {'+method+'}')();
 let resolve;const t=setup({boundary:()=>new Promise(r=>resolve=r)});assert(t.g.beginBounded(':a',[],1,2000));const p=t.g.commitBounded(':a',0,'A',2000);while(!resolve)await Promise.resolve();
 const h=new Handler();h._gate=t.g;h._boundaryAbort=()=>resolve(false);h.disable();assert.equal(await p,'unknown');assert.equal(h._gate,null);assert.equal(t.sent,1);assert.equal(await t.g.commitBounded(':a',1,'B',2000),'rejected');count++;
}
console.log(JSON.stringify({passed:count,scope:'actual isolated JS service; includes expected undelivered local-cancel limitation; no IPC or client ACK'}));
