"""Inspect only our own PID, numeric caret/selection and focus/interface metadata."""
import os,sys,subprocess,time,json
from pathlib import Path
import gi
gi.require_version('Atspi','2.0')
from gi.repository import Atspi
root=Path(sys.argv[1]);env=dict(os.environ);env['GDK_BACKEND']='wayland';env.pop('GTK_IM_MODULE',None)
log=(root/'actor.log').open('x');actor=subprocess.Popen(['/usr/bin/python3',str(root/'actor.py'),str(root)],env=env,stdin=subprocess.PIPE,text=True,stdout=log,stderr=subprocess.STDOUT)
rows=[];api_calls=0

def walk(node,depth=0):
 if depth>12:return
 yield node
 for i in range(min(node.get_child_count(),64)):
  child=node.get_child_at_index(i)
  if child:yield from walk(child,depth+1)

def focused():
 desktop=Atspi.get_desktop(0)
 for i in range(min(desktop.get_child_count(),128)):
  app=desktop.get_child_at_index(i)
  if app and app.get_process_id()==actor.pid:
   values=[n for n in walk(app) if n.get_state_set().contains(Atspi.StateType.FOCUSED)]
   return values[0] if len(values)==1 else None
 return None

def send(fixed,active=lambda:True):
 global api_calls
 if not active():return 'cancelled_not_attempted'
 target=focused()
 if not target:return 'no_target_not_attempted'
 if not target.get_state_set().contains(Atspi.StateType.EDITABLE):return 'unsupported_not_attempted'
 if not target.is_editable_text() or not target.is_text():return 'unsupported_not_attempted'
 text=target.get_text_iface();editable=target.get_editable_text_iface()
 if text.get_n_selections()!=0:return 'selection_not_attempted'
 caret=text.get_caret_offset()
 if type(caret) is not int or caret<0:return 'unsupported_not_attempted'
 if not active():return 'cancelled_not_attempted'
 if not target.get_state_set().contains(Atspi.StateType.FOCUSED):return 'focus_changed_not_attempted'
 api_calls+=1
 try:ok=editable.insert_text(caret,fixed,len(fixed.encode('utf8')))
 except Exception:return 'unknown'
 return 'called_true_unconfirmed' if ok else 'called_false_unknown'

def command(value):actor.stdin.write(value+'\n');actor.stdin.flush();time.sleep(.25)
def record(case,status):
 time.sleep(.2);row={'case':case,'status':status,'calls':api_calls,'owned':json.loads((root/'owned-state.json').read_text())};rows.append(row);print(json.dumps(row),flush=True)
try:
 time.sleep(2);assert actor.poll() is None
 print(json.dumps({'owned_pid':actor.pid,'start':Path(f'/proc/{actor.pid}/stat').read_text().rsplit(')',1)[1].split()[19]}),flush=True)
 record('initial_a',send('甲'))
 command('b');record('current_b',send('乙'))
 command('a');record('current_a_again',send('丙'))
 record('cancel_before',send('戊',lambda:False))
 command('button');record('no_text_focus',send('戊'))
 command('selection');record('selection_reject',send('戊'))
 command('race');record('switch_during_insert',send('丁'))
finally:
 actor.stdin.write('quit\n');actor.stdin.flush();rc=actor.wait(timeout=5);log.close()
 (root/'rows.json').write_text(json.dumps(rows,indent=2));print(json.dumps({'actor_exit':rc,'read_text_api_calls':0,'clipboard_api_calls':0,'total_insert_calls':api_calls}),flush=True)
