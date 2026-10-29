// SPDX-License-Identifier: MIT
// Experimental prototype: never auto-install or enable in a real user session.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import IBus from 'gi://IBus';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {getIBusManager} from 'resource:///org/gnome/shell/misc/ibusManager.js';
import {DeliveryGate} from './delivery_gate.js';
import {checkCapability} from './capability.js';

const XML = `<node><interface name="io.github.Creammmmm.InkEcho.IBusCandidate1">
  <method name="Begin"><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
  <method name="Commit"><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="out"/></method>
  <method name="Cancel"><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
</interface></node>`;



export default class Candidate extends Extension {
    enable() {
        this._gate = new DeliveryGate(character => {
            // Resolve at every send; no recording-time target or content read.
            const panel = getIBusManager()._panelService;
            if (!panel) return false;
            panel.commit_text(IBus.Text.new_from_string(character));
            return true;
        }, (_sender, token) => checkCapability(token));
        this._obj = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._obj.export(Gio.DBus.session, '/io/github/Creammmmm/InkEcho/IBusCandidate');
        this._owner = Gio.bus_own_name_on_connection(Gio.DBus.session,
            'io.github.Creammmmm.InkEcho.IBusCandidate', Gio.BusNameOwnerFlags.NONE,
            null, null);
        this._watch = Gio.DBus.session.signal_subscribe('org.freedesktop.DBus',
            'org.freedesktop.DBus', 'NameOwnerChanged', '/org/freedesktop/DBus',
            null, Gio.DBusSignalFlags.NONE, (_c, _s, _p, _i, _n, params) => {
                const [name, oldOwner, newOwner] = params.deep_unpack();
                if (name.startsWith(':') && oldOwner && !newOwner)
                    this._gate.ownerLost(name);
            });
    }
    BeginAsync([token], invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [this._gate.begin(invocation.get_sender(), token)]));
    }
    CommitAsync([token, sequence, text], invocation) {
        invocation.return_value(new GLib.Variant('(s)',
            [this._gate.commit(invocation.get_sender(), token, sequence, text)]));
    }
    CancelAsync([token], invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [this._gate.cancel(invocation.get_sender(), token)]));
    }
    disable() {
        if (this._watch) Gio.DBus.session.signal_unsubscribe(this._watch);
        if (this._owner) Gio.bus_unown_name(this._owner);
        if (this._obj) this._obj.unexport();
        this._gate = null;
    }
}
