// Disposable private-bus probe only: no GNOME Shell, no actual text output.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {DeliveryGate} from './delivery_gate.js';
import {checkCapability} from './capability.js';
const xml = `<node><interface name="io.github.Creammmmm.InkEcho.IBusCandidate1">
<method name="Begin"><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
<method name="Commit"><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="out"/></method>
<method name="Cancel"><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
</interface></node>`;
class Service {
    constructor() { this.gate = new DeliveryGate(() => true, (_sender, token) => checkCapability(token)); }
    BeginAsync([token], call) {call.return_value(new GLib.Variant('(b)', [this.gate.begin(call.get_sender(), token)]));}
    CommitAsync([token, seq, char], call) {call.return_value(new GLib.Variant('(s)', [this.gate.commit(call.get_sender(), token, seq, char)]));}
    CancelAsync([token], call) {call.return_value(new GLib.Variant('(b)', [this.gate.cancel(call.get_sender(), token)]));}
}
const obj = Gio.DBusExportedObject.wrapJSObject(xml, new Service());
obj.export(Gio.DBus.session, '/io/github/Creammmmm/InkEcho/IBusCandidate');
Gio.bus_own_name_on_connection(Gio.DBus.session, 'io.github.Creammmmm.InkEcho.IBusCandidate', Gio.BusNameOwnerFlags.NONE, () => print('ready'), null);
new GLib.MainLoop(null, false).run();
