# uRemote Pre-Release Review

**Date:** 2026-06-14  
**Audience:** Pybricks beginners  
**Platforms in focus:** EV3 ↔ LMS-ESP32, Prime/Technic hub ↔ ESP32  
**Scope:** `library/uremote.py`, `library/uremote.ubl`, examples (Python + MicroBlocks)

---

## Executive summary

uRemote is a small, practical UART RPC layer for pairing Pybricks hubs with ESP32/MicroBlocks devices. The core idea is easy to grasp: define a function on one side, `call()` it from the other, or run `process()` in a loop on the server side.

For a pre-teaching release, the library is **not yet beginner-ready**. The biggest blockers are inconsistent naming (`uRemote` / `MicroRemote` / `uremote`), two different `call()` return shapes between Python and MicroBlocks, examples that disagree with each other (and one that will not run), silent failures when things go wrong, and almost no onboarding path for the custom firmware requirement.

With targeted fixes to docs, examples, error messages, and a few code bugs, this could be teachable. The items marked **P0** below should be resolved before classroom use.

---

## 1. Beginner-friendliness

### What works well

- **Small surface area.** Three concepts cover most use cases: `uRemote(...)`, `.call(...)`, `.process()`.
- **Convention-over-configuration on ESP32.** `uRemote()` with no arguments is reasonable when pins and UART are already configured in LMS-ESP32 firmware.
- **Server-side handlers are plain functions.** On ESP32, defining `def led(updown): ...` and calling `ur.process()` in a loop matches how beginners already think about “do something when asked.”
- **Examples cover real projects.** Joystick, IMU, LED, and line sensor give teachers something concrete to demo.

### What will confuse Pybricks beginners

| Issue | Why it hurts beginners | Severity |
|-------|------------------------|----------|
| Custom firmware is required but not part of the library onboarding | README mentions `UARTDevice` firmware briefly; there is no step-by-step “flash hub → copy library → run first example” guide in scope | **P0** |
| Two ways to use the Python API | Examples use `uRemote(Port.A)` directly; `uremote_template_blocks.py` uses module-level `init('A')`, `call(...)`, `process()` | **P1** |
| `call()` return value is unclear | Some examples unpack `(cmd, data)`, others `(err, data)`, others only `data`. Beginners cannot tell success from failure | **P0** |
| Duplicate library in examples | `examples/line_sensor_ev3/ev3/uremote.py` is a stale copy of `library/uremote.py` (missing a bugfix). Beginners may copy the wrong file | **P1** |
| No wiring / port guidance in examples | EV3 uses `Port.S1`, Prime uses `Port.A`; never explained. LMS-ESP32 side assumes prior LMS-ESP32 knowledge | **P1** |
| Broken example | `examples/joystick/uremote_joystick_spike.py` imports `MicroRemote` but instantiates `uRemote` | **P0** |
| Hidden debug output in MicroBlocks library | `uremote.ubl` still calls `sayIt` on preamble mismatch (line 137) — will spam the stage during UART glitches | **P1** |

### Suggested minimum onboarding path (not present today)

1. Flash Pybricks firmware with `UARTDevice` (+ `power_pin` if powering NeoPixels/servos).
2. Copy `library/uremote.py` to the hub.
3. Connect TX/RX/GND (and power if needed) — with a diagram.
4. Run a “ping” example: hub calls `ping` on ESP32, ESP32 returns a number.
5. Explain client (`call`) vs server (`process`) roles explicitly.

---

## 2. Wording and API consistency

### Project naming

The repo and files use overlapping names:

| Term | Where it appears |
|------|------------------|
| **uRemote** | Repo name, class name, file `uremote.py` |
| **MicroRemote** | Comment in `uremote.py` (line 69), broken import in `uremote_joystick_spike.py` |
| **MicroRemote / UARTRemote** | README opening paragraph |
| **uremote** | MicroBlocks module name, block labels (`uremote init`, `uremote call`) |

**Recommendation:** Pick one product name (e.g. **uRemote**) and use it everywhere. Retire “MicroRemote” in comments and examples.

### Python API: class vs module functions

`library/uremote.py` exposes both patterns:

