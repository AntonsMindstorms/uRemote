# uRemote Async

`uRemote` is a small UART-based RPC library for MicroPython targets such as
Pybricks hubs and ESP32 boards.

This version adds cooperative asynchronous RPC calls for Pybricks while keeping
the existing synchronous API and wire protocol compatible with the previous
uRemote implementation.

Current version:

```text
1.3.1-async-read
```

## What is new

The library now supports:

```python
await ur.call_async(...)
await ur.exchange_async(...)
```

These methods are intended for programs that use Pybricks
`multitask()` / `run_task()` and need more than one coroutine to use the same
uRemote connection.

The existing synchronous methods remain available:

```python
ur.call(...)
ur.exchange(...)
ur.process()
```

The UART protocol itself has not changed.

This means an ESP32 running the remote/server side does **not** need to become
asynchronous just because the Pybricks caller uses `call_async()`.

---

## Why asynchronous support is needed

A normal synchronous uRemote call performs one complete transaction:

```text
send command
wait for reply
decode reply
return result
```

With a synchronous `call()`, waiting for the UART reply can prevent other
Pybricks tasks from running.

`call_async()` allows Pybricks to yield to other coroutines while waiting for
UART activity.

For example:

```python
value = await ur.call_async("motor")
```

While uRemote is waiting for the ESP32 reply, another Pybricks coroutine can
run.

---

## Transaction locking

uRemote uses a single UART connection with a request/reply protocol.

Two RPC calls must therefore not overlap like this:

```text
Task 1 -> send "Kp"
Task 2 -> send "motor"
Task 2 <- receive reply for "Kp"
Task 1 <- receive reply for "motor"
```

That would associate replies with the wrong requests.

The async implementation therefore contains a cooperative transaction lock.

A complete RPC operation is serialized:

```text
acquire lock
    send command
    wait for reply
    decode reply
release lock
```

Only one uRemote RPC transaction can be active at a time.

Other Pybricks tasks are still free to run while that transaction is waiting
for UART data.

The lock is released in a `finally` block, so it is also released when a call
times out or raises an exception.

---

## Pybricks UART handling

On Pybricks, UART operations used inside an async task must be handled
asynchronously.

In particular, this library uses:

```python
await self.uart.write(...)
await self.uart.read(...)
```

in the asynchronous code path.

The synchronous code path uses separate synchronous helpers.

This separation is important because calling `UARTDevice.read()` from an async
context without awaiting it can return a Pybricks `Async` object instead of the
received bytes.

The library therefore has distinct byte readers:

```python
_read_byte_sync()
_read_byte_async()
```

The async receive implementation always uses:

```python
await self._read_byte_async()
```

---

## Basic architecture

A typical setup consists of:

```text
Pybricks hub                 ESP32
-------------                -----

call_async("motor")   --->   process()
                              |
                              +-- calls motor()
                              |
                     <---     reply
```

The Pybricks side is normally the RPC caller.

The ESP32 side normally runs `process()` repeatedly and executes functions
defined in its main program.

---

# Pybricks example

```python
from pybricks.hubs import PrimeHub
from pybricks.parameters import Axis, Direction, Port
from pybricks.pupdevices import Motor
from pybricks.tools import multitask, run_task, wait

from uremote_async import uRemote


prime_hub = PrimeHub()
ur = uRemote("A")

motor = Motor(Port.F, Direction.CLOCKWISE)
dc_pct = 0


async def telemetry_task():
    while True:
        await ur.call_async(
            "spike_data",
            round(prime_hub.imu.rotation(Axis.X)),
            round(prime_hub.imu.rotation(Axis.Y)),
            round(prime_hub.imu.rotation(Axis.Z)),
        )

        kp = await ur.call_async("Kp")
        print(kp)

        # Give other RPC users an opportunity to acquire the
        # uRemote transaction lock.
        await wait(0)


async def motor_task():
    global dc_pct

    prime_hub.imu.reset_heading(0)

    while True:
        dc_pct = await ur.call_async("motor")
        motor.dc(dc_pct)

        await wait(0)


async def main():
    await multitask(
        telemetry_task(),
        motor_task(),
    )


run_task(main())
```

Both tasks use the same `uRemote` instance:

```python
ur = uRemote("A")
```

This is intentional. The internal transaction lock coordinates access to that
single UART connection.

---

# ESP32 example

The ESP32 remote side can remain synchronous.

For example:

```python
from uremote_async import uRemote


ur = uRemote(1)


_motor_value = 0
_kp = 25


def motor():
    return _motor_value


def Kp():
    return _kp


def spike_data(x, y, z):
    print("rotation:", x, y, z)


while True:
    ur.process()
```

No `uasyncio` loop is required for this normal server use case.

When the ESP32 receives:

```python
await ur.call_async("motor")
```

from Pybricks, the bytes received by the ESP32 are the same as they would be
for:

```python
ur.call("motor")
```

The difference exists only on the caller side: the async version cooperatively
yields while waiting.

---

# `call_async()`

Use:

```python
result = await ur.call_async("command", arg1, arg2)
```

Example:

```python
speed = await ur.call_async("motor")
```

or:

```python
await ur.call_async("spike_data", x, y, z)
```

`call_async()`:

1. waits for the async transaction lock,
2. sends the command,
3. waits asynchronously for the reply,
4. validates the reply command,
5. unwraps the returned payload,
6. releases the transaction lock.

It has the same result semantics as synchronous `call()`.

For example, a remote function returning:

```python
return 42
```

produces:

