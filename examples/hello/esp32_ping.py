# ESP32 server — copy library/uremote.py to the board.
# Pair with hub_ping_prime.py or hub_ping_ev3.py on a Pybricks hub.
from uremote import uRemote

ur = uRemote()

def hello(text):
    return f'ESP32 heard: {text}'

while 1:
    ur.process()
