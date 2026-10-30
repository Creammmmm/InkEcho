import assert from 'node:assert/strict';
import fs from 'node:fs';
const {OwnedGate}=await import(new URL('../../src/inkecho/platform/ibus_owned_candidate/owned_gate.js',import.meta.url));
const {DeliveryGateV2}=await import(new URL('../../src/inkecho/platform/ibus_owned_candidate/delivery_gate.js',import.meta.url));
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
 const source=fs.readFileSync(new URL('../../src/inkecho/platform/ibus_owned_candidate/extension.js',import.meta.url),'utf8');
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
 const source=fs.readFileSync(new URL('../../src/inkecho/platform/ibus_owned_candidate/extension.js',import.meta.url),'utf8');
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
 const source=fs.readFileSync(new URL('../../src/inkecho/platform/ibus_owned_candidate/extension.js',import.meta.url),'utf8');
 const method=source.slice(source.indexOf('    disable()'),source.lastIndexOf('}'));
 const Handler=new Function('return class {'+method+'}')();
 let resolve;const t=setup({boundary:()=>new Promise(r=>resolve=r)});assert(t.g.beginBounded(':a',[],1,2000));const p=t.g.commitBounded(':a',0,'A',2000);while(!resolve)await Promise.resolve();
 const h=new Handler();h._gate=t.g;h._boundaryAbort=()=>resolve(false);h.disable();assert.equal(await p,'unknown');assert.equal(h._gate,null);assert.equal(t.sent,1);assert.equal(await t.g.commitBounded(':a',1,'B',2000),'rejected');count++;
}
{
 // V2 retains one immutable task bound while each dispatch has a fresh short bound.
 const t=setup();assert(t.g.beginBounded(':a',[],2,200000000));
 assert.equal(await t.g.commit(':a',0,'A',true),'rejected');
 assert.equal(t.d.commitBatch(':a',0,'A'),'rejected');
 assert.equal(await t.g.commitBounded(':a',0,'A',3001000),'attempted');
 t.now=61001000;
 assert.equal(await t.g.commitBounded(':a',1,'B',64001000),'attempted');
 assert.equal(t.sent,2);
 assert.equal(await t.g.commitBounded(':a',2,'C',200000001),'unknown');
 assert.equal(t.sent,2);count++;
}
{
 let resolve;const t=setup({current:()=>new Promise(r=>resolve=r)});
 assert(t.g.beginBounded(':a',[],2,10000000));
 const p=t.g.commitBounded(':a',0,'A',3001000);t.now=3001000;resolve('/owned');
 assert.equal(await p,'unknown');assert.equal(t.sent,0);
 assert.equal(await t.g.commitBounded(':a',0,'A',4001000),'rejected');count++;
}
{
 // Verify the actual externally exported handlers bind their protocol version.
 const source=fs.readFileSync(new URL('../../src/inkecho/platform/ibus_owned_candidate/extension.js',import.meta.url),'utf8');
 const method=source.slice(source.indexOf('    BeginBoundedAsync('),source.indexOf('    CancelAsync('));
 const Handler=new Function('GLib','return class {'+method+'}')({Variant:class {constructor(_type,value){this.value=value;}}});
 const t=setup(),h=new Handler();h._gate=t.g;
 function invocation(){let value;return {get_sender:()=>':a',return_value:x=>value=x.value[0],get value(){return value}};}
 let x=invocation();h.BeginBoundedAsync(['n','t',2,10000000],x);assert.equal(x.value,false);
 x=invocation();h.BeginLongBoundedAsync(['n','t',1,10000000],x);assert.equal(x.value,false);
 x=invocation();h.BeginLongBoundedAsync(['n','t',2,10000000],x);assert.equal(x.value,true);
 x=invocation();await h.CommitBoundedAsync([0,'A',2000],x);assert.equal(x.value,'rejected');assert.equal(t.sent,0);
 x=invocation();await h.CommitLongBoundedAsync([0,'A',2000],x);assert.equal(x.value,'attempted');assert.equal(t.sent,1);count++;
}
{
 // A concurrent call must not replace the current request deadline.
 let release;const t=setup({current:()=>new Promise(r=>release=r)});
 assert(t.g.beginBounded(':a',[],2,10000000));
 const first=t.g.commitBounded(':a',0,'A',2000);
 assert.equal(await t.g.commitBounded(':a',0,'B',3000),'rejected');
 assert.equal(t.d.session.requestDeadlineUs,2000);
 t.now=2000;release('/owned');assert.equal(await first,'unknown');assert.equal(t.sent,0);count++;
}
{
 // Simulate another request entering after inner pending clears but before
 // the first wrapper resumes its finally microtask.
 let secondRelease,second,firstCall=true;const t=setup({current:()=>firstCall ? (firstCall=false,Promise.resolve('/owned')) : new Promise(r=>secondRelease=r)});
 assert(t.g.beginBounded(':a',[],2,10000000));
 const original=t.g.commit.bind(t.g);
 t.g.commit=(...args)=>{const p=original(...args);if (!second) p.then(()=>{second=t.g.commitBounded(':a',1,'B',3000)});return p;};
 assert.equal(await t.g.commitBounded(':a',0,'A',2000),'attempted');
 assert(second && secondRelease);assert.equal(t.d.session.requestDeadlineUs,3000);
 t.now=3000;secondRelease('/owned');assert.equal(await second,'unknown');assert.equal(t.sent,1);count++;
}
console.log(JSON.stringify({passed:count,scope:'actual isolated JS service; includes expected undelivered local-cancel limitation; no IPC or client ACK'}));
