# ESP32 server — copy library/uremote.py to the board.
# Pair with hub_ping_prime.py or hub_ping_ev3.py on a Pybricks hub.
from uremote import uRemote


def ping():
    return 42


ur = uRemote()

while True:
    ur.process()
