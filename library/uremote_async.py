"""uRemote - unified MicroPython UART RPC library.

Runs on:
- Pybricks hubs
- ESP32 / LMS-ESP32 style MicroPython
- Other MicroPython boards using machine.UART

The wire protocol is unchanged from uRemote 1.2.

Synchronous API:
    ur.call(...)
    ur.exchange(...)
    ur.process()

Asynchronous caller API:
    await ur.call_async(...)
    await ur.exchange_async(...)

The asynchronous API serializes complete request/reply transactions so two
concurrent tasks cannot interleave commands on the same UART.
"""

# ============================================================
# uRemote - unified MicroPython library
# Tested on Pybricks, LMS-ESP32 and OpenMV AE3
# ============================================================

__author__ = "Anton Vanhoucke & Ste7an"
__copyright__ = "Copyright 2024,2025,2026 AntonsMindstorms.com"
__license__ = "GPL"
__version__ = "1.3.1-async-read"
__status__ = "proof of concept"

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
PREAMBLE = b"<$MU"
PREAMBLE_LEN = const(4)

_T_BOOL = const(66)
_T_NUM = const(78)
_T_BYTES = const(65)
_T_STR = const(83)

try:
    from lms_esp32 import RX_PIN, TX_PIN
except ImportError:
    RX_PIN = None
    TX_PIN = None


if "Pybricks" in sys.version:
    _IS_PYBRICKS = True

    from pybricks.iodevices import UARTDevice
    from pybricks.tools import StopWatch, wait
    from pybricks.parameters import Port

    _ASYNCIO = None

else:
    _IS_PYBRICKS = False

    import time
    import machine

    # Only needed when call_async()/exchange_async() is used on a
    # non-Pybricks target. The normal ESP32 server path does not depend
    # on asyncio.
    try:
        import uasyncio as _ASYNCIO
    except ImportError:
        _ASYNCIO = None


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


