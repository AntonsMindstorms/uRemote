# EV3 client — copy library/uremote.py to the hub as uremote.py.
# Pair with esp32_ping.py on LMS-ESP32. Wire Port.S1 TX/RX to the ESP32.
from pybricks.parameters import Port
from uremote import uRemote, uRemoteError

ur = uRemote(Port.S1)

while True:
    try:
        print(ur.call('ping'))
    except uRemoteError as e:
        print('error:', e)
