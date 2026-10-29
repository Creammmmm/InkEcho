import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {verdict} from './gate.js';
const N='io.github.Creammmmm.InkEcho.GnomeOwnedContext',P='/io/github/Creammmmm/InkEcho/GnomeOwnedContext';
const XML=`<node><interface name="${N}1"><method name="Read"><arg type="s" direction="out"/></method></interface></node>`;
export default class Probe extends Extension {
 enable(){this._enabled=true;this._pending=null;this._epoch=0;this._display=global.display.connect('notify::focus-window',()=>this._epoch++);this._stage=global.stage.connect('notify::key-focus',()=>this._epoch++);this._obj=Gio.DBusExportedObject.wrapJSObject(XML,this);this._obj.export(Gio.DBus.session,P);this._owner=Gio.bus_own_name_on_connection(Gio.DBus.session,N,Gio.BusNameOwnerFlags.NONE,null,null);}
 _snapshot(){const im=Main.inputMethod,w=global.display.focus_window;return {epoch:this._epoch,pid:w?.get_pid()??0,window:w?.get_id()??0,native:!!w&&w.get_client_type()===Meta.WindowClientType.WAYLAND,focused:!!im?.currentFocus,shellUi:!!global.stage.key_focus,shellPath:im?._context?.get_object_path()??'',preedit:typeof im?.hasPreedit==='function'?im.hasPreedit():null};}
 _reply(invocation,result){try{invocation.return_value(new GLib.Variant('(s)',[JSON.stringify(result)]));}catch(_){}}
 ReadAsync(_args,invocation){let before;try{before=this._snapshot();}catch(_){this._reply(invocation,{verdict:'unknown'});return;}const im=Main.inputMethod;
  const initial=verdict(before,before.shellPath);if(initial!=='gnome_owned_native_candidate'){this._reply(invocation,{...before,verdict:initial});return;}
  if(this._pending||typeof im._ibus?.current_input_context_async!=='function'){this._reply(invocation,{...before,verdict:'unavailable'});return;}
  const cancel=new Gio.Cancellable();this._pending={cancel,invocation};im._ibus.current_input_context_async(750,cancel,(bus,res)=>{if(this._pending?.invocation!==invocation)return;this._pending=null;
   let current,after;try{current=bus.current_input_context_async_finish(res);after=this._snapshot();}catch(_){this._reply(invocation,{...before,verdict:'unknown'});return;}
   const stable=this._enabled&&Main.inputMethod===im&&after.epoch===before.epoch&&after.window===before.window&&after.shellPath===before.shellPath;
   this._reply(invocation,{...after,current,verdict:stable?verdict(after,current):'changed'});
  });
 }
 disable(){this._enabled=false;if(this._pending){const p=this._pending;this._pending=null;p.cancel.cancel();this._reply(p.invocation,{verdict:'closed'});}if(this._display)global.display.disconnect(this._display);if(this._stage)global.stage.disconnect(this._stage);if(this._owner)Gio.bus_unown_name(this._owner);this._obj?.unexport();}
}
