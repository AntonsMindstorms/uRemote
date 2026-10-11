# ============================================================
#  uRemote – unified MicroPython library
#  Tested on Pybricks, LMS-ESP32 and OpenMV AE3
# ============================================================
#
# HOW THIS FILE WORKS (read this before changing the transport code)
#
# One file runs on three kinds of boards:
#   * Pybricks hubs: client. Inside run_task()/multitask() the UARTDevice
#     read()/write() must be awaited; outside run_task() they block.
#   * ESP32 / OpenMV (plain MicroPython): server (process()) or client.
#     There is no run_task() and no async UART here, so everything blocks.
#
# MicroPython cannot write one function that is both blocking and awaitable.
# Instead of keeping two copies of the frame protocol in sync, the protocol
# is written ONCE as plain generators ("step generators"):
#
#   _recv_steps()    reads one frame. It does not touch the UART itself; it
#   _call_steps()    yields a request and receives the answer:
#                      yield _READ             -> receives one byte (or None)
#                      yield _PAUSE            -> wait a moment, receives None
#                      yield (_WRITE, bytes)   -> send bytes, receives None
#
# Two small drivers perform that I/O:
#   _drive_sync()    blocking UART calls. Used on ESP32 and on Pybricks
#                    outside run_task().
#   _drive_async()   awaits the UART calls so other Pybricks tasks keep
#                    running. Holds a cooperative lock (_async_busy) so two
#                    tasks cannot interleave their request/reply frames.
#
# _drive() chooses between them: Pybricks AND run_task() is truthy -> async,
# else sync. On ESP32 run_task is None and _IS_PYBRICKS is False, so the
# check short-circuits and run_task() is never called.
#
# To add a feature that talks over the wire, write it as a step generator
# and run it through _drive(); it then works in both modes for free.
#
# No silent failures: a call that returns an awaitable but is never awaited
# does nothing at all, so _drive() remembers it (_unawaited) and raises a
# uRemoteError that explains the fix on the next call.
__author__ = "Anton Vanhoucke & Ste7an"
__copyright__ = "Copyright 2024,2025,2026 AntonsMindstorms.com"
__license__ = "GPL"
__version__ = "1.4"
__status__ = "Production"

import __main__

import sys
try:
    from micropython import const
except ImportError:
    def const(arg):
        return arg

STATUS_OK = const(0)
STATUS_ERR = const(1)
MAX_FRAME = const(255)
MIN_FRAME = const(5)
MAX_CMD_LEN = const(31)
PREAMBLE = b'<$MU'
PREAMBLE_LEN = const(4)

# Step-generator requests, see uRemote._recv_steps().
_READ = const(0)
_PAUSE = const(1)
_WRITE = const(2)

_T_BOOL = const(66)
_T_NUM = const(78)
_T_BYTES = const(65)
_T_STR = const(83)

try:
    from lms_esp32 import RX_PIN, TX_PIN
except ImportError:
    RX_PIN = None
    TX_PIN = None

if 'Pybricks' in sys.version:
    _IS_PYBRICKS = True
    from pybricks.iodevices import UARTDevice
    from pybricks.tools import StopWatch, wait, run_task
    from pybricks.parameters import Port
else:
    _IS_PYBRICKS = False
    import time
    import machine
    run_task = None

class uRemoteError(Exception):
    pass


def _as_values(data):
    if isinstance(data, list):
        return data
    return [] if data is None else [data]


def _unwrap_result(payload):
    values = _as_values(payload)
    if not values:
        return None
    return values[0] if len(values) == 1 else tuple(values)


class _Awaitable:
    """What call()/exchange() return inside run_task().

    It wraps the real coroutine so that a forgotten ``await`` is self-explaining:
    ``print(ur.call('add', 1, 2))`` shows a hint instead of an opaque
    "<generator object>". Awaiting it behaves exactly like awaiting the
    coroutine. MicroPython awaits through __iter__ (hence the alias); CPython,
    used by the desktop tests, through __await__.
    """

    def __init__(self, coro, what):
        self._coro = coro
        self._what = what

    def __iter__(self):
        c = self._coro
        return c.__await__() if hasattr(c, '__await__') else c

    __await__ = __iter__

    def __repr__(self):
        return "<%s was multitasking. Use await %s to get data.>" % (self._what, self._what)

    __str__ = __repr__


