# 06 Gamepad rave: BluePad under run_task(). Needs an LMS-ESP32 with the
# BluePad32 uRemote firmware on Port.A (NOT esp32_playground.py).
# One task shows the left stick as a dot on the light matrix, another cycles
# the NeoPixels through colours - both talk to the same board at once.
# No gamepad? The dot dances by itself. Set SYNC = True to run the same thing
# without run_task() and check nothing regressed for classic blocking users.
from pybricks.hubs import PrimeHub
from pybricks.parameters import Icon, Port
from pybricks.tools import StopWatch, multitask, run_task, wait
from bluepad_ur import BluePad

SYNC = False
DURATION = 20000

hub = PrimeHub()
bp = BluePad(Port.A)
watch = StopWatch()
pad_reads = pixel_writes = 0
COLORS = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0))


def show(lx, ly, t):
    if lx == ly == 0:  # no stick input or no pad: dance
        lx, ly = (t % 5 - 2) * 40, ((t // 5) % 5 - 2) * 40
    hub.display.off()
    hub.display.pixel(min(4, max(0, 2 + ly // 40)), min(4, max(0, 2 + lx // 40)), 100)


async def pad_task():
    global pad_reads
    while watch.time() < DURATION:
        lx, ly, rx, ry, buttons, dpad = await bp.gamepad()
        show(lx, ly, pad_reads)
        pad_reads += 1
        await wait(0)


async def pixel_task():
    global pixel_writes
    while watch.time() < DURATION:
        await bp.neopixel_fill(COLORS[pixel_writes % 4])
        pixel_writes += 1
        await wait(100)


async def main():
    await multitask(pad_task(), pixel_task())


if SYNC:
    while watch.time() < DURATION:
        lx, ly = bp.gamepad()[:2]
        show(lx, ly, pad_reads)
        bp.neopixel_fill(COLORS[pad_reads % 4])
        pad_reads += 1
        pixel_writes = pad_reads
else:
    run_task(main())

print("pad reads:", pad_reads, "pixel writes:", pixel_writes)
if pad_reads > 50 and pixel_writes > 50:
    hub.display.icon(Icon.HAPPY)
    print("PASS")
else:
    hub.display.icon(Icon.SAD)
    print("FAIL: too few calls. Is the BluePad32 uRemote firmware running on Port.A?")
