import asyncio
import importlib.util
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from types import SimpleNamespace
import shutil
import pytest
import inkecho.platform
root=Path('/tmp/inkecho-owned-default/files/src/inkecho/platform')
inkecho.platform.__path__=[str(root),*inkecho.platform.__path__]
from inkecho.platform.owned_installation import FILES,UUID,installation_state,verified_installation
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.output_router import OutputRouterError
from inkecho.platform.owned_extension import OwnedExtensionManager

def installed(tmp_path):
 path=tmp_path/'assets';shutil.copytree(root/'ibus_owned_candidate',path,ignore=shutil.ignore_patterns('__pycache__'));path.chmod(0o755)
 for name in FILES:(path/name).chmod(0o644)
 return path

def test_absent_does_not_launch_gsettings(tmp_path):
 async def command(*args):raise AssertionError('must not spawn')
 assert asyncio.run(installation_state(root=tmp_path/'absent',command=command))=='absent'
@pytest.mark.parametrize('change',['modified','missing','writable','symlink','directorysymlink','fifo'])
def test_installed_damage_never_absent(tmp_path,change):
 path=installed(tmp_path);file=path/'probe.js'
 if change=='fifo':
  import os
  file.unlink();os.mkfifo(file)
 if change=='modified':file.write_text(file.read_text()+'x')
 if change=='missing':file.unlink()
 if change=='writable':file.chmod(0o666)
 if change=='symlink':file.unlink();file.symlink_to(path/'extension.js')
 if change=='directorysymlink':alias=tmp_path/'alias';alias.symlink_to(path,target_is_directory=True);path=alias
 with pytest.raises(OutputRouterError,match='input_capability_unknown'):verified_installation(path)
@pytest.mark.parametrize('value,expected',[("@as []",'disabled'),(repr([UUID]),'enabled')])
def test_enabled_is_separate_from_file_presence(tmp_path,value,expected):
 path=installed(tmp_path)
 async def command(*args):return value if args[-1]=="enabled-extensions" else "[]" if args[-1]=="disabled-extensions" else "false"
 assert asyncio.run(installation_state(root=path,command=command))==expected
@pytest.mark.parametrize('value',["broken",'{"not":"list"}',"['']"])
def test_bad_settings_not_disabled(tmp_path,value):
 path=installed(tmp_path)
 async def command(*args):return value
 with pytest.raises(OutputRouterError):asyncio.run(installation_state(root=path,command=command))

class Keyboard:
 def __init__(self):self.authorized=True;self.sent=[];self.connects=0;self.scopes=0
 async def connect(self):self.connects+=1
 @asynccontextmanager
 async def output_session(self):
  self.scopes+=1
  try:yield
  finally:self.scopes-=1
 async def insert(self,text,active,**kwargs):assert active();self.sent.append(text);return len(text)
 async def aclose(self):pass
class Bridge:
 def __init__(self):self.sent=[];self.owner=None
 async def connect(self,**kwargs):self.owner=kwargs.get('expected_owner')
 async def insert(self,text,active,**kwargs):assert active();self.sent.append(text);return len(text)
 async def aclose(self):pass
async def no_fcitx():return None
async def state_enabled():return 'enabled'
async def own():return ('ibus',':1.17')

def test_absent_preserves_old_auto_and_does_not_probe_owned():
 async def run():
  async def absent():return 'absent'
  async def never():raise AssertionError('owned must not be queried')
  k=Keyboard();r=DefaultAutoOutputRouter(k,state_probe=absent,system_detector=no_fcitx,owned_probe=never)
  await r.prepare_task('auto');assert not k.sent
  async with r.output_session():assert await r.insert('甲',lambda:True)==1
  assert k.sent==['甲'] and k.scopes==0
 asyncio.run(run())
def test_enabled_selects_owned_with_pinned_owner():
 async def run():
  k,b=Keyboard(),Bridge();r=DefaultAutoOutputRouter(k,state_probe=state_enabled,system_detector=no_fcitx,owned_probe=own,owned_factory=lambda:b)
  await r.prepare_task('auto')
  with pytest.raises(OutputRouterError,match='ibus_delivery_unknown'):
   async with r.output_session():assert await r.insert('甲',lambda:True)==1
  assert b.sent==['甲'] and b.owner==':1.17' and k.sent==[]
 asyncio.run(run())
def test_corrupt_installation_fails_closed_without_fcitx():
 async def run():
  async def corrupt():raise OutputRouterError('input_capability_unknown')
  k=Keyboard();r=DefaultAutoOutputRouter(k,state_probe=corrupt,system_detector=no_fcitx)
  await r.prepare_task('auto')
  with pytest.raises(OutputRouterError,match='input_capability_unknown'):
   async with r.output_session():await r.insert('甲',lambda:True)
  assert k.sent==[] and k.connects==0
 asyncio.run(run())
