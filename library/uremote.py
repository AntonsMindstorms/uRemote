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

# Wire protocol
STATUS_OK = const(0)
STATUS_ERR = const(1)
MAX_FRAME = const(255)
MIN_FRAME = const(6)
PREAMBLE = b'<$MU'
PREAMBLE_LEN = const(4)

# Typed field tags (ASCII code)
_T_BOOL = const(66)
_T_NUM = const(78)
_T_BYTES = const(65)
_T_STR = const(83)

# Platform backends
ESP32 = const(1)
PYBRICKS = const(2)

if sys.platform == 'esp32':
    _PLATFORM = ESP32
else:
    _PLATFORM = PYBRICKS

_IS_PYBRICKS = _PLATFORM == PYBRICKS

if _IS_PYBRICKS:
    from pybricks.iodevices import UARTDevice
    from pybricks.tools import StopWatch, wait
    RX_PIN, TX_PIN = 0, 0
else:
    import time
    import machine
    from lms_esp32 import RX_PIN, TX_PIN


class uRemoteError(Exception):
    """Raised when a remote call fails (transport, protocol, or handler error)."""


def _as_values(data):
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def _unwrap_result(payload):
    """Turn decoded payload into None, a scalar, or a tuple."""
    values = _as_values(payload)
    if len(values) == 0:
        return None
    if len(values) == 1:
        return values[0]
    return tuple(values)


def _normalize_handler_args(data):
    if isinstance(data, list):
        return data
    return [data]


def _normalize_handler_result(resp):
    if resp is None:
        return ()
    if isinstance(resp, tuple):
        return resp
    return (resp,)


