# 05 Pulled plug: errors are clear, and the hub stays alive and recovers.
# Follow the prints: a slow handler, a crashing handler, then YOU unplug the
# cable for a few seconds. A blinker task must never stop, and calls must work
# again after you plug the cable back in.
from pybricks.hubs import PrimeHub
from pybricks.parameters import Icon, Port
from pybricks.tools import StopWatch, multitask, run_task, wait
from uremote import uRemote, uRemoteError

hub = PrimeHub()
ur = uRemote(Port.A, wait_recv=1000)

ticks = errors = ok_after_error = 0
watch = StopWatch()
results = {}


async def blinker():
    global ticks
    while watch.time() < 30000:
        hub.display.icon(Icon.HAPPY if ticks % 2 else Icon.SAD)
        ticks += 1
        await wait(250)


async def expect_error(label, cmd, words):
    try:
        await ur.call(cmd)
        results[label] = False
    except uRemoteError as e:
        print(label, "->", e)
        results[label] = words in str(e)


async def tester():
    global errors, ok_after_error
    await expect_error("slow handler", 'slow', "")        # times out
    await wait(1500)                                      # let the server finish
    await expect_error("crashing handler", 'boom', "explodes")
    print(">>> UNPLUG the cable now, plug it back in after ~5 s <<<")
    while watch.time() < 30000:
        try:
            await ur.call('add', 1, 1)
            if errors:
                ok_after_error += 1
        except uRemoteError as e:
            errors += 1
            print("caught:", e)
        await wait(500)


async def main():
    await multitask(blinker(), tester())

run_task(main())

print(results, "errors:", errors, "good calls after:", ok_after_error, "blinks:", ticks)
if all(results.values()) and errors and ok_after_error and ticks > 60:
    print("PASS")
else:
    print("FAIL: need every error to be a uRemoteError with a hint, the blinker to "
          "keep going (lock released), and calls to work again after replugging.")
