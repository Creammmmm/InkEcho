import Gio from 'gi://Gio';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {getIBusManager} from 'resource:///org/gnome/shell/misc/ibusManager.js';
const NAME='io.github.Creammmmm.InkEcho.PresendFault',PATH='/io/github/Creammmmm/InkEcho/PresendFault';
const XML=`<node><interface name="${NAME}1"><method name="SetUnavailable"><arg type="b" direction="in"/><arg type="b" direction="out"/></method><method name="Present"><arg type="b" direction="out"/></method></interface></node>`;
export default class Fault extends Extension {
 enable(){this._saved=null;this._obj=Gio.DBusExportedObject.wrapJSObject(XML,this);this._obj.export(Gio.DBus.session,PATH);this._owner=Gio.bus_own_name_on_connection(Gio.DBus.session,NAME,Gio.BusNameOwnerFlags.NONE,null,null);}
 SetUnavailable(enable){let m=getIBusManager();if(enable){if(!m._panelService || this._saved)return false;this._saved=m._panelService;m._panelService=null;return !m._panelService;} if(!this._saved)return false;m._panelService=this._saved;this._saved=null;return !!m._panelService;}
 Present(){return !!getIBusManager()._panelService;}
 disable(){if(this._saved){getIBusManager()._panelService=this._saved;this._saved=null;}if(this._owner)Gio.bus_unown_name(this._owner);this._obj?.unexport();}
}