class uRemote:
    """UART RPC client/server for Pybricks hubs and ESP32 boards.
    
        Args:
            port_or_uart: Pybricks Port or ESP32 UART id.
            baudrate: Serial speed in bits per second, default 115200.
            wait_recv: Overall frame receive timeout in milliseconds, default 1000.
            uart_timeout: Per-read UART timeout in milliseconds, default 1000.
            rx: ESP32 RX pin (ignored on Pybricks), default from firmware.
            tx: ESP32 TX pin (ignored on Pybricks), default from firmware.
        """

    def __init__(
        self,
        port_or_uart=1,
        baudrate=115200,
        wait_recv=1000,
        uart_timeout=1000,
        rx=RX_PIN,
        tx=TX_PIN,
    ):
        self.byte_timeout = 10
        self.wait_recv = wait_recv
        self._last_rx_error = None

        if _IS_PYBRICKS:
            self._watch = StopWatch()
            self.uart = UARTDevice(port_or_uart, timeout=uart_timeout)
            self.uart.set_baudrate(baudrate)
        else:
            self.uart = machine.UART(
                port_or_uart,
                baudrate=baudrate,
                rx=machine.Pin(rx),
                tx=machine.Pin(tx),
                timeout=uart_timeout,
            )

    def _ticks(self):
        if _IS_PYBRICKS:
            return self._watch.time()
        return time.ticks_ms()

    def _elapsed(self, start):
        if _IS_PYBRICKS:
            return self._watch.time() - start
        return time.ticks_diff(time.ticks_ms(), start)

    def _pause(self, ms):
        if _IS_PYBRICKS:
            wait(ms)
        else:
            time.sleep_ms(ms)

    def _waiting(self):
        if _IS_PYBRICKS:
            return self.uart.waiting()
        return self.uart.any()

    def _read(self, n=1):
        return self.uart.read(n)

    def _read_byte(self):
        b = self._read(1)
        if b:
            return b[0]
        return None

    def _read_all(self):
        if _IS_PYBRICKS:
            self.uart.read_all()
        else:
            self.uart.read()

    def _write(self, b):
        self.uart.write(b)

    def _fail_rx(self, error):
        self.flush()
        self._last_rx_error = error
        return b''

    def _error_reply(self, message):
        return STATUS_ERR, "", message

    def flush(self):
        """Discard all bytes waiting in the UART receive buffer."""
        while self._waiting():
            self._read_all()

    def _send_bytes(self, payload):
        frame = PREAMBLE + payload
        if len(frame) > MAX_FRAME:
            raise uRemoteError("frame too large")
        self._write(bytes([len(frame)]) + frame)

    def _recv_bytes(self):
        self._last_rx_error = None
        start = self._ticks()

        while self._elapsed(start) < self.wait_recv and self._waiting() == 0:
            self._pause(1)

        if self._waiting() == 0:
            return self._fail_rx("timeout: no length byte")

        length = self._read_byte()
        if length is None:
            return self._fail_rx("timeout: no length byte")
        if length < MIN_FRAME or length > MAX_FRAME:
            return self._fail_rx("invalid frame length")

        payload = bytearray()
        total_start = self._ticks()
        byte_start = total_start
        preamble_index = 0

        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                return self._fail_rx("timeout: incomplete frame")

            if self._waiting():
                b = self._read_byte()
                if b is None:
                    return self._fail_rx("timeout: incomplete frame")

                payload.append(b)

                if preamble_index < PREAMBLE_LEN:
                    if b != PREAMBLE[preamble_index]:
                        return self._fail_rx("preamble mismatch")
                    preamble_index += 1

                byte_start = self._ticks()
            else:
                if self._elapsed(byte_start) > self.byte_timeout:
                    return self._fail_rx("timeout: inter-byte gap")
                self._pause(1)

        return bytes(payload[PREAMBLE_LEN:])

    def _encode(self, status, cmd, *argv):
        # Header: status byte, cmd length, cmd name
        encoded = bytes([status, len(cmd)]) + bytes(cmd, 'utf-8')
        for arg in argv:
            encoded += self._encode_value(arg)
        return encoded

    def _encode_value(self, arg):
        if type(arg) == bool:
            return bytes([_T_BOOL, 1, 1 if arg else 0])
        if type(arg) == int:
            s = str(arg)
            return bytes([_T_NUM, len(s)]) + bytes(s, 'utf-8')
        if type(arg) == bytes:
            return bytes([_T_BYTES, len(arg)]) + arg
        if type(arg) == str:
            return bytes([_T_STR, len(arg)]) + bytes(arg, 'utf-8')
        raise TypeError("unsupported type")

    def _decode(self, encoded):
        status = encoded[0]
        cmd_len = encoded[1]
        cmd = str(encoded[2:2 + cmd_len], 'utf-8')

        decoded = []
        p = 2 + cmd_len

        while p < len(encoded):
            t = encoded[p]
            length = encoded[p + 1]
            p += 2
            payload = encoded[p:p + length]
            p += length
            decoded.append(self._decode_value(t, payload))

        if len(decoded) == 1:
            decoded = decoded[0]
        return status, cmd, decoded

    def _decode_value(self, tag, payload):
        if tag == _T_NUM:
            return int(str(payload, 'utf-8'))
        if tag == _T_BYTES:
            return payload
        if tag == _T_STR:
            return str(payload, 'utf-8')
        if tag == _T_BOOL:
            return bool(payload[0])
        raise ValueError("unknown type " + str(tag))

    def _send_command(self, cmd, *data, status=STATUS_OK):
        self._send_bytes(self._encode(status, cmd, *data))

    def _recv_command(self):
        b = self._recv_bytes()
        if b:
            try:
                return self._decode(b)
            except (ValueError, IndexError, UnicodeError) as e:
                self.flush()
                return self._error_reply("decode error: " + str(e))
        return self._error_reply(self._last_rx_error or "no bytes received")

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

        data = _normalize_handler_args(data)

        if hasattr(__main__, cmd):
            resp = _normalize_handler_result(getattr(__main__, cmd)(*data))
            self._send_command(cmd, *resp, status=STATUS_OK)
        else:
            self._send_command(cmd, "handler not found: " + cmd, status=STATUS_ERR)
