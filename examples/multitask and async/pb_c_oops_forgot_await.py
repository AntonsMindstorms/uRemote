# 04 Oops, I forgot await: the classic mistake must be loud, not silent.
# Part 1: call without await, twice. The second call must raise an error that
#         tells the user to write `await`.
# Part 2: correct code, two tasks starting at the same time, must NOT trip it.
# Part 3: print(ur.call(...)) without await must show a hint, not an opaque
#         "<generator object>" (this is what Pybricks blocks users hit).
# Pass: party face and "PASS". Also proves run_task() detection works on this
# firmware version.
from pybricks.hubs import PrimeHub
from pybricks.parameters import Icon, Port
from pybricks.tools import multitask, run_task
from uremote import uRemote, uRemoteError

hub = PrimeHub()
ur = uRemote(Port.A)


# run_task() does not hand back the coroutine's return value, so results
# are stored in this dict.
results = {}


async def forgot_await():
    ur.call('hello', 'nobody')          # oops: no await, nothing is sent
    try:
        ur.call('hello', 'me')          # this one must complain
    except uRemoteError as e:
        print("caught:", e)
        results['caught'] = "await" in str(e)


async def asker(name):
    return await ur.call('hello', name)


async def print_instead_of_await():
    shown = str(ur.call('hello', 'print me'))   # no await
    print("printed:", shown)
    results["shown"] = "Use await" in shown


async def both_at_once():
    results['replies'] = await multitask(asker('left'), asker('right'))


run_task(forgot_await())
caught = results.get('caught')
print("Part 1 (forgotten await is reported):", caught)

# A fresh, correct program must work right after the mistake.
run_task(both_at_once())
replies = results.get('replies')
print("Part 2 (parallel awaits are fine):", replies)

# Last, because it deliberately leaves one call un-awaited.
run_task(print_instead_of_await())
shown = results.get('shown')
print("Part 3 (printing a forgotten await explains itself):", shown)

if caught and shown and replies == ('hello left', 'hello right'):
    hub.display.icon(Icon.HAPPY)
    print("PASS")
else:
    hub.display.icon(Icon.SAD)
    print("FAIL: part 1 means the guard is silent; part 2 means it fires falsely. "
          "Part 3 failing means the hint object is not used on this firmware. "
          "If part 2 fails, see the `_unawaited` comment in uremote.py `_drive()`.")
