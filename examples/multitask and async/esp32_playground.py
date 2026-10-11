# Server for all the multitask and async examples. Run on the LMS-ESP32 (or any MicroPython
# ESP32 wired to the hub). Copy library/uremote.py to the board as uremote.py.
import time
from uremote import uRemote

ur = uRemote()


def add(a, b):
    return a + b


def Kp():
    return 42


def hello(name):
    return "hello " + name


def slow():
    # Longer than the client's wait_recv, so the client must time out politely.
    time.sleep_ms(1500)
    return 1


def boom():
    raise ValueError("this handler always explodes")


print("playground ready")
while True:
    ur.process()
