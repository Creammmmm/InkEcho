import Gio from 'gi://Gio';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {getIBusManager} from 'resource:///org/gnome/shell/misc/ibusManager.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
const N='io.github.inkecho.VfuncLab', P='/io/github/inkecho/VfuncLab';
const XML=`<node><interface name="${N}"><method name="Key"><arg type="u" direction="in"/><arg type="b" direction="out"/></method><method name="Direct"><arg type="b" direction="in"/><arg type="s" direction="out"/></method></interface></node>`;
export default class Test extends Extension {
 enable(){this.obj=Gio.DBusExportedObject.wrapJSObject(XML,this);this.obj.export(Gio.DBus.session,P);this.owner=Gio.bus_own_name_on_connection(Gio.DBus.session,N,Gio.BusNameOwnerFlags.NONE,null,null);}
 Key(key){const p=getIBusManager()._panelService;if(!p||![32,110,105].includes(key))return false;p.forward_process_key_event(key,0,0);return true;}
 Direct(switchWindow){const f=Main.inputMethod?.currentFocus;if(!f)return 'no_focus';try {const method=f.vfunc_commit_text;if(typeof method!=='function')return 'method_missing';method.call(f,'甲');if(switchWindow){const w=global.get_window_actors().map(a=>a.meta_window).find(w=>w.get_title()==='InkEcho synthetic preedit B');if(!w)return 'window_missing';Main.activateWindow(w);}return 'invoked';} catch(e){return 'error:'+e.toString();}}
 disable(){Gio.bus_unown_name(this.owner);this.obj.unexport();}
}
