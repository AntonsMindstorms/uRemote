# 01 Ping-pong: blocking call() works and is fast.
# Hub: Pybricks Prime/Technic hub, ESP32 on Port.A running esp32_playground.py.
# Pass: smiley on the hub and "PASS". Compare calls/s with the baseline you
# recorded from main (see README.md) - it should be within about 10%.
from pybricks.hubs import PrimeHub
from pybricks.parameters import Icon, Port
from pybricks.tools import StopWatch, wait
from uremote import uRemote, uRemoteError

hub = PrimeHub()
ur = uRemote(Port.A)

N = 1000
wrong = 0
watch = StopWatch()
try:
    for i in range(N):
        if ur.call('add', i, 1) != i + 1:
            wrong += 1
        print(i)
except uRemoteError as e:
    wrong += 1
    print("call failed:", e)
ms = max(watch.time(), 1)

print("%d calls in %d ms = %d calls/s, %d wrong" % (i+1, ms, N * 1000 // ms, wrong))
if wrong == 0:
    hub.display.icon(Icon.HAPPY)
    print("PASS")
    wait(1000)
else:
    hub.display.icon(Icon.SAD)
    print("FAIL: wrong or failed replies. Is esp32_playground.py running? Same baudrate?")
    wait(1000)