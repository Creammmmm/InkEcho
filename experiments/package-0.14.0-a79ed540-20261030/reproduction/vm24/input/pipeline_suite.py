import os,json,subprocess,asyncio
from pathlib import Path
async def run_suite(py,appdir,actor_env,record):
 for case in ['normal','cancel-after-first']:
  folder=Path('/mnt/output')/os.environ.get('INKECHO_OUTPUT_STAGE','default')/('fcitx-pipeline-'+case);folder.mkdir(mode=0o700);target_env=dict(actor_env);target_env['INKECHO_PIPELINE_ROOT']=str(folder)
  target=subprocess.Popen(['/usr/bin/python3','/mnt/input/target.py'],env=target_env,stdout=(folder/'target.log').open('w'),stderr=subprocess.STDOUT)
  try:
   await asyncio.sleep(.4)
   ids=subprocess.check_output(['xdotool','search','--all','--onlyvisible','--pid',str(target.pid),'--name','^InkEcho candidate owned protocol target$'],env=target_env,text=True).split();assert len(ids)==1,ids
   subprocess.run(['xdotool','windowactivate','--sync',ids[0]],env=target_env,check=True,timeout=5)
   row={}
   for _ in range(100):
    if (folder/'target.json').exists():
     row=json.loads((folder/'target.json').read_text())
     if row['active'] and row['focused']:break
    await asyncio.sleep(.1)
   assert row.get('active') and row.get('focused') and row['text']=='',row
   pe=dict(os.environ);pe.update(INKECHO_EXPECTED_BACKEND='fcitx',GDK_BACKEND='x11',QT_QPA_PLATFORM='offscreen')
   with(folder/'pipeline.log').open('w')as log:r=subprocess.run([py,'/mnt/input/pipeline_receiver_cancel.py','--package-root',str(appdir/'packages'),'--output',str(folder/'report.json'),'--backend','auto','--case',case],env=pe,stdout=log,stderr=subprocess.STDOUT,timeout=70)
   first=json.loads((folder/'target.json').read_text());await asyncio.sleep(1.3);last=json.loads((folder/'target.json').read_text());sample='你好 InkEcho，café Ω\n第二行。'
   ok=last['text']==sample if case=='normal' else bool(last['text']) and len(last['text'])<len(sample) and sample.startswith(last['text'])
   result={'mode':case,'pipeline_exit':r.returncode,'text_exact_or_partial_prefix':ok,'no_late_text':first['text']==last['text'],'old_target_untouched':last['window_count']==2 and last['first_text']=='','received_codepoints':[ord(c)for c in last['text']]};(folder/'receiver.json').write_text(json.dumps(result,indent=2));record('actual_pipeline',**result);assert r.returncode==0 and ok and result['no_late_text'] and result['old_target_untouched'],result
  finally:
   if target.poll()is None:target.terminate()
   record('pipeline_target_exit',mode=case,exit=target.wait(timeout=5))
