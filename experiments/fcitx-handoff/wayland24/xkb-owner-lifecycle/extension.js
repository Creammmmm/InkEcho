import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {getKeyboardManager} from 'resource:///org/gnome/shell/misc/keyboardManager.js';
const NAME='org.example.InkEchoXkbProbe';
const XML=`<node><interface name="${NAME}"><method name="Apply"><arg direction="out" type="s"/></method><method name="Press"><arg direction="out" type="s"/></method><method name="Restore"><arg direction="out" type="s"/></method></interface></node>`;
export default class Probe extends Extension {
 enable(){this._session=null;this._settings=new Gio.Settings({schema_id:'org.gnome.desktop.input-sources'});this._change=this._settings.connect('changed',()=>{if(this._session)this._finish('settings-changed',false)});this._obj=Gio.DBusExportedObject.wrapJSObject(XML,this);this._obj.export(Gio.DBus.session,'/org/example/InkEchoXkbProbe');this._owner=Gio.bus_own_name_on_connection(Gio.DBus.session,NAME,Gio.BusNameOwnerFlags.NONE,null,null)}
 _current(){return {...getKeyboardManager()._currentKeymap}}
 _finish(reason,restore){let s=this._session;if(!s)return;this._session=null;if(s.watch)Gio.bus_unwatch_name(s.watch);if(restore&&JSON.stringify(this._current())===s.baseline){let k=this._current();global.backend.set_keymap(k.layouts,k.variants,k.options,k.model)};log(`InkEcho test finish ${reason}`)}
 ApplyAsync(_params,inv){let sender=inv.get_sender();if(this._session){inv.return_value(new GLib.Variant('(s)',['busy']));return}let k=this._current();this._session={sender,baseline:JSON.stringify(k),watch:0};this._session.watch=Gio.bus_watch_name_on_connection(Gio.DBus.session,sender,Gio.BusNameWatcherFlags.NONE,null,()=>this._finish('owner-lost',true));global.backend.set_keymap(k.layouts,k.variants,[k.options,'inkecho:test'].filter(Boolean).join(','),k.model);inv.return_value(new GLib.Variant('(s)',['acquired']))}
 PressAsync(_params,inv){let s=this._session;if(!s||s.sender!==inv.get_sender()){inv.return_value(new GLib.Variant('(s)',['not-owner']));return}if(JSON.stringify(this._current())!==s.baseline){this._finish('keymap-changed',false);inv.return_value(new GLib.Variant('(s)',['changed']));return}let seat=Clutter.get_default_backend().get_default_seat();this._keyboard=seat.create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);this._keyboard.notify_key(GLib.get_monotonic_time(),124,Clutter.KeyState.PRESSED);this._keyboard.notify_key(GLib.get_monotonic_time(),124,Clutter.KeyState.RELEASED);inv.return_value(new GLib.Variant('(s)',['sent']))}
 RestoreAsync(_params,inv){if(!this._session||this._session.sender!==inv.get_sender()){inv.return_value(new GLib.Variant('(s)',['not-owner']));return}this._finish('restore',true);inv.return_value(new GLib.Variant('(s)',['restored']))}
 disable(){this._finish('disable',true);if(this._change)this._settings.disconnect(this._change);if(this._owner)Gio.bus_unown_name(this._owner);if(this._obj)this._obj.unexport();this._keyboard=null}
}
