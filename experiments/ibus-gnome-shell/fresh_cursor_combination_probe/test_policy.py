import copy
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('policy_r2',Path(__file__).with_name('policy.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def sample():
 return {'live':True,'pid':15,'path':'/org/freedesktop/IBus/InputContext_3','epoch':4,'focusAt':20,'preedit':False,'scale':1,'cursor':{'kind':'set-cursor-location-relative','epoch':4,'at':21,'raw':[35,61,0,32]}},{'pid':15,'focused':True,'editable':True,'text_interface':True,'window':[26,60,329,34]}

def test_fresh_relative_focus_context_and_widget_combination():
 p,t=sample();assert m.verdict(p,t,p['path'])=='candidate_only'

def test_missing_fresh_cursor_cannot_reuse_previous_geometry():
 p,t=sample();p['cursor']=None;assert m.verdict(p,t,p['path'])=='unknown'

def test_old_generation_or_pre_focus_cursor_rejected():
 for key,value in [('epoch',3),('at',19)]:
  p,t=sample();p['cursor'][key]=value;assert m.verdict(p,t,p['path'])=='unknown'

def test_other_context_or_other_app_rejected():
 p,t=sample();assert m.verdict(p,t,'/different')=='unknown'
 t['pid']=16;assert m.verdict(p,t,p['path'])=='unknown'

def test_button_rejected_even_when_stale_context_still_exists():
 p,t=sample();t['editable']=False;t['text_interface']=False;assert m.verdict(p,t,p['path'])=='unsupported'

def test_preedit_busy_or_unknown_never_eligible():
 for value in [True,None]:
  p,t=sample();p['preedit']=value;assert m.verdict(p,t,p['path'])=='busy_or_unknown'

def test_unvalidated_coordinate_space_is_unknown_not_guessed():
 p,t=sample();p['scale']=2;assert m.verdict(p,t,p['path'])=='unknown_coordinate_space'
 p['scale']=1;p['cursor']['kind']='set-cursor-location';assert m.verdict(p,t,p['path'])=='unknown_coordinate_space'

def test_outside_widget_geometry_rejected():
 p,t=sample();p['cursor']['raw']=[900,900,0,20];assert m.verdict(p,t,p['path'])=='geometry_mismatch'

def test_documented_foreign_context_geometry_limit_is_not_hidden():
 # Geometry is not authentication: identical metadata cannot distinguish origin.
 p,t=sample();p['path']='/org/freedesktop/IBus/InputContext_foreign'
 assert m.verdict(p,t,p['path'])=='candidate_only'
