import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {DeliveryGateV2} from './delivery_gate.js';
import {consumeCapability} from './capability.js';
const xml = `<node><interface name="io.github.Creammmmm.InkEcho.IBusCandidateV21">
<method name="Begin"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
<method name="Commit"><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="out"/></method>
<method name="Cancel"><arg type="b" direction="out"/></method>
</interface></node>`;
class Service {
    constructor() { this.gate = new DeliveryGateV2(() => true, ([name, token]) => consumeCapability(name, token)); }
    BeginAsync([name, token], call) {call.return_value(new GLib.Variant('(b)', [this.gate.begin(call.get_sender(), [name, token])]));}
    CommitAsync([seq, char], call) {call.return_value(new GLib.Variant('(s)', [this.gate.commit(call.get_sender(), seq, char)]));}
    CancelAsync(_args, call) {call.return_value(new GLib.Variant('(b)', [this.gate.cancel(call.get_sender())]));}
}
const service = new Service();
const obj = Gio.DBusExportedObject.wrapJSObject(xml, service);
obj.export(Gio.DBus.session, '/io/github/Creammmmm/InkEcho/IBusCandidateV2');
Gio.DBus.session.signal_subscribe('org.freedesktop.DBus','org.freedesktop.DBus','NameOwnerChanged','/org/freedesktop/DBus',null,Gio.DBusSignalFlags.NONE,(_c,_s,_p,_i,_n,v)=>{
 const [name, oldOwner, newOwner] = v.deep_unpack();
 if (name.startsWith(':') && oldOwner && !newOwner) service.gate.ownerLost(name);
});
Gio.bus_own_name_on_connection(Gio.DBus.session, 'io.github.Creammmmm.InkEcho.IBusCandidateV2', Gio.BusNameOwnerFlags.NONE, () => print('ready'), null);
new GLib.MainLoop(null, false).run();
