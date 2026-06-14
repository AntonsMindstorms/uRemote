# Prime / Technic hub client — copy library/uremote.py to the hub as uremote.py.
# Pair with esp32_ping.py on LMS-ESP32. Wire Port.A TX/RX to the ESP32.
from pybricks.parameters import Port
from uremote import uRemote, uRemoteError

ur = uRemote(Port.A)

while True:
    try:
        print(ur.call('ping'))
    except uRemoteError as e:
        print('error:', e)
