"""Isolated actual Session orchestration with a synthetic local producer only."""
import asyncio,time
from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QApplication
_APP=QApplication.instance() or QApplication([])
from inkecho.config import ConfigStore,Provider
from inkecho.providers import Result,Usage
import inkecho.app as app
class Recorder(QObject):
 level=Signal(float);finished=Signal(bytes,float);failed=Signal(str)
 def start(self,*a,**kw):return True
 def stop(self):self.finished.emit(b'synthetic-not-audio',1)
 def cancel(self):pass
async def probe(router, sample, root, *, case, before_produce=lambda:None, output_method='auto'):
 chunks=list(sample);deltas=[];session=None
 class Client:
  async def transcribe(self,*a):return Result(sample,Usage(),0)
  async def polish(self,*a):return Result(sample,Usage(),0)
  async def polish_stream(self,*a):
   if case=='original-fallback':
    from inkecho.providers import ProviderError
    raise ProviderError('network')
   before_produce()
   for index,c in enumerate(chunks):
    await a[-1](c);deltas.append({'index':index,'monotonic':time.monotonic()});await asyncio.sleep(.025)
    if case=='pending-cancel' and index==1:session.cancel();await asyncio.sleep(0)
   return Result(sample,Usage(),0)
 store=ConfigStore(root);store.initialize()
 for p in [Provider('qwen','Synthetic ASR','transcription','qwen','https://example.invalid','','provider/qwen'),Provider('deepseek','Synthetic polish','polishing','openai','https://example.invalid','','provider/deepseek')]:store.save_provider(replace(p,model='synthetic-model'))
 store.save_settings(replace(store.load_settings(),transcription_provider='qwen',polishing_provider='deepseek',polishing_enabled=True,polishing_fallback=case=='original-fallback',polishing_streaming=case!='synchronous',output_method=output_method))
 session=app.Session(store,inputs=router,recorder=Recorder(),client=Client());out=[];session.finished.connect(out.append)
 async def key(_):return 'synthetic-not-a-real-key'
 session.key=key;orig=router.insert;calls=[]
 async def inserted(text,active,**kw):
  entry={'length':len(text),'has_lf':'\n'in text,'at':time.monotonic(),'route_before':router.selected};calls.append(entry);first=kw.get('on_first_sent')
  def sent(at=None):
   entry['first_sent_at']=at
   if first:first(at)
   if case=='cancel':session.cancel()
  kw['on_first_sent']=sent
  try:return await orig(text,active,**kw)
  except BaseException as error:
   entry['error_code']=getattr(error,'code',None);entry['error_type']=type(error).__name__;raise
  finally:
   entry['protocol']=getattr(router._selected,'_protocol',None);entry['route_after']=router.selected;entry['backend_type']=type(router._selected).__name__;entry['native_attempts']=getattr(router._selected,'_accepted',None)
 router.insert=inserted
 try:
  await session.toggle();session.stop_recording()
  async def done():
   while session.pending:await asyncio.sleep(.002)
  await asyncio.wait_for(done(),15)
  return {'route':router.selected,'outcome':str(session.controller.outcome),'metrics_characters':session.metrics.get('characters'),'reported_characters':out[-1].get('characters') if out else None,'outcomes':[{'characters':x.get('characters')}for x in out],'deltas':deltas,'dispatches':calls,'input_failure':next((d.get('error_code')for d in reversed(calls)if d.get('error_code')),getattr(session.input_failure,'code',None)),'error_code':getattr(getattr(session.controller,'failure',None),'code',None)}
 finally:await session.close()
