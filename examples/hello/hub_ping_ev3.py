# EV3 client — copy library/uremote.py to the hub as uremote.py.
# Pair with esp32_ping.py on LMS-ESP32. Wire Port.S1 TX/RX to the ESP32.


from uremote import uRemote, uRemoteError
from pybricks.parameters import Port
from pybricks.tools import StopWatch

ur = uRemote(Port.S1)

w = StopWatch()
for i in range(50):
    try:
        print(ur.call('hello', 'Anyone there?'))
    except uRemoteError as e:
        print('error:', e)
print('Elapsed ms for 50 calls: ', w.time())

