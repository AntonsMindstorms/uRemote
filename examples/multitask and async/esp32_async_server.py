# ESP32 server written with asyncio, so it can do other work while serving.
# Pair with e_async_esp32.py on the hub. Copy library/uremote.py to the board.
#
# How it fits together: ur.process() is synchronous but returns immediately
# when no request is waiting, so it is polled from one asyncio task and every
# other task gets the CPU in between. Handlers (add, beat, ...) are plain
# functions: while one runs, nothing else does. So keep handlers short, and let
# long jobs run as background tasks that a handler starts and another handler
# reads (see start_countdown / countdown below).
import asyncio
from uremote import uRemote

ur = uRemote()

beats = 0             # incremented by the heartbeat task
countdown_left = 0    # set by start_countdown(), ticked down by a worker task


def add(a, b):
    return a + b


def beat():
    return beats


def start_countdown(n):
    # Returns at once; the worker task does the slow part.
    global countdown_left
    countdown_left = n
    return n


def countdown():
    return countdown_left


async def serve():
    while True:
        ur.process()
        await asyncio.sleep_ms(0)


async def heartbeat():
    global beats
    while True:
        beats += 1
        await asyncio.sleep_ms(10)


async def countdown_worker():
    global countdown_left
    while True:
        if countdown_left > 0:
            await asyncio.sleep_ms(100)
            countdown_left -= 1
        else:
            await asyncio.sleep_ms(10)


async def main():
    await asyncio.gather(serve(), heartbeat(), countdown_worker())

print("async server ready")
asyncio.run(main())