def test_trusted_fcitx_has_priority_even_if_optional_ibus_corrupt():
 async def run():
  async def corrupt():raise OutputRouterError('input_capability_unknown')
  async def fcitx():return ('fcitx',':1.8')
  async def never():raise AssertionError('must not query owned')
  k,b=Keyboard(),Bridge();r=DefaultAutoOutputRouter(k,state_probe=corrupt,system_detector=fcitx,owned_probe=never,bridge_factory=lambda:b)
  await r.prepare_task('auto')
  async with r.output_session():assert await r.insert('甲',lambda:True)==1
  assert b.owner==':1.8' and b.sent==['甲'] and k.sent==[]
 asyncio.run(run())
def test_explicit_ibus_stays_legacy_and_bypasses_optional_guard():
 async def run():
  async def never():raise AssertionError('no auto guard')
  k,b=Keyboard(),Bridge();r=DefaultAutoOutputRouter(k,state_probe=never,legacy_factory=lambda:b)
  await r.prepare_task('ibus')
  with pytest.raises(OutputRouterError,match='ibus_delivery_unknown'):
   async with r.output_session():await r.insert('甲',lambda:True)
  assert b.sent==['甲']
 asyncio.run(run())
def test_cancel_while_guarding_does_not_send():
 async def run():
  active=True
  async def stopped():
   nonlocal active
   active=False;return 'enabled'
  k=Keyboard();r=DefaultAutoOutputRouter(k,state_probe=stopped)
  await r.prepare_task('auto')
  with pytest.raises(OutputRouterError,match='input_cancelled'):
   async with r.output_session():await r.insert('甲',lambda:active)
  assert k.sent==[] and k.connects==0
 asyncio.run(run())
def test_installer_never_enables_implicitly():
 import zipfile
 calls=[]
 def runner(args,**kwargs):
  calls.append(args[1])
  with zipfile.ZipFile(args[2]) as archive:assert set(archive.namelist())==set(FILES)
  return SimpleNamespace(returncode=0,stdout='')
 OwnedExtensionManager(runner=runner).install()
 assert calls==['install']

def test_fcitx_lost_under_corrupt_install_never_sends_fallback():
 async def run():
  async def corrupt():raise OutputRouterError('input_capability_unknown')
  count=0
  async def changed():
   nonlocal count
   count+=1;return ('fcitx',':1.8') if count==1 else None
  k=Keyboard();r=DefaultAutoOutputRouter(k,state_probe=corrupt,system_detector=changed)
  await r.prepare_task('auto')
  with pytest.raises(OutputRouterError,match='input_capability_unknown'):
   async with r.output_session():await r.insert('甲',lambda:True)
  assert not k.sent and k.scopes==0
 asyncio.run(run())

