"""One private bus and two owned real GTK clients; explicit root-approved send gate."""
import asyncio,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('/tmp/inkecho-fcitx-v2');WORK=Path('/tmp/inkecho-fcitx-v2-desktop-run-r2')
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'deps')]
from dbus_next import Message,MessageType
from dbus_next.aio import MessageBus
from inkecho.platform.fcitx5 import Fcitx5Bridge,FcitxOutputError
WORK.mkdir(mode=0o700,exist_ok=False)
for name in ['data/fcitx5/addon','config','home']:(WORK/name).mkdir(mode=0o700,parents=True,exist_ok=True)
for k,v in {'HOME':WORK/'home','XDG_CONFIG_HOME':WORK/'config','XDG_DATA_HOME':WORK/'data'}.items():os.environ[k]=str(v)
conf=(ROOT/'product-native-build/inkecho.conf').read_text().replace('Library=libinkecho','Library='+str(ROOT/'product-native-build/libinkecho'))
(WORK/'data/fcitx5/addon/inkecho.conf').write_text(conf)
log=(WORK/'fcitx.log').open('xb');daemon=subprocess.Popen(['/usr/bin/fcitx5','-D','--keep','--disable=wayland,xcb,notificationitem,classicui,clipboard'],stdout=log,stderr=subprocess.STDOUT)
targets=[];report={'scope':'actual GTK fcitx frontend/private bus; fixed owned controls only','passed':False,'checks':[],'environment':{k:os.environ.get(k) for k in ['DISPLAY','WAYLAND_DISPLAY','XDG_SESSION_TYPE','XDG_RUNTIME_DIR']},'daemon_pid':daemon.pid}
async def waitfor(path,seconds=8):
    end=time.monotonic()+seconds
    while not path.exists():
        assert time.monotonic()<end, str(path);await asyncio.sleep(.025)
    return json.loads(path.read_text()) if path.suffix=='.json' else path.read_text()
async def run():
    bus=await MessageBus().connect();owner=None
    async def raw(dest,path,interface,member,sig='',body=[]):
        reply=await asyncio.wait_for(bus.call(Message(destination=dest,path=path,interface=interface,member=member,signature=sig,body=body)),2)
        assert reply.message_type==MessageType.METHOD_RETURN,(member,reply.error_name);return reply.body
    try:
        for _ in range(100):
            try:owner=(await raw('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetNameOwner','s',['org.fcitx.Fcitx5']))[0];break
            except AssertionError:await asyncio.sleep(.05)
        assert owner
        for role in ['A','B']:
            env=os.environ.copy();env['GTK_IM_MODULE']='fcitx';env['GDK_BACKEND']='x11'
            p=subprocess.Popen(['/usr/bin/python3','/tmp/inkecho-fcitx-v2-desktop/target.py',str(WORK/role)],env=env,stdout=(WORK/(role+'.log')).open('xb'),stderr=subprocess.STDOUT)
            targets.append((role,p));ready=await waitfor(WORK/role/'ready.json');assert ready['pid']==p.pid and ready['module']=='fcitx' and ready['fcitx_module_loaded'];report[role]=ready
        (WORK/'ready.json').write_text(json.dumps(report,indent=2))
        await waitfor(WORK/'approve',180)
        for role,p in targets:
            r=report[role];assert p.poll() is None and time.monotonic()+15<r['expires_at'];assert Path('/proc',str(p.pid),'stat').read_text().split(') ',1)[1].split()[19]==r['start']
        async def activate(role):
            r=report[role];assert r['xid']
            subprocess.run(['xdotool','windowactivate','--sync',str(r['xid'])],check=True,timeout=3)
            assert int(subprocess.check_output(['xdotool','getactivewindow']))==r['xid'];await asyncio.sleep(.15)
        async def text(role):return (await waitfor(WORK/role/'text.json'))['text']
        bridge=Fcitx5Bridge();await bridge.connect(expected_owner=owner);assert bridge._detailed_focus
        for role,value in [('A','甲'),('B','乙'),('A','丙丁')]:
            await activate(role);assert await bridge.insert(value,lambda:True,deadline=time.monotonic()+3)==len(value)
            await asyncio.sleep(.15)
        await bridge.aclose()
        actual=[await text('A'),await text('B')];assert actual==['甲丙丁','乙'],actual
        report['checks'].append({'name':'actual_A_B_A_same_task','actual':actual,'exact':True})
        await activate('A');client=Fcitx5Bridge();await client.connect(expected_owner=owner);active=True
        def first(_):
            nonlocal active
            active=False;report['cancel_at']=time.monotonic()
        try:
            await client.insert('戊己庚',lambda:active,deadline=time.monotonic()+3,on_first_sent=first)
            raise AssertionError('cancel did not stop')
        except FcitxOutputError as error:
            assert error.code=='cancelled';report['cancel_error']=error.code
        await client.aclose();await asyncio.sleep(1.25)
        actual=[await text('A'),await text('B')];assert actual==['甲丙丁戊','乙'],actual
        report['checks'].append({'name':'actual_cancel_first_prefix','actual':actual,'tail_seconds':time.monotonic()-report['cancel_at'],'exact':True})
        report['delivery_checks_passed']=True
    finally:
        for role,p in targets:(WORK/role/'stop').touch()
        for role,p in targets:
            try:report[role+'_original_wait']=await asyncio.to_thread(p.wait,5)
            except subprocess.TimeoutExpired:report[role+'_wait_timeout']=True
        if owner:
            try:report['exit_reply']=await raw(owner,'/controller','org.fcitx.Fcitx.Controller1','Exit')
            except Exception as e:report['exit_error']=type(e).__name__
        bus.disconnect()
        try:report['daemon_original_wait']=await asyncio.to_thread(daemon.wait,5)
        except subprocess.TimeoutExpired:report['daemon_wait_timeout']=True
        report['passed']=report.get('delivery_checks_passed',False) and all(report.get(role+'_original_wait')==0 for role,_ in targets) and report.get('daemon_original_wait')==0
        (WORK/'result.json').write_text(json.dumps(report,indent=2));log.close()
try:asyncio.run(run())
except Exception as error:
    report['error_type']=type(error).__name__;report['error']=str(error);(WORK/'result.json').write_text(json.dumps(report,indent=2));raise