```python
# Pattern A — used in most examples
ur = uRemote(Port.A)
ur.call("imu", x, y, z)

# Pattern B — used in template / Pybricks blocks export
from uremote import init, call, process
init('A')
call('imu', 100, 2000, 300)
```

Pattern B’s `init('A')` uses `eval("Port." + port)`, which is brittle and opaque to beginners. Pattern A is clearer. **Pick one primary style for teaching** (recommend Pattern A) and demote or document the other.

### `call()` return shape — Python vs MicroBlocks

This is the largest cross-platform inconsistency:

| Platform | `call()` returns | On error |
|----------|------------------|----------|
| **Python** (`uremote.py`) | `(cmd, data)` — e.g. `("joy_ack", [x, y, pressed])` or `("!ERROR", "no bytes received")` | Second element is a string message; first is always `"!ERROR"` |
| **MicroBlocks** (`uremote.ubl`) | **Data only** — unwraps to scalar if one value | Empty byte array → decode returns empty list → `call` returns nothing useful |

Examples interpret the Python tuple differently:

```python
# examples/joystick/uremote_joystick.py — treats first value as "ack"
ack, resp = ur.call('joy')

# examples/joystick/uremote_joy_spike.py — treats first value as "err"
err, data = ur.call('joy')

# tests/speed/test_uart_send_ev3.py — treats first value as command name
cmd, data = ur.call('test', i, i+2)
```

Only the test file’s naming is accurate. **`ack` and `err` are both misleading** unless the reader knows the protocol.

**Recommendation:** Document the contract explicitly:

- Success: `(f"{name}_ack", payload)`
- Failure: `("!ERROR", "<specific reason>")`

Consider a helper or structured return for beginners, e.g. always return a small dict or named tuple with `ok`, `cmd`, `data`, `error`.

### Timeout parameter naming

| Location | Name |
|----------|------|
| `uRemote.__init__` | `wait_recv`, `uart_timeout` |
| README | `time_out`, `byte_timeout` |
| MicroBlocks `uremote.ubl` | Hard-coded `1000` ms and `10` ms |

Align README terms with code (`wait_recv`, `uart_timeout`, `byte_timeout`) or rename code to match docs.

### Command / response protocol terms

These are implicit but never defined for users:

| Term | Meaning |
|------|---------|
| `cmd` | Request command name (e.g. `"joy"`) |
| `cmd + "_ack"` | Response command on success |
| `cmd + "_err"` | Response command on receive/decode failure |
| `"!ERROR"` | Synthetic command name returned locally (not sent on the wire) |

Beginners will not infer this from code alone. A one-page “request/response lifecycle” diagram would help.

### Pybricks port naming in `init()`

`init('A')` works for Prime/Technic. EV3 examples use `Port.S1`. The string `'A'` vs `'S1'` convention is never explained.

---

## 3. Potential code issues

### P0 — Will cause wrong behavior or crashes

#### 3.1 Set instead of tuple in `process()` (Python)

```270:270:library/uremote.py
                    resp = {resp}
```

`{resp}` creates a **set**, not a one-element tuple. Should be `(resp,)`. Affects any handler that returns a single non-tuple value (e.g. an `int` or `bytes`). Unpacking a set into `send_command` is unordered and can break multi-value responses if the bug were `{a, b}`.

#### 3.2 Boolean return discarded in MicroBlocks `process()`

```186:188:library/uremote.ubl
    if (isType return 'boolean') {
      return = ('[data:makeList]')
    } (not (isType return 'list')) {
```

If an ESP32-side MicroBlocks handler returns `true`/`false`, the ack payload becomes an **empty list** instead of the boolean. Python does not have this bug.

#### 3.3 Broken import in example

```11:13:examples/joystick/uremote_joystick_spike.py
from microremote import MicroRemote

ur = uRemote(Port.A)
```

`microremote` / `MicroRemote` do not exist in this repo. This example fails immediately on import/name error.

#### 3.4 Stale vendored copy of the library

`examples/line_sensor_ev3/ev3/uremote.py` is missing the `process()` fix that wraps scalar `data` in a list before calling the handler. Single-argument remote calls can fail on the EV3 side if users copy this file instead of `library/uremote.py`.

### P1 — Likely to cause subtle or intermittent problems

#### 3.5 `call()` flushes before receiving

