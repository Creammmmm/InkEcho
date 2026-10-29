// Isolated prototype: never automatically installed or activated.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import IBus from 'gi://IBus';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {OwnedGate} from './owned_gate.js';
import {probeOwned} from './probe.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {getIBusManager} from 'resource:///org/gnome/shell/misc/ibusManager.js';
import {DeliveryGateV2} from './delivery_gate.js';
import {consumeCapability} from './capability.js';

const SERVICE = 'io.github.Creammmmm.InkEcho.IBusOwnedCandidateV5';
const PATH = '/io/github/Creammmmm/InkEcho/IBusOwnedCandidateV5';
const XML = `<node><interface name="${SERVICE}1">
 <method name="Probe"><arg type="s" direction="out"/></method>
 <method name="Begin"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
 <method name="Commit"><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="out"/></method>
 <method name="Cancel"><arg type="b" direction="out"/></method>
</interface></node>`;

export default class Candidate extends Extension {
    enable() {
        this._alive = true;
        this._epoch = 0;
        this._focusWatch = global.display.connect('notify::focus-window', () => this._epoch++);
        this._stageWatch = global.stage.connect('notify::key-focus', () => this._epoch++);
        this._delivery = new DeliveryGateV2(() => {
            const panel = getIBusManager()._panelService;
            if (!panel) return null;
            return character => panel.commit_text(IBus.Text.new_from_string(character));
        }, ([name, token]) => consumeCapability(name, token));
        this._gate = new OwnedGate(this._delivery, () => this._snapshot(),
            im => new Promise((resolve, reject) => {
                try { im._ibus.current_input_context_async(750, null, (bus, result) => {
                    try { resolve(bus.current_input_context_async_finish(result)); }
                    catch (error) { reject(error); }
                }); } catch (error) { reject(error); }
            }));
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
    _snapshot() {
        const im = Main.inputMethod, w = global.display.focus_window;
        return {im, epoch: this._epoch, window: w?.get_id() ?? 0,
            native: !!w && w.get_client_type() === Meta.WindowClientType.WAYLAND,
            focused: !!im?.currentFocus, shellUi: !!global.stage.key_focus,
            shellPath: im?._context?.get_object_path() ?? '',
            preedit: typeof im?.hasPreedit === 'function' ? im.hasPreedit() : null};
    }
    async ProbeAsync(_args, invocation) {
        let result = 'unknown';
        if (!this._probing && this._alive) {
            this._probing = true;
            try {
                result = await probeOwned(() => this._snapshot(), im =>
                    new Promise((resolve, reject) => {
                        try { im._ibus.current_input_context_async(750, null, (bus, res) => {
                            try { resolve(bus.current_input_context_async_finish(res)); }
                            catch (error) { reject(error); }
                        }); } catch (error) { reject(error); }
                    }), () => this._alive);
            } finally { this._probing = false; }
        }
        invocation.return_value(new GLib.Variant('(s)', [result]));
    }
    BeginAsync([name, token], invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [this._gate.begin(invocation.get_sender(), [name, token])]));
    }
    async CommitAsync([sequence, text], invocation) {
        const result = await this._gate.commit(invocation.get_sender(), sequence, text);
        invocation.return_value(new GLib.Variant('(s)', [result]));
    }
    CancelAsync(_args, invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [this._gate.cancel(invocation.get_sender())]));
    }
    disable() {
        this._alive = false;
        this._gate.close();
        if (this._focusWatch) global.display.disconnect(this._focusWatch);
        if (this._stageWatch) global.stage.disconnect(this._stageWatch);
        if (this._watch) Gio.DBus.session.signal_unsubscribe(this._watch);
        if (this._owner) Gio.bus_unown_name(this._owner);
        if (this._obj) this._obj.unexport();
        this._gate = null;
    }
}
