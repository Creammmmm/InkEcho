import asyncio, json, subprocess, sys
from inkecho.platform.hybrid_keyboard import HybridKeyboardInput

mode = sys.argv[1]
active = True

def first_sent(_time):
    global active
    if mode == 'cancel':
        active = False
    if mode == 'switch':
        result = subprocess.run(['gdbus','call','--session','--dest','io.github.Creammmmm.InkEcho.WaylandFocusProbe','--object-path','/io/github/Creammmmm/InkEcho/WaylandFocusProbe','--method','io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Activate','InkEcho isolated wayland'], capture_output=True, text=True, timeout=5)
        print('switch', result.returncode, result.stdout.strip(), result.stderr.strip(), flush=True)

async def main():
    keyboard = HybridKeyboardInput()
    try:
        await keyboard.connect()
        await keyboard.authorize()
        print('authorized', keyboard.authorized, 'xonly', keyboard._xonly, flush=True)
        count = await keyboard.insert('风云Ω中', lambda: active, on_first_sent=first_sent)
        print('completed', count, flush=True)
    except Exception as e:
        print('error', type(e).__name__, getattr(e, 'code', ''), str(e), flush=True)
    finally:
        await keyboard.aclose()
asyncio.run(main())
