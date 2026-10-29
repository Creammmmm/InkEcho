import os
import select
import time
import tty

tty.setraw(0)
with open("/tmp/inkecho-ibus-lf-received", "wb", buffering=0) as output:
    end = time.time() + 8
    while time.time() < end:
        if select.select([0], [], [], 0.1)[0]:
            output.write(os.read(0, 1024))
