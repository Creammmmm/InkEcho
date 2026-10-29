import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const NAME = 'io.github.Creammmmm.InkEcho.FocusObjectProbe';
const PATH = '/io/github/Creammmmm/InkEcho/FocusObjectProbe';
const XML = `<node><interface name="${NAME}1">
 <method name="Activate"><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
 <method name="Remember"><arg type="b" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/></method>
 <method name="Compare"><arg type="b" direction="out"/><arg type="b" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/></method>
</interface></node>`;

export default class Probe extends Extension {
    enable() {
        this._remembered = null;
        this._obj = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._obj.export(Gio.DBus.session, PATH);
        this._owner = Gio.bus_own_name_on_connection(Gio.DBus.session, NAME,
            Gio.BusNameOwnerFlags.NONE, null, null);
    }
    Activate(title) {
        if (!title.startsWith('InkEcho isolated ')) return false;
        const window = global.get_window_actors().map(a => a.meta_window).find(w => w.get_title() === title);
        if (!window) return false;
        Main.activateWindow(window);
        return true;
    }
    Remember() {
        this._remembered = Main.inputMethod?.currentFocus ?? null;
        const title = global.display.focus_window?.get_title() ?? '';
        return [!!this._remembered, Main.inputMethod?._context?.get_object_path() ?? '',
            title.startsWith('InkEcho isolated ') ? title : 'other'];
    }
    Compare() {
        const current = Main.inputMethod?.currentFocus ?? null;
        const title = global.display.focus_window?.get_title() ?? '';
        return [!!current, !!current && current === this._remembered,
            Main.inputMethod?._context?.get_object_path() ?? '',
            title.startsWith('InkEcho isolated ') ? title : 'other'];
    }
    disable() {
        this._remembered = null;
        if (this._owner) Gio.bus_unown_name(this._owner);
        this._obj?.unexport();
    }
}