```253:256:library/uremote.py
    def call(self, cmd, *data):
        self.send_command(cmd, *data)
        self.flush()
        return self.receive_command()
```

`flush()` drains **all** pending UART input after sending. If the peer responds quickly, those bytes can be discarded before `receive_command()` runs. This may work in practice due to timing but is fragile; a race could produce `"no bytes received"` with no hint that flush caused it.

#### 3.6 Single-byte frame length limit

```142:145:library/uremote.py
    def send_bytes(self, payload):
        b = PREAMBLE + payload
        b = bytes([len(b)]) + b
```

The length prefix is one byte (max frame 255 bytes). Large string or bytearray payloads will fail silently or truncate. Not documented; beginners sending sensor arrays may hit this.

#### 3.7 `encode()` uses separate `if` chains, not `elif`

Each argument is tested with independent `if` statements. Unusual types could theoretically match multiple branches (e.g. future type confusion). Using `elif` would be safer; unknown types are silently dropped today.

#### 3.8 Missing handler is silent (Python `process()`)

```263:271:library/uremote.py
        if cmd != "!ERROR":
            if hasattr(__main__, cmd):
                func = getattr(__main__, cmd)
                ...
                self.send_command(cmd + "_ack", *resp)
```

If the command name is received but no matching function exists, **no ack and no err is sent**. The caller hangs until timeout, then gets `"no bytes received"`. Same gap in MicroBlocks `process()` (no error path at all).

#### 3.9 MicroBlocks `_decode` unknown type falls through silently

```48:49:library/uremote.ubl
    } else {
    }
```

Unknown type codes append nothing and do not signal error. Python raises `ValueError("Unknown type code")` (though it is caught and collapsed to a generic `"decode error"`).

#### 3.10 Debug `sayIt` left in production MicroBlocks library

```137:137:library/uremote.ubl
          sayIt idx (at idx buf) (at idx PREAMBLE)
```

Will confuse beginners during normal UART resync after noise.

### P2 — Code quality / platform edge cases

- Bare `except:` in platform detection (`uremote.py` lines 14, 43, 248) hides real import and decode errors.
- `type(arg) == int` etc. instead of `isinstance` — minor, but `bool` is a subclass of `int` in Python; current ordering happens to work.
- Platform constants (`_EV3`, `_SPIKE`, …) are defined but only `_PYBRICKS` and `_ESP32` backends exist; dead code may confuse maintainers.
- `examples/line_sensor_ev3/lms-esp32/uremote_line.py` references `LineSensor()` but imports `line_sensor` module — class name mismatch (`LineSensor` vs import) may be a separate LMS-ESP32 convention, but the example has no comments tying pieces together.

---

## 4. Issues that do not tell users what went wrong

Beginners need actionable messages. Today many failure modes collapse to the same opaque outcome.

### 4.1 Generic local errors (Python)

| Condition | User sees | What actually happened |
|-----------|-----------|------------------------|
| Timeout waiting for frame | `("!ERROR", "no bytes received")` | Could be: not wired, wrong port, peer not running, baud mismatch, flush race, or peer crashed |
| Preamble mismatch | `("!ERROR", "no bytes received")` | Garbage on the line; buffer was flushed — resync failed |
| Inter-byte gap > 10 ms | `("!ERROR", "no bytes received")` | Partial frame; same message as total timeout |
| Decode failure (malformed payload) | `("!ERROR", "decode error")` | Catches all exceptions; no detail (unknown type, truncated data, bad UTF-8) |
| Missing handler on server | *(caller timeout)* → `"no bytes received"` | Server received command but has no function — indistinguishable from wiring failure |

**Recommendation:** Return distinct error strings, e.g. `"timeout: no length byte"`, `"timeout: incomplete frame"`, `"preamble mismatch"`, `"decode: unknown type 0x??"`, `"handler not found: joy"`. Avoid bare `except Exception` without logging the cause.

### 4.2 MicroBlocks: failures look like success

| Condition | User sees |
|-----------|-----------|
| Timeout / preamble error | Empty byte array from `_wait and read serial` → `_receive command` returns empty list → `call` returns `()` / empty |
| Decode with wrong types | Partial or empty data, no error block |
| Missing custom handler | `callCustomReporter cmd data` fails opaquely in MicroBlocks |

