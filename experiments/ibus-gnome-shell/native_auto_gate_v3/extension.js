import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import IBus from 'gi://IBus';
import {getIBusManager} from 'resource:///org/gnome/shell/misc/ibusManager.js';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {Gate} from './gate.mjs';
const NAME='io.github.Creammmmm.InkEcho.OwnedNativeGateV3';
const PATH='/io/github/Creammmmm/InkEcho/OwnedNativeGateV3';
const XML=`<node><interface name="${NAME}1">
<method name="Begin"><arg type="u" direction="in"/><arg type="b" direction="out"/></method>
<method name="Send"><arg type="u" direction="in"/><arg type="s" direction="out"/></method>
<method name="Cancel"><arg type="b" direction="out"/></method>
<method name="Activate"><arg type="u" direction="in"/><arg type="b" direction="out"/></method>
<method name="Key"><arg type="u" direction="in"/><arg type="b" direction="out"/></method>
<method name="SwitchSend"><arg type="u" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="out"/><arg type="b" direction="out"/></method>
<method name="Read"><arg type="b" direction="out"/><arg type="b" direction="out"/><arg type="b" direction="out"/><arg type="b" direction="out"/><arg type="u" direction="out"/></method>
</interface></node>`;
export default class Probe extends Extension {
    enable() {
        this._pid = 0;
        this._gate = new Gate(() => this._snapshot(), () => Main.inputMethod.commit('甲'));
        this._obj = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._obj.export(Gio.DBus.session, PATH);
        this._owner = Gio.bus_own_name_on_connection(Gio.DBus.session, NAME,
            Gio.BusNameOwnerFlags.NONE, null, null);
    }
    _snapshot() {
        const im=Main.inputMethod;
        const w=global.display.focus_window;
        const supported=typeof im?.hasPreedit==='function' && typeof im?.commit==='function';
        const owned=!!w && w.get_pid()===this._pid &&
            w.get_title()==='InkEcho isolated wayland' &&
            w.get_client_type()===Meta.WindowClientType.WAYLAND;
        // Only inspect the boolean API; never get surrounding/preedit text.
        return {supported, owned, focused:!!im?.currentFocus,
            preedit:supported ? im.hasPreedit() : null};
    }
    BeginAsync([pid], invocation) {
        if (this._gate.owner === null) this._pid=pid;
        const s=this._snapshot();
        const ok=s.owned && this._gate.begin(invocation.get_sender());
        invocation.return_value(new GLib.Variant('(b)', [ok]));
    }
    SendAsync([seq], invocation) {
        invocation.return_value(new GLib.Variant('(s)',
            [this._gate.send(invocation.get_sender(),seq)]));
    }
    CancelAsync(_args, invocation) {
        invocation.return_value(new GLib.Variant('(b)',
            [this._gate.cancel(invocation.get_sender())]));
    }
    Activate(pid) {
        const w=global.get_window_actors().map(a=>a.meta_window).find(w=>
            w.get_pid()===pid && ['InkEcho isolated wayland','InkEcho isolated button',
                'InkEcho isolated simple'].includes(w.get_title()));
        if (!w) return false;
        Main.activateWindow(w);
        return global.display.focus_window===w;
    }
    Key(key) {
        const s=this._snapshot();
        const panel=getIBusManager()._panelService;
        if (!s.owned || !s.focused || !panel || ![110,105,32].includes(key)) return false;
        panel.forward_process_key_event(key,0,0);
        return true;
    }
    SwitchSendAsync([seq,pid], invocation) {
        const status=this._gate.send(invocation.get_sender(),seq);
        const switched=status==='attempted' ? this.Activate(pid) : false;
        invocation.return_value(new GLib.Variant('(sb)',[status,switched]));
    }
    Read() {
        const s=this._snapshot();
        return [s.supported,s.owned,s.focused,s.preedit===true,this._gate.attempts];
    }
    disable() {
        if(this._gate?.owner) this._gate.cancel(this._gate.owner);
        if(this._owner) Gio.bus_unown_name(this._owner);
        this._obj?.unexport();
    }
}
