// Disposable isolated test only. No text, credentials or surrounding text.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {getIBusManager} from 'resource:///org/gnome/shell/misc/ibusManager.js';

const NAME = 'io.github.Creammmmm.InkEcho.FocusProbe';
const PATH = '/io/github/Creammmmm/InkEcho/FocusProbe';
const XML = `<node><interface name="${NAME}1">
 <method name="Read"><arg type="b" direction="out"/><arg type="s" direction="out"/><arg type="as" direction="out"/></method>
</interface></node>`;

export default class FocusProbe extends Extension {
    enable() {
        this._panel = null;
        this._handlers = [];
        this._last = '';
        this._events = [];
        this._obj = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._obj.export(Gio.DBus.session, PATH);
        this._owner = Gio.bus_own_name_on_connection(Gio.DBus.session, NAME,
            Gio.BusNameOwnerFlags.NONE, null, null);
        this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
            const panel = getIBusManager()._panelService;
            if (panel !== this._panel) {
                this._disconnect();
                this._panel = panel;
                this._last = '';
                this._events.push('panel-changed');
                if (panel) {
                    this._handlers.push(panel.connect('focus-in', (_p, path) => {
                        this._last = String(path);
                        this._events.push(`in:${path}`);
                    }));
                    this._handlers.push(panel.connect('focus-out', (_p, path) => {
                        this._events.push(`out:${path}`);
                        if (this._last === String(path)) this._last = '';
                    }));
                }
            }
            if (this._events.length > 100) this._events.splice(0, this._events.length - 100);
            return GLib.SOURCE_CONTINUE;
        });
    }
    ReadAsync(_args, invocation) {
        invocation.return_value(new GLib.Variant('(bsas)',
            [this._panel !== null, this._last, this._events]));
    }
    _disconnect() {
        if (this._panel) for (const id of this._handlers) this._panel.disconnect(id);
        this._handlers = [];
    }
    disable() {
        if (this._timer) GLib.Source.remove(this._timer);
        this._disconnect();
        if (this._owner) Gio.bus_unown_name(this._owner);
        if (this._obj) this._obj.unexport();
    }
}