class uRemote:
    """UART RPC client/server for Pybricks hubs and ESP32 boards."""

    def __init__(
        self,
        port_or_uart=1,
        baudrate=115200,
        wait_recv=1000,
        uart_timeout=1000,
        rx=RX_PIN,
        tx=TX_PIN,
        power_pin=2,
    ):
        self.byte_timeout = 10
        self.wait_recv = wait_recv
        self._last_rx_error = None

        # Cooperative mutex for async request/reply transactions.
        #
        # uRemote is a request -> reply protocol. A second task must not
        # transmit another command before the first task has received its
        # reply, otherwise replies can be consumed by the wrong task.
        self._async_busy = False

        if _IS_PYBRICKS:
            self._watch = StopWatch()

            if isinstance(port_or_uart, str):
                port_or_uart = eval("Port." + port_or_uart)

            self.uart = UARTDevice(
                port_or_uart,
                timeout=uart_timeout,
                power_pin=power_pin,
            )
            self.uart.set_baudrate(baudrate)
            self.uart.read_all()

        else:
            kwargs = {
                "timeout": uart_timeout,
                "baudrate": baudrate,
            }

            if rx is not None and tx is not None:
                kwargs["rx"] = machine.Pin(rx)
                kwargs["tx"] = machine.Pin(tx)

            self.uart = machine.UART(port_or_uart, **kwargs)

    # --------------------------------------------------------
    # Platform helpers
    # --------------------------------------------------------

    def _ticks(self):
        return self._watch.time() if _IS_PYBRICKS else time.ticks_ms()

    def _elapsed(self, start):
        if _IS_PYBRICKS:
            return self._watch.time() - start
        return time.ticks_diff(time.ticks_ms(), start)

    def _pause(self, ms):
        """Blocking pause used by the synchronous API."""
        if _IS_PYBRICKS:
            wait(ms)
        else:
            time.sleep_ms(ms)

    async def _yield_async(self):
        """Yield cooperatively to another task."""
        if _IS_PYBRICKS:
            await wait(0)
            return

        if _ASYNCIO is None:
            raise uRemoteError(
                "async uRemote calls require uasyncio on this platform"
            )

        await _ASYNCIO.sleep_ms(0)

    def _waiting(self):
        return self.uart.waiting() if _IS_PYBRICKS else self.uart.any()

    def _read_byte_sync(self):
        # Synchronous byte read. Use only from the synchronous receive path.
        # On Pybricks, UARTDevice.read() becomes awaitable when called from
        # an async task, so the async receive path uses _read_byte_async().
        data = self.uart.read(1)
        return data[0] if data else None

    async def _read_byte_async(self):
        # Async byte read for the coroutine receive path.
        if _IS_PYBRICKS:
            data = await self.uart.read(1)
        else:
            # machine.UART.read() is synchronous. _waiting() is checked
            # first, so this normally returns immediately.
            data = self.uart.read(1)
        return data[0] if data else None

    def _fail_rx(self, error):
        self.flush()
        self._last_rx_error = "Read error: " + error
        return b""

    def flush(self):
        """Discard all bytes waiting in the UART receive buffer."""
        while self._waiting():
            if _IS_PYBRICKS:
                self.uart.read_all()
            else:
                self.uart.read()

    # --------------------------------------------------------
    # Framing: synchronous
    # --------------------------------------------------------

    def _send_bytes(self, payload):
        frame = PREAMBLE + payload

        if len(frame) > MAX_FRAME:
            raise uRemoteError("frame too large")

        self.uart.write(bytes([len(frame)]) + frame)

    def _recv_bytes(self):
        self._last_rx_error = None

        start = self._ticks()

        while self._elapsed(start) < self.wait_recv and not self._waiting():
            self._pause(1)

        if not self._waiting():
            return self._fail_rx(
                "No data. Is remote script running?"
            )

        length = self._read_byte_sync()

        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            if length is None:
                return self._fail_rx(
                    "No length byte. Is remote script running?"
                )

            return self._fail_rx("Invalid frame length")

        payload = bytearray()
        total_start = self._ticks()
        byte_start = total_start
        preamble_index = 0

        while len(payload) < length:

            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("Incomplete frame.")

            if self._waiting():
                value = self._read_byte_sync()

                if value is None:
                    return self._fail_rx("Incomplete frame.")

                payload.append(value)

                if preamble_index < PREAMBLE_LEN:
                    if value != PREAMBLE[preamble_index]:
                        return self._fail_rx("Preamble mismatch.")

                    preamble_index += 1

                byte_start = self._ticks()

            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx("Inter-byte timeout.")

            else:
                self._pause(1)

        return bytes(payload[PREAMBLE_LEN:])

    # --------------------------------------------------------
    # Framing: asynchronous
    # --------------------------------------------------------

    async def _send_bytes_async(self, payload):
        frame = PREAMBLE + payload

        if len(frame) > MAX_FRAME:
            raise uRemoteError("frame too large")

        packet = bytes([len(frame)]) + frame

        if _IS_PYBRICKS:
            # UARTDevice.write() participates in Pybricks cooperative
            # multitasking when run under run_task().
            await self.uart.write(packet)

        else:
            # machine.UART.write() is synchronous. UART packets are tiny
            # (max 256 bytes including the length byte), so write it and
            # then yield once.
            self.uart.write(packet)
            await self._yield_async()

    async def _recv_bytes_async(self):
        self._last_rx_error = None

        start = self._ticks()

        while self._elapsed(start) < self.wait_recv and not self._waiting():
            await self._yield_async()

        if not self._waiting():
            return self._fail_rx(
                "No data. Is remote script running?"
            )

        length = await self._read_byte_async()

        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            if length is None:
                return self._fail_rx(
                    "No length byte. Is remote script running?"
                )

            return self._fail_rx("Invalid frame length")

        payload = bytearray()
        total_start = self._ticks()
        byte_start = total_start
        preamble_index = 0

        while len(payload) < length:

            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("Incomplete frame.")

            if self._waiting():
                value = await self._read_byte_async()

                if value is None:
                    return self._fail_rx("Incomplete frame.")

                payload.append(value)

                if preamble_index < PREAMBLE_LEN:
                    if value != PREAMBLE[preamble_index]:
                        return self._fail_rx("Preamble mismatch.")

                    preamble_index += 1

                byte_start = self._ticks()

            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx("Inter-byte timeout.")

            else:
                await self._yield_async()

        return bytes(payload[PREAMBLE_LEN:])

    # --------------------------------------------------------
    # Codec
    # --------------------------------------------------------

    def _encode(self, status, cmd, *argv):
        name_len = len(cmd)

        if name_len > MAX_CMD_LEN:
            raise uRemoteError("command name too long")

        out = (
            bytes([(status << 5) | name_len])
            + bytes(cmd, "utf-8")
        )

        for arg in argv:

            if type(arg) == bool:
                out += bytes([
                    _T_BOOL,
                    1,
                    1 if arg else 0,
                ])

            elif type(arg) == int:
                raw = str(arg)
                out += (
                    bytes([_T_NUM, len(raw)])
                    + bytes(raw, "utf-8")
                )

            elif type(arg) == bytes:
                out += bytes([_T_BYTES, len(arg)]) + arg

            elif type(arg) == str:
                out += (
                    bytes([_T_STR, len(arg)])
                    + bytes(arg, "utf-8")
                )

            else:
                raise TypeError("unsupported type")

        return out

    def _decode(self, encoded):
        header = encoded[0]
        status = header >> 5
        name_len = header & 0x1F

        cmd = str(
            encoded[1:1 + name_len],
            "utf-8",
        )

        decoded = []
        pos = 1 + name_len

        while pos < len(encoded):
            item_type = encoded[pos]
            item_len = encoded[pos + 1]
            pos += 2

            chunk = encoded[pos:pos + item_len]
            pos += item_len

            if item_type == _T_NUM:
                decoded.append(int(chunk))

            elif item_type == _T_BYTES:
                decoded.append(chunk)

            elif item_type == _T_STR:
                decoded.append(str(chunk, "utf-8"))

            elif item_type == _T_BOOL:
                decoded.append(bool(chunk[0]))

            else:
                raise ValueError(
                    "unknown type " + str(item_type)
                )

        if len(decoded) == 1:
            decoded = decoded[0]

        return status, cmd, decoded

    # --------------------------------------------------------
    # Command transport: synchronous
    # --------------------------------------------------------

    def _send_command(self, cmd, *data, status=STATUS_OK):
        self._send_bytes(
            self._encode(status, cmd, *data)
        )

    def _recv_command(self):
        data = self._recv_bytes()

        if not data:
            return (
                STATUS_ERR,
                "",
                self._last_rx_error or "no bytes received",
            )

        try:
            return self._decode(data)

        except (ValueError, IndexError, UnicodeError) as exc:
            self.flush()
            return (
                STATUS_ERR,
                "",
                "decode error: " + str(exc),
            )

    # --------------------------------------------------------
    # Command transport: asynchronous
    # --------------------------------------------------------

    async def _send_command_async(
        self,
        cmd,
        *data,
        status=STATUS_OK
    ):
        await self._send_bytes_async(
            self._encode(status, cmd, *data)
        )

    async def _recv_command_async(self):
        data = await self._recv_bytes_async()

        if not data:
            return (
                STATUS_ERR,
                "",
                self._last_rx_error or "no bytes received",
            )

        try:
            return self._decode(data)

        except (ValueError, IndexError, UnicodeError) as exc:
            self.flush()
            return (
                STATUS_ERR,
                "",
                "decode error: " + str(exc),
            )

    # --------------------------------------------------------
    # Public synchronous caller API
    # --------------------------------------------------------

    def exchange(self, cmd, *data):
        """Send a command and return the raw reply tuple."""
        self._send_command(cmd, *data)
        return self._recv_command()

    def call(self, cmd, *data):
        """Call a remote command and return its result."""
        self._send_command(cmd, *data)

        status, reply_cmd, payload = self._recv_command()

        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(
                payload
                if isinstance(payload, str)
                else str(payload)
            )

        if reply_cmd != cmd:
            raise uRemoteError(
                "unexpected reply: " + reply_cmd
            )

        return _unwrap_result(payload)

    # --------------------------------------------------------
    # Public asynchronous caller API
    # --------------------------------------------------------

    async def _acquire(self):
        """Acquire the cooperative async transaction lock."""
        while self._async_busy:
            await self._yield_async()

        # Cooperative scheduling only switches at await points, so the
        # check above and this assignment are atomic with respect to the
        # other uRemote coroutines.
        self._async_busy = True

    def _release(self):
        self._async_busy = False

    async def exchange_async(self, cmd, *data):
        """Asynchronously send a command and return the raw reply tuple.

        Complete request/reply exchanges are serialized. This prevents
        concurrent tasks from consuming each other's replies.
        """
        await self._acquire()

        try:
            await self._send_command_async(cmd, *data)
            return await self._recv_command_async()

        finally:
            self._release()

    async def call_async(self, cmd, *data):
        """Asynchronously call a remote command and return its result.

        This is the preferred API when uRemote is called from multiple
        Pybricks tasks running under multitask()/run_task().
        """
        await self._acquire()

        try:
            await self._send_command_async(cmd, *data)

            status, reply_cmd, payload = (
                await self._recv_command_async()
            )

            if status != STATUS_OK or not reply_cmd:
                raise uRemoteError(
                    payload
                    if isinstance(payload, str)
                    else str(payload)
                )

            if reply_cmd != cmd:
                raise uRemoteError(
                    "unexpected reply: " + reply_cmd
                )

            return _unwrap_result(payload)

        finally:
            self._release()

    # --------------------------------------------------------
    # Server API
    # --------------------------------------------------------

    def process(self):
        """Handle one incoming command and send a reply.

        This remains synchronous intentionally. The UART wire protocol
        is still one request followed by one reply, so an ESP32 remote
        does not need any changes when the Pybricks caller switches from
        call() to call_async().
        """
        if not self._waiting():
            return

        status, cmd, data = self._recv_command()

        if status != STATUS_OK or not cmd:
            return

        if not isinstance(data, list):
            data = [data]

        if hasattr(__main__, cmd):
            try:
                response = getattr(__main__, cmd)(*data)

            except Exception as exc:
                self._send_command(
                    cmd,
                    cmd + ": " + str(exc),
                    status=STATUS_ERR,
                )
                return

            if response is None:
                response = ()

            elif not isinstance(response, tuple):
                response = (response,)

            self._send_command(
                cmd,
                *response,
                status=STATUS_OK,
            )

        else:
            self._send_command(
                cmd,
                cmd + "() function not found remotely",
                status=STATUS_ERR,
            )
