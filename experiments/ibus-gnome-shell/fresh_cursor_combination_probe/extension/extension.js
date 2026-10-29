import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {getIBusManager} from 'resource:///org/gnome/shell/misc/ibusManager.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
const N='io.github.Creammmmm.InkEcho.MetadataCombination',P='/io/github/Creammmmm/InkEcho/MetadataCombination';
const XML=`<node><interface name="${N}1"><method name="Read"><arg type="s" direction="out"/></method></interface></node>`;
export default class Probe extends Extension {
enable(){this._epoch=0;this._path='';this._cursor=null;this._focusAt=0;this._events=[];this._manager=getIBusManager();this._panel=this._manager._panelService;this._ids=[];if(this._panel){
 for(const name of ['focus-in','focus-out','destroy-context'])this._ids.push(this._panel.connect(name,(_p,path)=>{this._epoch++;this._cursor=null;this._path=name==='focus-in'?path:'';this._focusAt=GLib.get_monotonic_time();this._events.push({kind:name,path,at:this._focusAt,epoch:this._epoch});}));
 for(const name of ['set-cursor-location','set-cursor-location-relative']){try{this._ids.push(this._panel.connect(name,(_p,x,y,w,h)=>{const d=this._manager._candidatePopup?._dummyCursor;const stage=d?[...d.get_position(),...d.get_size()]:null;this._cursor={kind:name,raw:[x,y,w,h],stage,epoch:this._epoch,at:GLib.get_monotonic_time()};this._events.push({...this._cursor});if(this._events.length>256)this._events.splice(0,this._events.length-256);}));}catch(_){}}
 }this._obj=Gio.DBusExportedObject.wrapJSObject(XML,this);this._obj.export(Gio.DBus.session,P);this._owner=Gio.bus_own_name_on_connection(Gio.DBus.session,N,Gio.BusNameOwnerFlags.NONE,null,null);}
Read(){const w=global.display.focus_window;const visible=this._manager._candidatePopup?._preeditText?.visible;return JSON.stringify({live:this._manager._panelService===this._panel&&!!this._panel,epoch:this._epoch,path:this._path,focusAt:this._focusAt,cursor:this._cursor,pid:w?.get_pid()??0,window:w?.get_id()??0,scale:w?.get_compositor_private()?.get_resource_scale()??0,preedit:typeof visible==='boolean'?visible:null,events:this._events});}
disable(){for(const id of this._ids)this._panel.disconnect(id);if(this._owner)Gio.bus_unown_name(this._owner);this._obj?.unexport();}
}
