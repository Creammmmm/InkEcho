import Gio from 'gi://Gio';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
const NAME='io.github.Creammmmm.InkEcho.WaylandFocusProbe';
const PATH='/io/github/Creammmmm/InkEcho/WaylandFocusProbe';
const XML=`<node><interface name="${NAME}1"><method name="Read"><arg type="s" direction="out"/></method><method name="Activate"><arg type="s" direction="in"/><arg type="b" direction="out"/></method></interface></node>`;
export default class Probe extends Extension {
 enable() { this._obj=Gio.DBusExportedObject.wrapJSObject(XML,this); this._obj.export(Gio.DBus.session,PATH); this._owner=Gio.bus_own_name_on_connection(Gio.DBus.session,NAME,Gio.BusNameOwnerFlags.NONE,null,null); }
 Read() { let title=global.display.focus_window?.get_title() ?? ''; return title.startsWith('InkEcho isolated ') ? title : 'other'; }
 Activate(title) { if (!title.startsWith('InkEcho isolated ')) return false; const w=global.get_window_actors().map(a=>a.meta_window).find(w=>(w.get_title() ?? '').startsWith(title)); if (!w) return false; Main.activateWindow(w); return true; }
 disable() { if(this._owner) Gio.bus_unown_name(this._owner); this._obj?.unexport(); }
}