MicroBlocks users get **no `"!ERROR"` equivalent** in the Python library sense. Cross-platform teaching will diverge unless documented.

### 4.3 Misleading variable names in examples teach bad habits

```python
err, data = ur.call('sen')  # err is not an error unless cmd == "!ERROR"
```

Beginners will write `if err:` checks that do not mean what they think.

### 4.4 Server sends generic wire error

```273:273:library/uremote.py
            self.send_command(cmd + "_err", "recv error")
```

When the server fails to receive/decode, the client gets the string `"recv error"` with no distinction between timeout, bad preamble, and decode failure — and only if the server is the one calling `process()` and hitting an error path. The `"!ERROR"` path is local to each side’s `receive_command()`.

---

## 5. Example inventory (consistency check)

| Example | Hub | Role | API style | `call()` unpacking | Status |
|---------|-----|------|-----------|-------------------|--------|
| `uremote_imu_spike.py` | Prime | Client | `uRemote(Port.A)` | Ignores return | OK |
| `uremote_led_spike.py` | Prime | Client | `uRemote(Port.A)` | Ignores return | OK |
| `uremote_joy_spike.py` | Prime | Client | `uRemote(Port.A)` | `err, data` — misleading | OK if wired |
| `uremote_joystick_spike.py` | Prime | Client | Broken import | `ack, resp` | **Broken** |
| `uremote_joystick.py` | EV3 | Client | `uRemote(Port.S1)` | `ack, resp` | OK |
| `uremote_line_ev3.py` | EV3 | Client | `uRemote(Port.S1)` | `err, data` in try/except | OK |
| `esp32_led.py` | ESP32 | Server | `process()` loop | — | OK |
| `uremote_line.py` | ESP32 | Server | `process()` loop | — | Needs LMS-ESP32 context |
| `uremote_template_blocks.py` | Prime | Client | `init/call/process` | Module-level | OK for blocks |

No single “hello world” pair (minimal hub script + minimal ESP32 script) exists in the examples set.

---

## 6. Pre-release checklist

### P0 — Block teaching until fixed

- [ ] Fix `{resp}` → `(resp,)` in `library/uremote.py` `process()`
- [ ] Fix boolean ack bug in `library/uremote.ubl` `process()`
- [ ] Fix or remove `examples/joystick/uremote_joystick_spike.py` broken import
- [ ] Remove or update stale `examples/line_sensor_ev3/ev3/uremote.py` (point to `library/uremote.py` only)
- [ ] Document `call()` return contract and check `cmd == "!ERROR"` (standardize example variable names to `cmd, data`)
- [ ] Add minimal getting-started steps including custom firmware flash (even if firmware is out of scope, link to it)

### P1 — Strongly recommended before classroom use

- [ ] Unify naming: uRemote everywhere; remove MicroRemote references
- [ ] Remove debug `sayIt` from `uremote.ubl`
- [ ] Send `_err` (or `_ack` with error payload) when handler function is missing
- [ ] Differentiate error strings in `receive_command()` (timeout vs preamble vs decode)
- [ ] Revisit `call()` → `flush()` → `receive_command()` ordering
- [ ] Document 255-byte frame limit and supported types
- [ ] Add paired “hello world” hub + ESP32 examples for Prime and EV3
- [ ] Align README timeout names with code

### P2 — Nice to have

- [ ] Deprecate or document `init()` / module-level API vs `uRemote` class
- [ ] Replace bare `except:` with specific exceptions
- [ ] MicroBlocks parity for error reporting (mirror `"!ERROR"` pattern or document differences)
- [ ] Type-check unknown `encode()` arguments and raise clearly

---

## 7. Overall assessment

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Beginner-friendliness | **2 / 5** | Good concepts, weak onboarding, inconsistent examples |
| Wording / API consistency | **2 / 5** | Multiple names, dual Python APIs, Python ≠ MicroBlocks `call()` |
| Code correctness | **3 / 5** | Core protocol works; known bugs in `process()` paths |
| Error clarity | **1.5 / 5** | Most failures look the same; examples use wrong variable names |

**Verdict:** Suitable for experienced users who already run LMS-ESP32 + custom Pybricks firmware. **Not yet ready to hand to Pybricks beginners** without instructor cheat-sheets and the P0 fixes above.
