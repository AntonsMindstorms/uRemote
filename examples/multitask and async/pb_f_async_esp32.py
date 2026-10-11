# e Async ESP32: the ESP32 side runs asyncio (esp32_async_server.py) and keeps
# doing its own work while answering. The hub side stays plain blocking code,
# which shows that both ends choose sync or async independently.
# Pass: the ESP32 heartbeat kept ticking while it served calls, and a 1 s
# background countdown finished while it stayed responsive.
from pybricks.hubs import PrimeHub
from pybricks.parameters import Icon, Port
from pybricks.tools import StopWatch, wait
from uremote import uRemote, uRemoteError

hub = PrimeHub()
ur = uRemote(Port.A)

try:
    # Part 1: 200 quick calls. The server's heartbeat task must advance meanwhile.
    before = ur.call('beat')
    wrong = sum(ur.call('add', i, i) != 2 * i for i in range(200))
    beats_during = ur.call('beat') - before
    print("heartbeats during 200 calls:", beats_during, "wrong replies:", wrong)

    # Part 2: start a slow job and poll it. Every poll must be answered quickly.
    ur.call('start_countdown', 10)
    watch, slowest = StopWatch(), 0
    while ur.call('countdown') > 0 and watch.time() < 3000:
        t = watch.time()
        ur.call('add', 1, 1)
        slowest = max(slowest, watch.time() - t)
        wait(50)
    finished = ur.call('countdown') == 0
    print("countdown finished:", finished, "slowest call (ms):", slowest)
except uRemoteError as e:
    print("call failed:", e)
    beats_during, wrong, finished, slowest = 0, 1, False, 9999

if beats_during > 5 and wrong == 0 and finished and slowest < 200:
    hub.display.icon(Icon.HAPPY)
    print("PASS")
else:
    hub.display.icon(Icon.SAD)
    print("FAIL: is esp32_async_server.py running (not esp32_playground.py)? "
          "A slow handler blocks the whole ESP32 loop; keep handlers short.")
