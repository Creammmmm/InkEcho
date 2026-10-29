import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {getIBusManager} from 'resource:///org/gnome/shell/misc/ibusManager.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
const N='io.github.Creammmmm.InkEcho.V3Fixture';const P='/io/github/Creammmmm/InkEcho/V3Fixture';
const XML=`<node><interface name="${N}1"><method name="Arm"><arg type="u" direction="in"/><arg type="b" direction="out"/></method><method name="Key"><arg type="u" direction="in"/><arg type="b" direction="out"/></method><method name="Read"><arg type="b" direction="out"/><arg type="b" direction="out"/></method></interface></node>`;
export default class Fixture extends Extension {
enable(){this._pid=0;this._obj=Gio.DBusExportedObject.wrapJSObject(XML,this);this._obj.export(Gio.DBus.session,P);this._owner=Gio.bus_own_name_on_connection(Gio.DBus.session,N,Gio.BusNameOwnerFlags.NONE,null,null);}
Arm(pid){this._pid=pid;const w=global.display.focus_window;return !!w&&w.get_pid()===pid&&w.get_title()==='InkEcho V3 owned receiver';}
Read(){return [!!Main.inputMethod.currentFocus,Main.inputMethod.hasPreedit()===true];}
    Key(key) {
        const w=global.display.focus_window;const s={owned:!!w&&w.get_pid()===this._pid&&w.get_title()==='InkEcho V3 owned receiver',focused:!!Main.inputMethod.currentFocus};
        const panel=getIBusManager()._panelService;
        if (!s.owned || !s.focused || !panel || ![110,105,32].includes(key)) return false;
        panel.forward_process_key_event(key,0,0);
        return true;
    }
disable(){if(this._owner)Gio.bus_unown_name(this._owner);this._obj?.unexport();}
}
