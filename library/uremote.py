# ============================================================
#  uRemote – unified Pybricks + MicroPython ESP32 library
# ============================================================

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
RX_PIN = 0
TX_PIN = 0

if 'Pybricks' in sys.version:
    _IS_PYBRICKS = True
    from pybricks.iodevices import UARTDevice
    from pybricks.tools import StopWatch, wait
else:
    _IS_PYBRICKS = False
    import time
    import machine
    if not 'OpenMV' in sys.version:
        from lms_esp32 import RX_PIN, TX_PIN
    

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
        """

    def __init__(self, port_or_uart=1, baudrate=115200, wait_recv=1000, uart_timeout=1000, rx=RX_PIN, tx=TX_PIN):
        self.byte_timeout = 10
        self.wait_recv = wait_recv
        self._last_rx_error = None
        if _IS_PYBRICKS:
            self._watch = StopWatch()
            self.uart = UARTDevice(port_or_uart, timeout=uart_timeout)
            self.uart.set_baudrate(baudrate)
        elif 'OpenMV' in sys.version:
            self.uart = machine.UART(port_or_uart, baudrate)
        else:
            self.uart = machine.UART(port_or_uart, baudrate=baudrate, rx=machine.Pin(rx), tx=machine.Pin(tx), timeout=uart_timeout)

    def _ticks(self):
        return self._watch.time() if _IS_PYBRICKS else time.ticks_ms()

    def _elapsed(self, start):
        return (self._watch.time() - start) if _IS_PYBRICKS else time.ticks_diff(time.ticks_ms(), start)

    def _pause(self, ms):
        wait(ms) if _IS_PYBRICKS else time.sleep_ms(ms)

    def _waiting(self):
        return self.uart.waiting() if _IS_PYBRICKS else self.uart.any()

    def _read_byte(self):
        b = self.uart.read(1)
        return b[0] if b else None

    def _fail_rx(self, error):
        self.flush()
        self._last_rx_error = "Read error: " + error
        return b''

    def flush(self):
        """Discard all bytes waiting in the UART receive buffer."""
        while self._waiting():
            self.uart.read_all() if _IS_PYBRICKS else self.uart.read()

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
            return self._fail_rx("no length byte")

        length = self._read_byte()
        if length is None or length < MIN_FRAME or length > MAX_FRAME:
            return self._fail_rx("no length byte" if length is None else "invalid frame length")

        payload = bytearray()
        total_start = byte_start = self._ticks()
        pre = 0
        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("incomplete frame")
            if self._waiting():
                b = self._read_byte()
                if b is None:
                    return self._fail_rx("incomplete frame")
                payload.append(b)
                if pre < PREAMBLE_LEN:
                    if b != PREAMBLE[pre]:
                        return self._fail_rx("preamble mismatch")
                    pre += 1
                byte_start = self._ticks()
            elif self._elapsed(byte_start) > self.byte_timeout:
                return self._fail_rx("inter-byte timout")
            else:
                self._pause(1)
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

    def _recv_command(self):
        b = self._recv_bytes()
        if not b:
            return STATUS_ERR, "", self._last_rx_error or "no bytes received"
        try:
            return self._decode(b)
        except (ValueError, IndexError, UnicodeError) as e:
            self.flush()
            return STATUS_ERR, "", "decode error: " + str(e)

    def exchange(self, cmd, *data):
        """Send a command and return the raw reply tuple.

        Args:
            cmd: Command name.
            *data: Values to send.

        Returns:
            Tuple ``(status, reply_cmd, payload)`` without validation.
        """
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
        self._send_command(cmd, *data)
        status, reply_cmd, payload = self._recv_command()

        # Transport/decode failures: STATUS_ERR and empty cmd
        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        # Reply must echo the requested command name
        if reply_cmd != cmd:
            raise uRemoteError("unexpected reply: " + reply_cmd)
        return _unwrap_result(payload)

    def process(self):
        """Handle one incoming command and send a reply.

        Looks up a function named like the command in ``__main__``, calls it
        with the decoded arguments, and sends back the return value(s).
        """
        status, cmd, data = self._recv_command()
        if status != STATUS_OK or not cmd:
            return
        if not isinstance(data, list):
            data = [data]
        if hasattr(__main__, cmd):
            resp = getattr(__main__, cmd)(*data)
            if resp is None:
                resp = ()
            elif not isinstance(resp, tuple):
                resp = (resp,)
            self._send_command(cmd, *resp, status=STATUS_OK)
        else:
            self._send_command(cmd, "handler not found: " + cmd, status=STATUS_ERR)
