// Isolated prototype: never automatically installed or activated.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import IBus from 'gi://IBus';
import Clutter from 'gi://Clutter';
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
 <method name="OwnerGuardVersion"><arg type="s" direction="out"/></method>
 <method name="Probe"><arg type="s" direction="out"/></method>
 <method name="Begin"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
 <method name="Commit"><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="out"/></method>
 <method name="BeginBatch"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="b" direction="out"/></method>
 <method name="CommitBatch"><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="out"/></method>
 <method name="BeginBounded"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="t" direction="in"/><arg type="b" direction="out"/></method>
 <method name="CommitBounded"><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="t" direction="in"/><arg type="s" direction="out"/></method>
 <method name="BeginLongBounded"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="t" direction="in"/><arg type="b" direction="out"/></method>
 <method name="CommitLongBounded"><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="t" direction="in"/><arg type="s" direction="out"/></method>
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
            return character => Main.inputMethod.commit(character);
        }, ([name, token]) => consumeCapability(name, token), () => GLib.get_monotonic_time());
        this._gate = new OwnedGate(this._delivery, () => this._snapshot(),
            im => new Promise((resolve, reject) => {
                try { im._ibus.current_input_context_async(750, null, (bus, result) => {
                    try { resolve(bus.current_input_context_async_finish(result)); }
                    catch (error) { reject(error); }
                }); } catch (error) { reject(error); }
            }), () => this._producerBoundary());
        this._obj = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._obj.export(Gio.DBus.session, PATH);
        this._owner = Gio.bus_own_name_on_connection(Gio.DBus.session, SERVICE,
            Gio.BusNameOwnerFlags.NONE, null, null);
        this._watch = Gio.DBus.session.signal_subscribe('org.freedesktop.DBus',
            'org.freedesktop.DBus', 'NameOwnerChanged', '/org/freedesktop/DBus',
            null, Gio.DBusSignalFlags.NONE, (_c, _s, _p, _i, _n, params) => {
                const [name, oldOwner, newOwner] = params.deep_unpack();
                if (name === SERVICE && oldOwner === Gio.DBus.session.get_unique_name() &&
                    newOwner !== oldOwner)
                    this._gate.close();
                if (name.startsWith(':') && oldOwner && !newOwner)
                    this._gate.ownerLost(name);
            });
    }
    _producerBoundary() {
        // GNOME 46 source: stage processes queued events before after-update;
        // text-input done is scheduled at CLUTTER_PRIORITY_EVENTS + 1 (=1).
        // Priority 2 below runs only after that ready producer source. Not ACK.
        return new Promise(resolve => {
            let signal = 0, idle = 0, timeout = 0, finished = false;
            const finish = ok => {
                if (finished) return;
                finished = true;
                if (signal) global.stage.disconnect(signal);
                if (idle) GLib.source_remove(idle);
                if (timeout) GLib.source_remove(timeout);
                this._boundaryAbort = null;
                resolve(ok);
            };
            this._boundaryAbort = () => finish(false);
            signal = global.stage.connect('after-update', () => {
                if (Clutter.events_pending()) { global.stage.schedule_update(); return; }
                global.stage.disconnect(signal); signal = 0;
                idle = GLib.idle_add(2, () => {
                    idle = 0;
                    finish(true);
                    return GLib.SOURCE_REMOVE;
                });
            });
            timeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 750, () => {
                timeout = 0; finish(false); return GLib.SOURCE_REMOVE;
            });
            global.stage.schedule_update();
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
    OwnerGuardVersionAsync(_args, invocation) {
        invocation.return_value(new GLib.Variant('(s)', ['owner-loss-v1']));
    }
    // Legacy methods stay introspectable but can never create or mutate a task.
    // A matching upgraded client must negotiate the bounded methods.
    BeginAsync([name, token], invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [false]));
    }
    async CommitAsync([sequence, text], invocation) {
        invocation.return_value(new GLib.Variant('(s)', ['rejected']));
    }
    BeginBatchAsync([name, token, version], invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [false]));
    }
    async CommitBatchAsync([sequence, text], invocation) {
        invocation.return_value(new GLib.Variant('(s)', ['rejected']));
    }
    BeginBoundedAsync([name, token, version, deadlineUs], invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [version === 1 && this._gate.beginBounded(invocation.get_sender(), [name, token], version, deadlineUs)]));
    }
    async CommitBoundedAsync([sequence, text, deadlineUs], invocation) {
        const result = this._gate.delivery.session?.version === 1 ?
            await this._gate.commitBounded(invocation.get_sender(), sequence, text, deadlineUs) : 'rejected';
        invocation.return_value(new GLib.Variant('(s)', [result]));
    }
    BeginLongBoundedAsync([name, token, version, deadlineUs], invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [version === 2 && this._gate.beginBounded(invocation.get_sender(), [name, token], version, deadlineUs)]));
    }
    async CommitLongBoundedAsync([sequence, text, deadlineUs], invocation) {
        const result = this._gate.delivery.session?.version === 2 ?
            await this._gate.commitBounded(invocation.get_sender(), sequence, text, deadlineUs) : 'rejected';
        invocation.return_value(new GLib.Variant('(s)', [result]));
    }
    CancelAsync(_args, invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [this._gate.cancel(invocation.get_sender(), () => this._boundaryAbort?.())]));
    }
    disable() {
        this._alive = false;
        this._boundaryAbort?.();
        this._gate.close();
        if (this._focusWatch) global.display.disconnect(this._focusWatch);
        if (this._stageWatch) global.stage.disconnect(this._stageWatch);
        if (this._watch) Gio.DBus.session.signal_unsubscribe(this._watch);
        if (this._owner) Gio.bus_unown_name(this._owner);
        if (this._obj) this._obj.unexport();
        this._gate = null;
    }
}
