import Gio from 'gi://Gio';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
const NAME='io.github.Creammmmm.InkEcho.IsolatedCommitR16';
const PATH='/io/github/Creammmmm/InkEcho/IsolatedCommitR16';
const XML=`<node><interface name="${NAME}1"><method name="Begin"><arg type="b" direction="out"/></method><method name="Cancel"><arg type="b" direction="out"/></method><method name="Send"><arg type="s" direction="in"/><arg type="b" direction="out"/><arg type="b" direction="out"/></method><method name="Activate"><arg type="s" direction="in"/><arg type="b" direction="out"/></method><method name="Read"><arg type="b" direction="out"/><arg type="s" direction="out"/></method></interface></node>`;
export default class Probe extends Extension {
 enable(){this._active=false;this._obj=Gio.DBusExportedObject.wrapJSObject(XML,this);this._obj.export(Gio.DBus.session,PATH);this._owner=Gio.bus_own_name_on_connection(Gio.DBus.session,NAME,Gio.BusNameOwnerFlags.NONE,null,null);}
 Begin(){this._active=true;return true;}
 Cancel(){this._active=false;return true;}
 Read(){const title=global.display.focus_window?.get_title() ?? '';return [!!Main.inputMethod?.currentFocus,title.startsWith('InkEcho isolated ') ? title : 'other'];}
 Activate(title){if(!title.startsWith('InkEcho isolated '))return false;const w=global.get_window_actors().map(a=>a.meta_window).find(w=>w.get_title()===title);if(!w)return false;Main.activateWindow(w);return true;}
 Send(mode){if(!this._active||!Main.inputMethod?.currentFocus)return [false,false];Main.inputMethod.commit('甲');if(mode==='cancel')this._active=false;if(mode==='switch')this.Activate('InkEcho isolated B');return [true,mode==='switch' && global.display.focus_window?.get_title()==='InkEcho isolated B'];}
 disable(){this._active=false;if(this._owner)Gio.bus_unown_name(this._owner);this._obj?.unexport();}
}
