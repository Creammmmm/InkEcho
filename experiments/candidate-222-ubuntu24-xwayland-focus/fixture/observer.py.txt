import ctypes as c, json
from inkecho.platform.keyboard import _XDriver,KeyboardError
x=_XDriver()
try:
 raw=c.c_ulong();rv=c.c_int();x.x11.XGetInputFocus(x.display,c.byref(raw),c.byref(rv))
 active=x._property(x.root,x.active_atom)
 try: focus=x.focus(); code='ok'
 except KeyboardError as e: focus=None;code=e.code
 print(json.dumps({'raw_x_focus':raw.value,'active_window':active,'selected_focus':focus,'code':code}))
finally:x.close()
