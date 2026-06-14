# OpenMV AE3 server — copy library/uremote.py to the AE3 as uremote.py.
# Pair with hub_ping_ev3.py on EV3. Wire Port.S1 TX/RX to the AE3.
from uremote import uRemote
import sys
print(sys.version)

ur = uRemote()

def hello(text):
    return f'OpenMV heard: {text}'

while 1:
    ur.process()