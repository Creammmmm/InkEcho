import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const NAME = 'io.github.Creammmmm.InkEcho.WaylandFocusProbe';
const PATH = '/io/github/Creammmmm/InkEcho/WaylandFocusProbe';
const XML = `<node><interface name="${NAME}1">
 <method name="Read"><arg type="b" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/></method>
 <method name="Test"><arg type="s" direction="in"/><arg type="b" direction="out"/><arg type="b" direction="out"/></method>
 <method name="Preedit"><arg type="b" direction="out"/></method>
 <method name="Activate"><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
</interface></node>`;

// Experimental only: extracting an event from the shared queue can reorder it.
export default class Probe extends Extension {
    enable() {
        this._obj = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._obj.export(Gio.DBus.session, PATH);
        this._owner = Gio.bus_own_name_on_connection(Gio.DBus.session, NAME,
            Gio.BusNameOwnerFlags.NONE, null, null);
    }
    Read() {
        const im = Main.inputMethod;
        let path = '';
        try { path = im?._context?.get_object_path() ?? ''; } catch (_) {}
        const title = global.display.focus_window?.get_title() ?? '';
        return [!!im?.currentFocus, String(path), title.startsWith('InkEcho isolated ') ? title : 'other'];
    }
    Test(target) {
        const im = Main.inputMethod;
        const focus = im?.currentFocus;
        if (!focus?.is_focused()) return [false, false];
        im.commit('甲');
        const event = Clutter.Event.get();
        if (!event) return [false, false];
        if (event.type() !== Clutter.EventType.IM_COMMIT || event.get_im_text() !== '甲') {
            event.put();
            return [false, false];
        }
        const handled = focus.process_event(event);
        if (target) this.Activate(target);
        return [handled, target ? global.display.focus_window?.get_title() === target : false];
    }
    Preedit() {
        const im = Main.inputMethod;
        if (!im?.currentFocus?.is_focused()) return false;
        im.set_preedit_text('测试', 1, 1, Clutter.PreeditResetMode.CLEAR);
        return true;
    }
    Activate(title) {
        if (!title.startsWith('InkEcho isolated ')) return false;
        const window = global.get_window_actors().map(a => a.meta_window).find(w => w.get_title() === title);
        if (!window) return false;
        Main.activateWindow(window);
        return true;
    }
    disable() {
        if (this._owner) Gio.bus_unown_name(this._owner);
        this._obj?.unexport();
    }
}