def test_actual_app_import_uses_default_router(tmp_path,monkeypatch):
 spec=importlib.util.spec_from_file_location('owned_default_app_candidate',root.parent/'app.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 assert module.OutputRouter is DefaultAutoOutputRouter
 from inkecho.config import ConfigStore
 keyboard=Keyboard();monkeypatch.setattr(module,'keyboard_for_desktop',lambda:keyboard)
 session=module.Session(store=ConfigStore(tmp_path/'actual-session'))
 assert type(session.inputs) is DefaultAutoOutputRouter
 assert session.inputs.keyboard is keyboard
 assert session.settings.output_method=='auto'
 asyncio.run(session.close())

@pytest.mark.parametrize('disabled,global_disabled',[(repr([UUID]),'false'),('[]','true'),(repr([UUID]),'true')])
def test_legitimate_disable_overrides_enabled(tmp_path,disabled,global_disabled):
 path=installed(tmp_path)
 async def command(*args):return {'enabled-extensions':repr([UUID]),'disabled-extensions':disabled,'disable-user-extensions':global_disabled}[args[-1]]
 assert asyncio.run(installation_state(root=path,command=command))=='disabled'
@pytest.mark.parametrize('key,value',[('disabled-extensions','?'),('disabled-extensions','[1]'),('disable-user-extensions','unknown'),('disable-user-extensions','False')])
def test_unknown_disable_values_fail_closed(tmp_path,key,value):
 path=installed(tmp_path)
 async def command(*args):return value if args[-1]==key else {'enabled-extensions':repr([UUID]),'disabled-extensions':'[]','disable-user-extensions':'false'}[args[-1]]
 with pytest.raises(OutputRouterError,match='input_capability_unknown'):asyncio.run(installation_state(root=path,command=command))
@pytest.mark.parametrize('changed',['enabled-extensions','disabled-extensions','disable-user-extensions','assets'])
def test_state_change_during_snapshot_is_unknown(tmp_path,changed):
 path=installed(tmp_path);counts={}
 async def command(*args):
  key=args[-1];counts[key]=counts.get(key,0)+1
  if changed=='assets' and key=='disable-user-extensions' and counts[key]==2:(path/'probe.js').unlink()
  if counts[key]==2 and key==changed:return {'enabled-extensions':'[]','disabled-extensions':repr([UUID]),'disable-user-extensions':'true'}[key]
  return {'enabled-extensions':repr([UUID]),'disabled-extensions':'[]','disable-user-extensions':'false'}[key]
 with pytest.raises(OutputRouterError,match='input_capability_unknown'):asyncio.run(installation_state(root=path,command=command))

def test_disabled_default_uses_legacy_keyboard_without_owned_probe():
 async def run():
  async def disabled():return 'disabled'
  async def never():raise AssertionError('must not query disabled bridge')
  k=Keyboard();r=DefaultAutoOutputRouter(k,state_probe=disabled,system_detector=no_fcitx,owned_probe=never)
  await r.prepare_task('auto')
  async with r.output_session():assert await r.insert('甲',lambda:True)==1
  assert k.sent==['甲']
 asyncio.run(run())

def test_installer_child_umask_makes_uuid_directory_private(tmp_path):
 import os,subprocess,stat
 calls=[]
 def runner(args,**kwargs):
  calls.append(kwargs.get('umask'))
  if args[1]=='install':
   target=tmp_path/'installed-dir'
   return subprocess.run([sys.executable,'-c','import os,sys; os.mkdir(sys.argv[1],0o777)',str(target)],**kwargs)
  return SimpleNamespace(returncode=0,stdout='')
 manager=OwnedExtensionManager(runner=runner);manager.install()
 assert stat.S_IMODE((tmp_path/'installed-dir').stat().st_mode)==0o700
 manager.disable();assert calls==[0o077,None]


@pytest.mark.parametrize('state',['unknown','enabled','absent','disabled'])
@pytest.mark.parametrize('code',['no_target','ambiguous_target'])
def test_fcitx_insert_rejection_respects_owned_uncertainty(state,code):
 from inkecho.platform.fcitx5 import FcitxOutputError
 async def run():
  async def probe():return state
  async def fcitx():return ('fcitx',':1.8')
  class Reject(Bridge):
   async def insert(self,text,active,**kwargs):raise FcitxOutputError(code,unsent_offset=0)
  k=Keyboard();r=DefaultAutoOutputRouter(k,state_probe=probe,system_detector=fcitx,bridge_factory=Reject)
  await r.prepare_task('auto')
  if state in {'absent','disabled'}:
   async with r.output_session():assert await r.insert('甲',lambda:True)==1
  else:
   with pytest.raises(OutputRouterError,match='fcitx_'+code):
    async with r.output_session():await r.insert('甲',lambda:True)
  assert k.sent==(['甲'] if state in {'absent','disabled'} else [])
 asyncio.run(run())

@pytest.mark.parametrize('case',['accepted','uncertain','cancel','owner_changed','cross_fragment'])
def test_unknown_owned_fcitx_failure_never_replays(case):
 from inkecho.platform.fcitx5 import FcitxOutputError
 async def run():
  active=True
  async def probe():return 'unknown'
  async def fcitx():return ('fcitx',':1.8')
  class Reject(Bridge):
   calls=0
   async def insert(self,text,check,**kwargs):
    nonlocal active
    self.calls+=1
    if case=='cross_fragment' and self.calls==1:self.sent.append(text);return len(text)
    if case=='cancel':active=False
    raise FcitxOutputError('owner_changed' if case=='owner_changed' else 'no_target',accepted=1 if case=='accepted' else 0,uncertain=case=='uncertain',unsent_offset=0)
  k=Keyboard();b=Reject();r=DefaultAutoOutputRouter(k,state_probe=probe,system_detector=fcitx,bridge_factory=lambda:b)
  await r.prepare_task('auto')
  with pytest.raises(OutputRouterError):
   async with r.output_session():
    if case=='cross_fragment':assert await r.insert('甲',lambda:active)==1
    await r.insert('乙',lambda:active)
  assert not k.sent and k.connects==0
  assert b.sent==(['甲'] if case=='cross_fragment' else [])
 asyncio.run(run())