```python
value = await ur.call_async("foo")
# value == 42
```

---

# `exchange_async()`

Use:

```python
status, command, payload = await ur.exchange_async(
    "command",
    arg1,
    arg2,
)
```

This is the asynchronous equivalent of:

```python
status, command, payload = ur.exchange(
    "command",
    arg1,
    arg2,
)
```

It exposes the raw decoded reply instead of validating and unwrapping it like
`call_async()` does.

---

# Synchronous API

The original API remains available.

## `call()`

```python
result = ur.call("motor")
```

Use this in simple single-loop programs that are not using the Pybricks async
task model.

## `exchange()`

```python
status, command, payload = ur.exchange("motor")
```

This returns the decoded raw RPC response.

## `process()`

```python
ur.process()
```

This processes one incoming RPC command if UART data is available.

It is intended primarily for the remote/server side.

Typical ESP32 loop:

```python
while True:
    ur.process()
```

---

# Mixing synchronous and asynchronous calls

Avoid mixing:

```python
ur.call(...)
```

and:

```python
await ur.call_async(...)
```

on the same `uRemote` instance while multiple async tasks are active.

The async transaction lock protects async calls from other async calls, but a
synchronous `call()` does not participate in that cooperative lock.

In a Pybricks multitasking application, prefer using `call_async()` consistently
for RPC traffic.

---

# Fairness between tasks

The internal lock guarantees transaction correctness, but it is intentionally
simple.

After a task finishes an RPC call, it can be useful to explicitly yield:

```python
await wait(0)
```

For example:

```python
async def task1():
    while True:
        value = await ur.call_async("foo")
        await wait(0)
```

This gives another coroutine an opportunity to acquire the uRemote transaction
lock before the current task starts its next RPC transaction.

---

# Timeouts

The existing timeout behavior remains in place.

Constructor example:

```python
ur = uRemote(
    "A",
    baudrate=115200,
    wait_recv=1000,
    uart_timeout=1000,
)
```

`wait_recv` controls how long uRemote waits for a complete RPC response.

The library also uses an inter-byte timeout while receiving frames.

Timeout and receive errors raise `uRemoteError` when using `call()` or
`call_async()`.

Example:

```python
from uremote_async import uRemote, uRemoteError


try:
    speed = await ur.call_async("motor")
except uRemoteError as exc:
    print("uRemote error:", exc)
```

---

# Supported argument types

The current protocol supports:

- `bool`
- `int`
- `bytes`
- `str`

Example:

```python
await ur.call_async(
    "update",
    True,
    123,
    b"abc",
    "hello",
)
```

Other argument types raise `TypeError`.

---

# Return values

A remote function can return nothing:

```python
def reset():
    return
```

or one value:

```python
def motor():
    return 50
```

or a tuple:

```python
def position():
    return 10, 20, 30
```

The caller receives:

```python
await ur.call_async("reset")
# None

await ur.call_async("motor")
# 50

await ur.call_async("position")
# (10, 20, 30)
```

---

# Remote function discovery

`process()` looks for functions in the remote board's `__main__` module.

For example:

```python
def motor():
    return 50
```

can be called remotely with:

```python
speed = await ur.call_async("motor")
```

If the requested function does not exist, the remote returns an error and the
caller raises `uRemoteError`.

---

# Using async calls on ESP32

The normal ESP32 server does not need async support.

However, the library also contains a generic async yield path for non-Pybricks
targets using `uasyncio`.

That means an ESP32 can potentially act as an asynchronous caller using:

```python
await ur.call_async(...)
```

provided that `uasyncio` is available.

For the normal architecture:

```text
Pybricks caller -> ESP32 server
```

this feature is not required.

---

# Compatibility

The async implementation is designed to preserve compatibility with the
existing uRemote protocol.

In particular:

- frame format is unchanged;
- command encoding is unchanged;
- reply encoding is unchanged;
- `process()` behavior is unchanged;
- existing synchronous applications can continue using `call()`;
- an existing ESP32 uRemote server can communicate with a Pybricks
  `call_async()` client.

This means async support is primarily an implementation/API enhancement rather
than a protocol revision.

---

# Recommended usage

For a traditional single-loop program:

```python
value = ur.call("foo")
```

For a Pybricks program using `multitask()`:

```python
value = await ur.call_async("foo")
```

For an ESP32 acting as the remote RPC server:

```python
while True:
    ur.process()
```

When multiple Pybricks tasks share uRemote, use one shared `uRemote` object:

```python
ur = uRemote("A")
```

and use `call_async()` consistently from all of those tasks.

---

# Version check

When debugging deployments, it can be useful to verify which library file is
actually running.

```python
import uremote_async

print(uremote_async.__version__)
```

For this release it should print:

```text
1.3.1-async-read
```

This is especially useful on Pybricks if multiple copies or differently named
versions of `uremote.py` / `uremote_async.py` have been transferred to the
hub.

---

# Summary

The async extension keeps uRemote's simple request/reply design:

```text
Pybricks async task
        |
        | await call_async()
        v
     uRemote
        |
        | UART
        v
      ESP32
        |
        | process()
        v
 remote function
```

The key design choices are:

- asynchronous UART reads and writes on Pybricks;
- cooperative yielding while waiting for data;
- serialization of complete RPC transactions;
- no change to the wire protocol;
- no requirement for an async ESP32 server;
- full retention of the existing synchronous API.

This makes uRemote usable from cooperative Pybricks multitasking programs
without allowing concurrent RPC calls to corrupt request/reply pairing.
