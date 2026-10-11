# ESP32 / OpenMV as CLIENT: plain MicroPython has no run_task(), so call()
# must simply block and return values. Wire this board's UART to another board
# running esp32_playground.py (TX<->RX crossed, common ground).
# Pass: "PASS", and free memory about the same as on main (see README.md).
import gc
import uremote
from uremote import uRemote, uRemoteError

ur = uRemote()
gc.collect()
before = gc.mem_free()

wrong = 0
for i in range(200):
    if ur.call('add', i, i) != 2 * i:
        wrong += 1
print("200 calls, wrong:", wrong)

errors_ok = 0
for cmd, words in (('boom', 'explodes'), ('no_such_command', 'not found')):
    try:
        ur.call(cmd)
    except uRemoteError as e:
        print(cmd, "->", e)
        errors_ok += words in str(e)

gc.collect()
print("run_task is None (as expected off Pybricks):", uremote.run_task is None)
print("free memory before/after:", before, gc.mem_free())
if wrong == 0 and errors_ok == 2 and uremote.run_task is None:
    print("PASS")
else:
    print("FAIL: blocking call() or error reporting is broken on this board.")
