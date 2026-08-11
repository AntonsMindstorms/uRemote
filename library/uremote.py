# ============================================================
#  uRemote – unified MicroPython library
#  Tested on Pybricks, LMS-ESP32 and OpenMV AE3
# ============================================================
__author__ = "Anton Vanhoucke & Ste7an"
__copyright__ = "Copyright 2024,2025,2026 AntonsMindstorms.com"
__license__ = "GPL"
__version__ = "1.3"
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

    def _require_sync_uart(self):
        # Under run_task(), UARTDevice write/read must be awaited — sync call()
        # would return Async handles and never actually transfer bytes.
        if _IS_PYBRICKS and run_task():
            raise uRemoteError("use call_async() under run_task()/multitask()")

    def flush(self):
        """Discard all bytes waiting in the UART receive buffer."""
        while self._waiting():
            self._drain()

    def _packet(self, payload):
        frame = PREAMBLE + payload
        if len(frame) > MAX_FRAME:
            raise uRemoteError("frame too large")
        return bytes([len(frame)]) + frame

    def _send_bytes(self, payload):
        self.uart.write(self._packet(payload))

    def _read_byte(self):
        # Sync path only. From an async task on Pybricks, use _read_byte_async().
        b = self.uart.read(1)
        return b[0] if b else None

    async def _read_byte_async(self):
        b = await self.uart.read(1)
        return b[0] if b else None

    def _recv_bytes(self):
        self._last_rx_error = None
        start = self._ticks()
        while self._elapsed(start) < self.wait_recv and not self._waiting():
            self._pause(1)
        if not self._waiting():
            return self._fail_rx("No data. Is remote script running?")

        length = self._read_byte()
        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            return self._fail_rx("No length byte. Is remote script running?" if length is None else "Invalid frame length")

        payload = bytearray()
        total_start = byte_start = self._ticks()
        pre = 0
        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("Incomplete frame.")
            if self._waiting():
                b = self._read_byte()
                if b is None:
                    return self._fail_rx("Incomplete frame.")
                payload.append(b)
                if pre < PREAMBLE_LEN:
                    if b != PREAMBLE[pre]:
                        return self._fail_rx("Preamble mismatch.")
                    pre += 1
                byte_start = self._ticks()
            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx("Inter-byte timeout.")
            else:
                self._pause(1)
        return bytes(payload[PREAMBLE_LEN:])

    async def _recv_bytes_async(self):
        # Pybricks only (see call_async).
        self._last_rx_error = None
        start = self._ticks()
        while self._elapsed(start) < self.wait_recv and not self._waiting():
            await wait(0)
        if not self._waiting():
            return self._fail_rx("No data. Is remote script running?")

        length = await self._read_byte_async()
        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            return self._fail_rx("No length byte. Is remote script running?" if length is None else "Invalid frame length")

        payload = bytearray()
        total_start = byte_start = self._ticks()
        pre = 0
        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("Incomplete frame.")
            if self._waiting():
                b = await self._read_byte_async()
                if b is None:
                    return self._fail_rx("Incomplete frame.")
                payload.append(b)
                if pre < PREAMBLE_LEN:
                    if b != PREAMBLE[pre]:
                        return self._fail_rx("Preamble mismatch.")
                    pre += 1
                byte_start = self._ticks()
            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx("Inter-byte timeout.")
            else:
                await wait(0)
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
        self._send_bytes(self._encode(status, cmd, *data))

    async def _send_command_async(self, cmd, *data, status=STATUS_OK):
        # UARTDevice.write must be awaited under run_task().
        await self.uart.write(self._packet(self._encode(status, cmd, *data)))

    def _decode_command(self, b):
        if not b:
            return STATUS_ERR, "", self._last_rx_error or "no bytes received"
        try:
            return self._decode(b)
        except (ValueError, IndexError, UnicodeError) as e:
            self.flush()
            return STATUS_ERR, "", "decode error: " + str(e)

    def _recv_command(self):
        return self._decode_command(self._recv_bytes())

    async def _recv_command_async(self):
        return self._decode_command(await self._recv_bytes_async())

    def _finish_call(self, cmd, status, reply_cmd, payload):
        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        if reply_cmd != cmd:
            self.flush()
            raise uRemoteError("unexpected reply: " + reply_cmd)
        return _unwrap_result(payload)

    def exchange(self, cmd, *data):
        """Send a command and return the raw reply tuple.

        Args:
            cmd: Command name.
            *data: Values to send.

        Returns:
            Tuple ``(status, reply_cmd, payload)`` without validation.
        """
        self._require_sync_uart()
        self._send_command(cmd, *data)
        return self._recv_command()

    def call(self, cmd, *data):
        """Call a remote command and return its result.

        Args:
            cmd: Command name (must match the reply command name).
            *data: Arguments passed to the remote handler.

        Returns:
            ``None``, a scalar, or a tuple of values from the remote handler.

        Raises:
            uRemoteError: On transport, protocol, or remote handler errors.
        """
        self._require_sync_uart()
        self.flush()
        self._send_command(cmd, *data)
        return self._finish_call(cmd, *self._recv_command())

    async def call_async(self, cmd, *data):
        """Asynchronously call a remote command and return its result.

        Pybricks only. Preferred when calling uRemote from multiple tasks under
        ``multitask()`` / ``run_task()``. Same result semantics as ``call()``.

        Raises:
            uRemoteError: On transport, protocol, or remote handler errors,
                or when used outside Pybricks.
        """
        if not _IS_PYBRICKS:
            raise uRemoteError("call_async is only supported on Pybricks")
        while self._async_busy:
            await wait(0)
        self._async_busy = True
        try:
            self.flush()
            await self._send_command_async(cmd, *data)
            return self._finish_call(cmd, *(await self._recv_command_async()))
        finally:
            self._async_busy = False

    def process(self):
        """Handle one incoming command and send a reply.

        Looks up a function named like the command in ``__main__``, calls it
        with the decoded arguments, and sends back the return value(s).

        Returns immediately when the UART receive buffer is empty, so it is
        safe to call in a tight loop. Remains synchronous: ESP32 servers do
        not need async when the Pybricks caller uses ``call_async()``.
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
