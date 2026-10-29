"""Real private D-Bus protocol experiment; no desktop/text transport exists."""
import asyncio,json
from dbus_next import Message,MessageType
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface,method

NAME='io.github.Creammmmm.InkEcho.IsolatedEpochModel'
PATH='/io/github/Creammmmm/InkEcho/IsolatedEpochModel'

class Model(ServiceInterface):
 def __init__(self):
  super().__init__(NAME);self.epoch=0;self.pending=False;self.cancelled=False;self.attempts=0;self.calls=0
 @method()
 def Focus(self)->'u':
  self.epoch+=1;return self.epoch
 @method()
 def Cancel(self)->'b':
  self.cancelled=True;return True
 @method()
 async def Attempt(self)->'s':
  if self.cancelled:return 'not_attempted'
  if self.pending:return 'busy'
  self.pending=True;generation=self.epoch;self.attempts+=1;self.calls+=1
  # A bounded private-protocol delay, NOT a suggested desktop wait/ACK.
  await asyncio.sleep(.05)
  self.pending=False
  if self.cancelled:return 'unknown_cancelled'
  if generation!=self.epoch:
   self.cancelled=True;return 'unknown_focus_changed'
  return 'attempted_unconfirmed'

async def run_case(case):
 server=await MessageBus().connect();client=await MessageBus().connect();model=Model();server.export(PATH,model);await server.request_name(NAME)
 async def call(member):
  r=await client.call(Message(destination=NAME,path=PATH,interface=NAME,member=member));assert r.message_type==MessageType.METHOD_RETURN;return r.body[0]
 try:
  task=asyncio.create_task(call('Attempt'))
  # Wait only for the model's local pending state so control RPC is in-flight.
  for _ in range(100):
   if model.pending:break
   await asyncio.sleep(.001)
  assert model.pending
  if case=='aba':await call('Focus');await call('Focus')
  elif case=='cancel':await call('Cancel')
  elif case=='overlap':assert await call('Attempt')=='busy'
  result=await task
  expected={'normal':'attempted_unconfirmed','aba':'unknown_focus_changed','cancel':'unknown_cancelled','overlap':'attempted_unconfirmed'}[case];assert result==expected
  if case in {'aba','cancel'}:assert await call('Attempt')=='not_attempted'
  assert model.calls==model.attempts==1
  print(json.dumps({'case':case,'result':result,'attempts':model.attempts,'focus_epoch':model.epoch,'replay_calls':0,'actual_text_transport':False}),flush=True)
 finally:client.disconnect();server.disconnect()

async def main():
 for case in ['normal','aba','cancel','overlap']:await run_case(case)
asyncio.run(main())
