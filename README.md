<div align="center">
<img alt="uRemote logo" src="https://raw.githubusercontent.com/AntonsMindstorms/uRemote/main/docs/uremote.png" width="200">

# uRemote

uRemote is a small UART RPC library for pairing **Pybricks LEGO hubs** with **LMS-ESP32 / MicroBlocks** devices. One side defines plain functions; the other side calls them over serial.

Typical setup: a Pybricks hub is the **client** (`call`) and an ESP32 running MicroPython or MicroBlocks is the **server** (`process`).

The wire format is a stripped-down version of the [UARTRemote](https://github.com/scopeland-UARTRemote) protocol.

</div>

## Getting started

### 1. Flash Pybricks firmware with UARTDevice

Standard Pybricks firmware does not include `UARTDevice`. Use a patched build from this repo:

1. Clone or download this repository locally.
2. Open the [Pybricks code editor](https://code.pybricks.com) and put your hub in firmware update mode.
3. Enable **Advanced options** → **Use local firmware file**.
4. Select the firmware for your hub from [`pybricks_firmware/`](pybricks_firmware/).

See [`pybricks_firmware/old_firmwares/README.md`](pybricks_firmware/old_firmwares/README.md) for platform-specific notes. If you power NeoPixels or servos from the hub port, use the [`UARTDevice_power_pin`](pybricks_firmware/UARTDevice_power_pin/) patch.

### 2. Copy the library

Copy [`library/uremote.py`](library/uremote.py) to your Pybricks hub project as `uremote.py`.

For MicroBlocks on the ESP32 side, import the [`library/uremote.ubl`](library/uremote.ubl) library.

### 3. Wire the devices

Connect the hub UART port to the ESP32 (cross TX/RX, common GND):

```
Hub TX  ──► ESP32 RX
Hub RX  ◄── ESP32 TX
GND     ─── GND
```

Use an **input port** on the hub:

| Hub | Typical port in examples |
|-----|--------------------------|
| EV3 | `Port.S1`, `Port.S2`, … |
| SPIKE Prime / Technic | `Port.A`, `Port.B`, … |

Default baud rate is **115200** on both sides.

### 4. Hello world

**ESP32 (server)** — define a handler and run `process()` in a loop:

```python
from uremote import uRemote

def ping():
    return 42

ur = uRemote()

while True:
    ur.process()
```

**Pybricks hub (client)** — call the remote function:

```python
from pybricks.parameters import Port
from uremote import uRemote, uRemoteError

ur = uRemote(Port.A)

try:
    answer = ur.call('ping')
    print(answer)   # 42
except uRemoteError as e:
    print('failed:', e)
```

More examples are in [`examples/`](examples/) (joystick, IMU, LED, line sensor). Minimal pairs are in [`examples/hello/`](examples/hello/).

---

## Python API

Create one shared `uRemote` instance per program:

```python
from pybricks.parameters import Port
from uremote import uRemote

ur = uRemote(Port.A)          # Pybricks hub
ur = uRemote()                # ESP32 (uses LMS-ESP32 default pins)
```

### Client: `call(cmd, *args)`

Send a command and wait for the reply. On success, returns the answer directly. On failure, raises `uRemoteError`.

```python
x, y, pressed = ur.call('joy')   # multiple return values → tuple
data = ur.call('sen')              # single value → that value
ur.call('led', -1)                 # no return value → None
```

| Response payload | `call()` returns |
|------------------|------------------|
| nothing | `None` |
| one value | the value (`42`, `b'...'`, `True`, …) |
| multiple values | tuple `(x, y, z)` |

```python
from uremote import uRemoteError

try:
    x, y, z = ur.call('imu')
except uRemoteError as e:
    print(e)   # e.g. "no bytes received", "handler not found: imu"
```

`call()` checks that the reply command matches the request and that the status byte is `0`. You never handle status bytes or command suffixes yourself.

### Server: `process()`

Receive one command, call a **same-named function** in your main program, and send back the result:

```python
def led(updown):
    # ...
    return

ur = uRemote()

while True:
    ur.process()
```

Handler return values are sent with status `0`:

- `return` / `None` → status `0`, no data fields
- `return 42` → status `0`, one number
- `return x, y, z` → status `0`, three numbers

If no matching function exists, the server replies with status `1` and an error string.

### Advanced: `exchange()`

For debugging, use `exchange()` to send a command and get the raw `(status, cmd, payload)` tuple without validation:

```python
status, cmd, data = ur.exchange('test', 1, 2)
```

### Constructor options

```python
ur = uRemote(
    Port.A,           # Pybricks port, or UART id on ESP32
    baudrate=115200,
    wait_recv=1000,   # overall frame receive timeout (ms)
    uart_timeout=1000,# per-read UART timeout (ms)
    power_pin=2,      # Pybricks only: 8V on P1 (1) or P2 (2); 0 = off
)
```

On Pybricks hubs with the [`UARTDevice_power_pin`](pybricks_firmware/UARTDevice_power_pin/) firmware patch, `power_pin` enables 8V on P1 (`1`) or P2 (`2`). Default is `2`, which matches LMS-ESP32 and SPIKE-OPENMV wiring. Set to `0` to leave P1/P2 unpowered. This argument is ignored on ESP32.

8V power is only switched on **while your program is running** — it turns off when the program stops. The **first time** you request 8V power in a program, Pybricks will prompt you on the hub to confirm.

Inter-byte timeout (`byte_timeout`) is fixed at **10 ms**.

---

## MicroBlocks API

Import the `uremote` library on the ESP32/MicroBlocks side.

| Block | Role |
|-------|------|
| `uremote init` | Open serial at 115200 baud |
| `uremote call` | Client: send command, return data |
| `uremote last error` | Reporter: last error from `call` (empty on success) |
| `uremote process` | Server: receive command, call handler, send reply |

MicroBlocks `call` returns **data only** and does not raise exceptions. After a failed `call`, read **`uremote last error`** — e.g. `"timeout: no length byte"`, `"preamble mismatch"`, `"handler not found"`.

**Fixed timeouts (MicroBlocks only):** receive wait **1000 ms**, inter-byte gap **10 ms**. These are not configurable in `.ubl`; Python uses `wait_recv` and `byte_timeout` on the constructor instead.

---

## Request / response lifecycle

When the hub calls `ur.call('joy')`:

1. Hub sends status `0`, command `"joy"`, and optional arguments.
2. Server runs `process()`, which calls function `joy(...)` in the main script.
3. On success, server replies with status `0`, command `"joy"`, and return values.
4. On failure, server replies with status `1`, command `"joy"`, and an error string.
5. Python `call()` checks the command name and status byte, then returns the payload or raises `uRemoteError`.

Transport failures (timeout, bad preamble, decode error) never produce a valid frame. Python reports them as distinct `uRemoteError` messages (`timeout: no length byte`, `preamble mismatch`, `timeout: incomplete frame`, `timeout: inter-byte gap`, `decode error: …`). The synthetic cmd name `"!ERROR"` is never sent on the wire.

Payloads that exceed the 255-byte frame limit raise `uRemoteError("frame too large")` at send time.

---

## Supported data types

| Type | Wire code | Encoding |
|------|-----------|----------|
| Number | `N` (78) | UTF-8 decimal string |
| String | `S` (83) | UTF-8 text |
| Boolean | `B` (66) | `0x00` = False, `0x01` = True |
| ByteArray | `A` (65) | raw bytes |

Unknown Python types passed to `encode()` raise `TypeError`.

---

## Protocol format

Each UART frame:

```
<tot_len> <PREAMBLE> <hdr> <cmd> [<type> <data_len> <data> ...]
```

- **tot_len** — total bytes in the frame (including preamble), max **255**
- **PREAMBLE** — fixed sync bytes: `<$MU`
- **hdr** — one byte: upper 3 bits = status, lower 5 bits = cmd length (max **31**)
- **cmd** — command name as UTF-8 text (same name on request and reply)

Status values: `0` = OK, `1` = error reply.

Example request `joy(100, 200)` and success reply `joy → (42)`:

```
hdr=joy_len "joy"  N 3 "100"  N 3 "200"     ← request (status 0)
hdr=joy_len "joy"  N 2 "42"                  ← reply   (status 0)
```

Example error reply:

```
hdr=joy_len "joy"  S 19 "handler not found"  ← reply (status 1)
```

### Robust receive handling

Incoming data is read one byte at a time until a complete frame arrives or a timeout occurs.

- **Overall receive timeout:** `wait_recv`
- **UART read timeout:** `uart_timeout`
- **Inter-byte timeout:** `byte_timeout` (10 ms)

If the preamble does not match, the UART buffer is flushed and the frame is discarded so the receiver can resync after noise or partial frames.

---

## Repository layout

| Path | Purpose |
|------|---------|
| [`library/uremote.py`](library/uremote.py) | Pybricks + ESP32 MicroPython library |
| [`library/uremote.ubl`](library/uremote.ubl) | MicroBlocks library |
| [`examples/hello/`](examples/hello/) | Minimal hub + ESP32 ping pair |
| [`examples/`](examples/) | Joystick, IMU, LED, line sensor demos |
| [`pybricks_firmware/`](pybricks_firmware/) | Patched firmware with `UARTDevice` |
| [`tests/speed/`](tests/speed/) | UART throughput tests |

Copy `library/uremote.py` to your hub — do not use old copies from example folders.
