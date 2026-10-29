import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {EpochPolicy} from './policy.mjs';
const NAME='io.github.Creammmmm.InkEcho.IMEpochProbe';
const PATH='/io/github/Creammmmm/InkEcho/IMEpochProbe';
const XML=`<node><interface name="${NAME}1">
<method name="Activate"><arg type="u" direction="in"/><arg type="b" direction="out"/></method>
<method name="Cancel"><arg type="b" direction="out"/></method>
<method name="Test"><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="out"/><arg type="u" direction="out"/><arg type="u" direction="out"/></method>
</interface></node>`;
export default class Probe extends Extension {
 enable(){
  this._generation=0;this._source=0;this._policy=null;this._sender=null;
  this._watch=global.display.connect('notify::focus-window',()=>{this._generation++;this._policy?.focusChanged();});
  this._obj=Gio.DBusExportedObject.wrapJSObject(XML,this);this._obj.export(Gio.DBus.session,PATH);
  this._owner=Gio.bus_own_name_on_connection(Gio.DBus.session,NAME,Gio.BusNameOwnerFlags.NONE,null,null);
 }
 _window(pid){return global.get_window_actors().map(a=>a.meta_window).find(w=>w.get_pid()===pid && ['InkEcho isolated wayland','InkEcho isolated simple'].includes(w.get_title()));}
 Activate(pid){const w=this._window(pid);if(!w)return false;Main.activateWindow(w);return global.display.focus_window===w;}
 CancelAsync(_args,invocation){
  const match=this._policy!==null && invocation.get_sender()===this._sender;
  if(match)this._policy.cancel();
  invocation.return_value(new GLib.Variant('(b)',[match]));
 }
 TestAsync([mode,sourcePid,targetPid],invocation){
  const source=this._window(sourcePid),target=this._window(targetPid),im=Main.inputMethod;
  const reject=code=>invocation.return_value(new GLib.Variant('(suu)',[code,0,0]));
  if(this._policy){reject('busy');return;}
  if(!['normal','switch','aba','cancel','cancel_rpc'].includes(mode)||!source||!target||
     global.display.focus_window!==source||source.get_client_type()!==Meta.WindowClientType.WAYLAND||
     !im?.currentFocus||typeof im.hasPreedit!=='function'||im.hasPreedit()){reject('not_attempted');return;}
  const policy=new EpochPolicy();policy.epoch=this._generation;
  const token=policy.begin();this._policy=policy;this._sender=invocation.get_sender();
  const initial=this._generation;
  if(!policy.attempted(token)){reject('not_attempted');return;}
  try{im.commit('甲');}catch(_){policy.cancel();}
  if(mode==='switch'||mode==='aba')this.Activate(targetPid);
  if(mode==='aba')this.Activate(sourcePid);
  if(mode==='cancel')policy.cancel();
  const finish=()=>{
   this._source=0;const status=policy.finish(token);
   if(this._policy===policy){this._policy=null;this._sender=null;}
   invocation.return_value(new GLib.Variant('(suu)',[status,this._generation-initial,policy.attempts]));
   return GLib.SOURCE_REMOVE;
  };
  this._source=mode==='cancel_rpc' ? GLib.timeout_add(GLib.PRIORITY_DEFAULT,50,finish) :
      GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE,finish);
 }
 disable(){
  this._policy?.cancel();if(this._source)GLib.source_remove(this._source);
  if(this._watch)global.display.disconnect(this._watch);
  if(this._owner)Gio.bus_unown_name(this._owner);this._obj?.unexport();
 }
}
