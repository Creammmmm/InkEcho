import Gio from 'gi://Gio';
import IBus from 'gi://IBus';
import {getIBusManager} from 'resource:///org/gnome/shell/misc/ibusManager.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
const NAME = 'io.github.inkecho.IsolatedPreedit';
const PATH = '/io/github/inkecho/IsolatedPreedit';
const XML = `<node><interface name="${NAME}"><method name="Key"><arg type="u" direction="in"/><arg type="b" direction="out"/></method><method name="Commit"><arg type="s" direction="in"/><arg type="b" direction="out"/></method></interface></node>`;
export default class Probe extends Extension {
    enable() {
        this.obj = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this.obj.export(Gio.DBus.session, PATH);
        this.owner = Gio.bus_own_name_on_connection(Gio.DBus.session, NAME, Gio.BusNameOwnerFlags.NONE, null, null);
    }
    Key(key) {
        const panel = getIBusManager()._panelService;
        if (!panel || ![32, 110, 105].includes(key)) return false;
        panel.forward_process_key_event(key, 0, 0);
        return true;
    }
    Commit(text) {
        const panel = getIBusManager()._panelService;
        if (!panel || !['甲', '乙'].includes(text)) return false;
        panel.commit_text(IBus.Text.new_from_string(text));
        return true;
    }
    disable() { Gio.bus_unown_name(this.owner); this.obj.unexport(); }
}
