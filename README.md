# uRemote

uRemote is a small UART RPC library for pairing **Pybricks LEGO hubs** with **LMS-ESP32 / MicroBlocks** devices. One side defines plain functions; the other side calls them over serial.

Typical setup: a Pybricks hub is the **client** (`call`) and an ESP32 running MicroPython or MicroBlocks is the **server** (`process`).

The wire format is a stripped-down version of the [UARTRemote](https://github.com/scopeland-UARTRemote) protocol.

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

More examples are in [`examples/`](examples/) (joystick, IMU, LED, line sensor).

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

`call()` checks the reply command internally — you do not need to inspect `_ack` or `_err` names yourself.

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

Handler return values are sent as the ack payload:

- `return` / `None` → empty ack
- `return 42` → one number
- `return x, y, z` → three numbers

If no matching function exists, the server sends `{cmd}_err` with `"handler not found: …"`.

### Advanced: `exchange()` and `receive_command()`

For debugging or custom protocols, use the low-level methods that return the raw `(reply_cmd, payload)` tuple without validation:

```python
cmd, data = ur.exchange('test', 1, 2)   # send + receive
cmd, data = ur.receive_command()        # receive only
```

### Constructor options

```python
ur = uRemote(
    Port.A,           # Pybricks port, or UART id on ESP32
    baudrate=115200,
    wait_recv=1000,   # overall frame receive timeout (ms)
    uart_timeout=1000,# per-read UART timeout (ms)
)
```

Inter-byte timeout (`byte_timeout`) is fixed at **10 ms**.

---

## MicroBlocks API

Import the `uremote` library on the ESP32/MicroBlocks side.

| Block | Role |
|-------|------|
| `uremote init` | Open serial at 115200 baud |
| `uremote call` | Client: send command, return data |
| `uremote process` | Server: receive command, call handler, send ack |

MicroBlocks `call` returns **data only** (no command name). On failure it returns empty/nothing — it does not raise exceptions like Python. Plan error checks accordingly when teaching both platforms.

---

## Request / response lifecycle

When the hub calls `ur.call('joy')`:

1. Hub sends command `"joy"` with optional arguments.
2. Server runs `process()`, which calls function `joy(...)` in the main script.
3. On success, server replies with command `"joy_ack"` and return values.
4. On failure, server replies with `"joy_err"` and an error string.
5. Python `call()` validates the reply and returns the payload or raises `uRemoteError`.

You only name the base command (e.g. `"joy"`). The `_ack` / `_err` suffixes are added automatically.

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
<tot_len> <PREAMBLE> <len_cmd> <cmd> [<type> <data_len> <data> ...]
```

- **tot_len** — total bytes in the frame (including preamble), max **255** (single-byte length prefix)
- **PREAMBLE** — fixed sync bytes: `<$MU`
- **cmd** — command name as UTF-8 text

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
| [`examples/`](examples/) | Joystick, IMU, LED, line sensor demos |
| [`pybricks_firmware/`](pybricks_firmware/) | Patched firmware with `UARTDevice` |
| [`tests/speed/`](tests/speed/) | UART throughput tests |

Copy `library/uremote.py` to your hub — do not use old copies from example folders.
