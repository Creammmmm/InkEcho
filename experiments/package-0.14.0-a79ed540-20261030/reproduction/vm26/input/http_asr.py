import asyncio,base64,hashlib,io,json,ssl,struct,subprocess,sys,tempfile,wave
from pathlib import Path
import httpx
from inkecho.config import Provider
from inkecho.providers import ProviderClient
import inkecho.providers as product
async def main():
 report={'passed':False,'synthetic_wav':True,'real_cloud':False,'module':product.__file__,'module_sha256':hashlib.sha256(Path(product.__file__).read_bytes()).hexdigest()};tasks=set();server=None;client=None
 try:
  with tempfile.TemporaryDirectory(prefix='inkecho-http-asr-') as folder:
   d=Path(folder);subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(d/'key'),' -out'.strip(),str(d/'cert'),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=IP:127.0.0.1'],check=True,capture_output=True)
   tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(d/'cert',d/'key');trust=ssl.create_default_context(cafile=str(d/'cert'))
   wav=io.BytesIO()
   with wave.open(wav,'wb') as w:w.setparams((1,2,16000,0,'NONE','none'));w.writeframes(struct.pack('<1600h',*([7000,-7000]*800)))
   audio=wav.getvalue()
   async def handler(r,w):
    tasks.add(asyncio.current_task())
    try:
     header=await r.readuntil(b'\r\n\r\n');size=next(int(x.split(b':',1)[1]) for x in header.split(b'\r\n') if x.lower().startswith(b'content-length:'));body=json.loads(await r.readexactly(size));data=body['messages'][0]['content'][0]['input_audio']['data'];assert data.startswith('data:audio/wav;base64,');assert base64.b64decode(data.split(',',1)[1])==audio;report['wire_wav_exact']=True;report['request_path']=header.split(b'\r\n',1)[0].decode();reply=json.dumps({'choices':[{'message':{'content':'你好，HTTP Ω 😀。'}}]}).encode();w.write(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n'+f'Content-Length: {len(reply)}\r\n\r\n'.encode()+reply);await w.drain()
    finally:
     w.close()
     try:await asyncio.wait_for(w.wait_closed(),1)
     except (TimeoutError,ConnectionError):w.transport.abort()
     tasks.discard(asyncio.current_task())
   server=await asyncio.start_server(handler,'127.0.0.1',0,ssl=tls);port=server.sockets[0].getsockname()[1];client=httpx.AsyncClient(verify=trust,trust_env=False);provider=Provider('http-probe','Local HTTP ASR','transcription','qwen',base_url=f'https://127.0.0.1:{port}/v1',model='qwen3-asr-flash');result=await ProviderClient(http=client).transcribe(provider,'synthetic-local-key',audio);assert result.text=='你好，HTTP Ω 😀。';report.update(passed=True,returned_codepoints=[ord(c) for c in result.text])
 except Exception as e:report['error']=type(e).__name__+':'+str(e)
 finally:
  if client:await client.aclose()
  if server:server.close();await server.wait_closed()
  if tasks:await asyncio.gather(*tasks)
  report['server_handlers_remaining']=len(tasks);Path(sys.argv[1]).write_text(json.dumps(report,indent=2));print(json.dumps(report))
 return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