class uRemote:
    """UART RPC client/server for Pybricks hubs and ESP32 boards.
    
        Args:
            port_or_uart: Pybricks Port or ESP32 UART id, default 1 - works for LMS-ESP32 and OpenMV AE3
            baudrate: Serial speed in bits per second, default 115200.
            wait_recv: Overall frame receive timeout in milliseconds, default 1000.
            uart_timeout: Per-read UART timeout in milliseconds, default 1000.
            rx: ESP32 RX pin (ignored on Pybricks), default from firmware.
            tx: ESP32 TX pin (ignored on Pybricks), default from firmware.
            power_pin: Pybricks 8V power pin, default 2 for LMS-ESP32 and SPIKE-OPENMV. Set to 0 to disable power.
        """

    def __init__(self, port_or_uart=1, baudrate=115200, wait_recv=1000, uart_timeout=1000, rx=RX_PIN, tx=TX_PIN, power_pin=2):
        self.byte_timeout = 10
        self.wait_recv = wait_recv
        self._last_rx_error = None
        # Cooperative lock so concurrent async tasks cannot interleave RPC transactions.
        self._async_busy = False
        # True between handing out an awaitable and it starting to run.
        self._unawaited = False
        if _IS_PYBRICKS:
            self._watch = StopWatch()
            if isinstance(port_or_uart, str):
                port_or_uart = eval("Port."+port_or_uart)
            self.uart = UARTDevice(port_or_uart, timeout=uart_timeout, power_pin=power_pin)
            self.uart.set_baudrate(baudrate)
            self.uart.read_all()
            self._ticks = self._watch.time
            self._elapsed = lambda start: self._watch.time() - start
            self._pause = wait
            self._waiting = self.uart.waiting
            self._drain = self.uart.read_all
        else:
            kwargs = {'timeout': uart_timeout, 'baudrate': baudrate}
            if rx is not None and tx is not None:
                kwargs['rx'] = machine.Pin(rx)
                kwargs['tx'] = machine.Pin(tx)
            self.uart = machine.UART(port_or_uart, **kwargs)
            self._ticks = time.ticks_ms
            self._elapsed = lambda start: time.ticks_diff(time.ticks_ms(), start)
            self._pause = time.sleep_ms
            self._waiting = self.uart.any
            self._drain = self.uart.read

    def _fail_rx(self, error):
        self.flush()
        self._last_rx_error = "Read error: " + error
        return b''

    def flush(self):
        """Discard all bytes waiting in the UART receive buffer."""
        while self._waiting():
            self._drain()

    def _packet(self, payload):
        frame = PREAMBLE + payload
        if len(frame) > MAX_FRAME:
            raise uRemoteError("frame too large")
        return bytes([len(frame)]) + frame

    def _recv_steps(self):
        # Frame reader written once for both modes. It is a generator that
        # yields _READ to get one byte (sent back in) and _PAUSE to wait,
        # so _drive() and _drive_async() decide how the I/O is done.
        self._last_rx_error = None
        start = self._ticks()
        while self._elapsed(start) < self.wait_recv and not self._waiting():
            yield _PAUSE
        if not self._waiting():
            return self._fail_rx("No data. Check wiring and baudrate, and that the remote script is running process().")

        length = yield _READ
        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            return self._fail_rx("No length byte. Check wiring and that the remote script is running process()." if length is None else "Invalid frame length. Baudrate mismatch or other traffic on the UART?")

        payload = bytearray()
        total_start = byte_start = self._ticks()
        pre = 0
        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("Incomplete frame. Check the cable, or raise wait_recv for slow remotes.")
            if self._waiting():
                b = yield _READ
                if b is None:
                    return self._fail_rx("Incomplete frame. Check the cable, or raise wait_recv for slow remotes.")
                payload.append(b)
                if pre < PREAMBLE_LEN:
                    if b != PREAMBLE[pre]:
                        return self._fail_rx("Preamble mismatch. Baudrate differs, or something else is talking on this UART.")
                    pre += 1
                byte_start = self._ticks()
            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx("Inter-byte timeout. Check the cable/connector, or raise ur.byte_timeout.")
            else:
                yield _PAUSE
        return bytes(payload[PREAMBLE_LEN:])

    def _encode(self, status, cmd, *argv):
        n = len(cmd)
        if n > MAX_CMD_LEN:
            raise uRemoteError("command name too long")
        # hdr: 3-bit status | 5-bit cmd length
        out = bytes([(status << 5) | n]) + bytes(cmd, 'utf-8')
        for arg in argv:
            if type(arg) == bool:
                out += bytes([_T_BOOL, 1, 1 if arg else 0])
            elif type(arg) == int:
                s = str(arg)
                out += bytes([_T_NUM, len(s)]) + bytes(s, 'utf-8')
            elif type(arg) == bytes:
                out += bytes([_T_BYTES, len(arg)]) + arg
            elif type(arg) == str:
                out += bytes([_T_STR, len(arg)]) + bytes(arg, 'utf-8')
            else:
                raise TypeError("unsupported type")
        return out

    def _decode(self, encoded):
        hdr = encoded[0]
        status, n = hdr >> 5, hdr & 0x1F
        cmd = str(encoded[1:1 + n], 'utf-8')
        decoded, p = [], 1 + n
        while p < len(encoded):
            t, ln = encoded[p], encoded[p + 1]
            p += 2
            chunk = encoded[p:p + ln]
            p += ln
            if t == _T_NUM:
                decoded.append(int(chunk))
            elif t == _T_BYTES:
                decoded.append(chunk)
            elif t == _T_STR:
                decoded.append(str(chunk, 'utf-8'))
            elif t == _T_BOOL:
                decoded.append(bool(chunk[0]))
            else:
                raise ValueError("unknown type " + str(t))
        if len(decoded) == 1:
            decoded = decoded[0]
        return status, cmd, decoded

    def _send_command(self, cmd, *data, status=STATUS_OK):
        # Sync write, used by the server side (process()).
        self.uart.write(self._packet(self._encode(status, cmd, *data)))

    def _decode_command(self, b):
        if not b:
            return STATUS_ERR, "", self._last_rx_error or "no bytes received"
        try:
            return self._decode(b)
        except (ValueError, IndexError, UnicodeError) as e:
            self.flush()
            return STATUS_ERR, "", "decode error: " + str(e)

    def _recv_command(self):
        return self._decode_command(self._drive_sync(self._recv_steps()))

    def _exchange_steps(self, cmd, data):
        yield (_WRITE, self._packet(self._encode(STATUS_OK, cmd, *data)))
        b = yield from self._recv_steps()
        return self._decode_command(b)

    def _call_steps(self, cmd, data):
        self.flush()
        reply = yield from self._exchange_steps(cmd, data)
        return self._finish_call(cmd, *reply)

    def _drive_sync(self, steps):
        # Run a step generator with blocking UART I/O.
        try:
            op = next(steps)
            while True:
                if op == _READ:
                    b = self.uart.read(1)
                    op = steps.send(b[0] if b else None)
                elif op == _PAUSE:
                    self._pause(1)
                    op = steps.send(None)
                else:
                    self.uart.write(op[1])
                    op = steps.send(None)
        except StopIteration as e:
            return e.args[0] if e.args else None

    async def _drive_async(self, steps):
        # Same as _drive_sync, but awaits Pybricks UART I/O so other tasks
        # keep running. The lock stops two tasks interleaving transactions.
        self._unawaited = False  # we are running, so someone did await us
        while self._async_busy:
            await wait(0)
        self._async_busy = True
        try:
            op = next(steps)
            while True:
                if op == _READ:
                    b = await self.uart.read(1)
                    op = steps.send(b[0] if b else None)
                elif op == _PAUSE:
                    await wait(0)
                    op = steps.send(None)
                else:
                    await self.uart.write(op[1])
                    op = steps.send(None)
        except StopIteration as e:
            return e.args[0] if e.args else None
        finally:
            self._async_busy = False

    def _drive(self, steps, what="call(...)"):
        # Auto-detect: inside Pybricks run_task()/multitask() return an
        # awaitable, otherwise run to completion and return the result.
        if _IS_PYBRICKS and run_task():
            # A forgotten `await` leaves the previous coroutine unstarted:
            # nothing was sent and nothing would ever tell the user. Catch it
            # on the next call. Known limit: creating two calls before either
            # has started (e.g. passing both to one gather-like helper) trips
            # this too; start/await them one after another.
            if self._unawaited:
                self._unawaited = False
                raise uRemoteError("Previous call() was not awaited. Under run_task() write: await ur.call(...)")
            self._unawaited = True
            return _Awaitable(self._drive_async(steps), what)
        return self._drive_sync(steps)

    def _finish_call(self, cmd, status, reply_cmd, payload):
        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        if reply_cmd != cmd:
            self.flush()
            raise uRemoteError("unexpected reply: " + reply_cmd)
        return _unwrap_result(payload)

    def exchange(self, cmd, *data):
        """Send a command and return the raw reply tuple.

        Works like ``call()``: inside ``run_task()`` / ``multitask()`` on
        Pybricks it returns an awaitable, so use ``await ur.exchange(...)``.

        Args:
            cmd: Command name.
            *data: Values to send.

        Returns:
            Tuple ``(status, reply_cmd, payload)`` without validation.
        """
        return self._drive(self._exchange_steps(cmd, data), "exchange(%r)" % cmd)

    def call(self, cmd, *data):
        """Call a remote command and return its result.

        Detects async use automatically: inside ``run_task()`` /
        ``multitask()`` on Pybricks it returns an awaitable, so write
        ``await ur.call(...)`` there. Everywhere else it blocks and returns
        the result directly.

        Args:
            cmd: Command name (must match the reply command name).
            *data: Arguments passed to the remote handler.

        Returns:
            ``None``, a scalar, or a tuple of values from the remote handler
            (or an awaitable for that result under ``run_task()``).

        Raises:
            uRemoteError: On transport, protocol, or remote handler errors.
        """
        return self._drive(self._call_steps(cmd, data), "call(%r)" % cmd)

    def process(self):
        """Handle one incoming command and send a reply.

        Looks up a function named like the command in ``__main__``, calls it
        with the decoded arguments, and sends back the return value(s).

        Returns immediately when the UART receive buffer is empty, so it is
        safe to call in a tight loop. Remains synchronous: ESP32 servers do
        not need async when the Pybricks caller awaits ``call()``.

        Raises:
            uRemoteError: When called under Pybricks ``run_task()``.
        """
        if _IS_PYBRICKS and run_task():
            # The server loop reads the UART synchronously; under run_task()
            # that read would return an unawaited handle and fail cryptically.
            raise uRemoteError("process() blocks; run it outside run_task()")
        if not self._waiting():
            return
        status, cmd, data = self._recv_command()
        if status != STATUS_OK or not cmd:
            return
        if not isinstance(data, list):
            data = [data]
        if hasattr(__main__, cmd):
            try:
                resp = getattr(__main__, cmd)(*data)
            except Exception as e:
                self._send_command(cmd, cmd + ": " + str(e), status=STATUS_ERR)
                return
            if resp is None:
                resp = ()
            elif not isinstance(resp, tuple):
                resp = (resp,)
            self._send_command(cmd, *resp, status=STATUS_OK)
        else:
            self._send_command(cmd, cmd + "() function not found remotely", status=STATUS_ERR)
