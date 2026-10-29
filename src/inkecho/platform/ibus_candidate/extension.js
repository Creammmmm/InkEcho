// Isolated prototype: never automatically installed or activated.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import IBus from 'gi://IBus';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {getIBusManager} from 'resource:///org/gnome/shell/misc/ibusManager.js';
import {DeliveryGateV2} from './delivery_gate.js';
import {consumeCapability} from './capability.js';

const SERVICE = 'io.github.Creammmmm.InkEcho.IBusCandidateV2';
const PATH = '/io/github/Creammmmm/InkEcho/IBusCandidateV2';
const XML = `<node><interface name="${SERVICE}1">
 <method name="Begin"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
 <method name="Commit"><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="out"/></method>
 <method name="Cancel"><arg type="b" direction="out"/></method>
</interface></node>`;

export default class Candidate extends Extension {
    enable() {
        this._gate = new DeliveryGateV2(() => {
            const panel = getIBusManager()._panelService;
            if (!panel) return null;
            return character => panel.commit_text(IBus.Text.new_from_string(character));
        }, ([name, token]) => consumeCapability(name, token));
        this._obj = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._obj.export(Gio.DBus.session, PATH);
        this._owner = Gio.bus_own_name_on_connection(Gio.DBus.session, SERVICE,
            Gio.BusNameOwnerFlags.NONE, null, null);
        this._watch = Gio.DBus.session.signal_subscribe('org.freedesktop.DBus',
            'org.freedesktop.DBus', 'NameOwnerChanged', '/org/freedesktop/DBus',
            null, Gio.DBusSignalFlags.NONE, (_c, _s, _p, _i, _n, params) => {
                const [name, oldOwner, newOwner] = params.deep_unpack();
                if (name.startsWith(':') && oldOwner && !newOwner)
                    this._gate.ownerLost(name);
            });
    }
    BeginAsync([name, token], invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [this._gate.begin(invocation.get_sender(), [name, token])]));
    }
    CommitAsync([sequence, text], invocation) {
        invocation.return_value(new GLib.Variant('(s)',
            [this._gate.commit(invocation.get_sender(), sequence, text)]));
    }
    CancelAsync(_args, invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [this._gate.cancel(invocation.get_sender())]));
    }
    disable() {
        if (this._watch) Gio.DBus.session.signal_unsubscribe(this._watch);
        if (this._owner) Gio.bus_unown_name(this._owner);
        if (this._obj) this._obj.unexport();
        this._gate = null;
    }
}
