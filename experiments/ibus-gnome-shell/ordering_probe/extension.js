import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
const NAME='io.github.Creammmmm.InkEcho.IMOrderProbe';
const PATH='/io/github/Creammmmm/InkEcho/IMOrderProbe';
const XML=`<node><interface name="${NAME}1">
<method name="Activate"><arg type="u" direction="in"/><arg type="b" direction="out"/></method>
<method name="Test"><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="out"/><arg type="b" direction="out"/><arg type="x" direction="out"/></method>
</interface></node>`;
export default class Probe extends Extension {
    enable() {
        this._sources=new Set();this._generation=0;
        this._obj=Gio.DBusExportedObject.wrapJSObject(XML,this);
        this._obj.export(Gio.DBus.session,PATH);
        this._owner=Gio.bus_own_name_on_connection(Gio.DBus.session,NAME,Gio.BusNameOwnerFlags.NONE,null,null);
    }
    _window(pid) {
        return global.get_window_actors().map(a=>a.meta_window).find(w=>
            w.get_pid()===pid && ['InkEcho isolated wayland','InkEcho isolated simple'].includes(w.get_title()));
    }
    Activate(pid) {
        const w=this._window(pid);if(!w)return false;
        Main.activateWindow(w);return global.display.focus_window===w;
    }
    _later(priority,callback) {
        let id=GLib.idle_add(priority,()=>{this._sources.delete(id);callback();return GLib.SOURCE_REMOVE;});
        this._sources.add(id);
    }
    TestAsync([mode,sourcePid,targetPid],invocation) {
        const source=this._window(sourcePid),target=this._window(targetPid),im=Main.inputMethod;
        if (!['inline','idle','contended','stable'].includes(mode) || !source || !target ||
            global.display.focus_window!==source || source.get_client_type()!==Meta.WindowClientType.WAYLAND ||
            !im?.currentFocus || typeof im.hasPreedit!=='function' || im.hasPreedit()) {
            invocation.return_value(new GLib.Variant('(sbx)',['not_attempted',false,0]));return;
        }
        const started=GLib.get_monotonic_time();const generation=this._generation;
        im.commit('甲'); // asynchronous: attempted, never a delivery ACK
        const finish=()=>invocation.return_value(new GLib.Variant('(sbx)',
            ['attempted',global.display.focus_window===target,GLib.get_monotonic_time()-started]));
        if(mode==='inline'){this.Activate(targetPid);finish();return;}
        if(mode==='contended')this._later(GLib.PRIORITY_HIGH,()=>{if(generation===this._generation)this.Activate(targetPid);});
        this._later(GLib.PRIORITY_DEFAULT_IDLE,()=>{
            if(generation!==this._generation){finish();return;}
            if(mode==='idle')this.Activate(targetPid);
            finish();
        });
    }
    disable() {
        this._generation++;
        for(const id of this._sources)GLib.source_remove(id);this._sources.clear();
        if(this._owner)Gio.bus_unown_name(this._owner);this._obj?.unexport();
    }
}
