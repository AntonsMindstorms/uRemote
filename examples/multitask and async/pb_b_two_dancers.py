# 02 Two dancers: two tasks share one uRemote under run_task()/multitask().
# One task animates the light matrix, the other keeps asking the ESP32 to add.
# Pass: both keep making progress for DURATION ms and no reply is wrong, which
# proves the lock stops tasks from stealing each other's answers.
from pybricks.hubs import PrimeHub
from pybricks.parameters import Icon, Port
from pybricks.tools import StopWatch, multitask, run_task, wait
from uremote import uRemote, uRemoteError

hub = PrimeHub()
ur = uRemote(Port.A)

DURATION = 20000
frames = calls = wrong = 0
watch = StopWatch()


async def dancer():
    global frames
    while watch.time() < DURATION:
        hub.display.pixel(frames // 5 % 5, frames % 5, 100)
        hub.display.pixel((frames - 1) // 5 % 5, (frames - 1) % 5, 0)
        frames += 1
        await wait(50)


async def asker():
    global calls, wrong
    while watch.time() < DURATION:
        try:
            if await ur.call('add', calls, calls) != 2 * calls:
                wrong += 1
        except uRemoteError as e:
            wrong += 1
            print("call failed:", e)
        calls += 1
        await wait(0)  # let the dancer have a turn


async def main():
    await multitask(dancer(), asker())

run_task(main())

print("dancer frames:", frames, "asker calls:", calls, "wrong:", wrong)
if wrong == 0 and frames > 100 and calls > 100:
    hub.display.icon(Icon.HAPPY)
    print("PASS")
else:
    hub.display.icon(Icon.SAD)
    print("FAIL: a task starved or replies got mixed up. Does every call use `await`?")
