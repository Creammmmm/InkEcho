import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {getKeyboardManager} from 'resource:///org/gnome/shell/misc/keyboardManager.js';
const NAME='org.example.InkEchoXkbProbe';
const XML=`<node><interface name="${NAME}"><method name="Apply"><arg direction="out" type="s"/></method><method name="Press"><arg direction="out" type="s"/></method><method name="PressKey"><arg direction="in" type="u"/><arg direction="out" type="s"/></method><method name="Restore"><arg direction="out" type="s"/></method></interface></node>`;
export default class Probe extends Extension {
 enable() {this._original=null;this._obj=Gio.DBusExportedObject.wrapJSObject(XML,this);this._obj.export(Gio.DBus.session,'/org/example/InkEchoXkbProbe');this._owner=Gio.bus_own_name_on_connection(Gio.DBus.session,NAME,Gio.BusNameOwnerFlags.NONE,null,null);}
 Apply() {let km=getKeyboardManager();this._original={...km._currentKeymap}; let k=this._original;global.backend.set_keymap(k.layouts,k.variants,[k.options,'inkecho:test'].filter(Boolean).join(','),k.model); return JSON.stringify(k);}
 Press() {return this.PressKey(124);}
 PressKey(key) {let seat=Clutter.get_default_backend().get_default_seat();this._keyboard=seat.create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);this._keyboard.notify_key(GLib.get_monotonic_time(),key,Clutter.KeyState.PRESSED);this._keyboard.notify_key(GLib.get_monotonic_time(),key,Clutter.KeyState.RELEASED);return 'sent';}
 Restore() {if (!this._original) return 'not-applied';let k={...getKeyboardManager()._currentKeymap};global.backend.set_keymap(k.layouts,k.variants,k.options,k.model);this._original=null;return 'restored-current:'+JSON.stringify(k);}
 disable(){if(this._original)this.Restore();if(this._owner) Gio.bus_unown_name(this._owner);if(this._obj)this._obj.unexport();this._keyboard=null;}
}
