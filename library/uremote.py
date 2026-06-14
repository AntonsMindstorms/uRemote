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
MIN_FRAME = const(6)
ESP32 = const(1)
PYBRICKS = const(2)

if sys.platform == 'esp32':
    _platform = ESP32
else:
    _platform = PYBRICKS

if _platform == 2:
    from pybricks.iodevices import UARTDevice
    from pybricks.parameters import Port
    from pybricks.tools import StopWatch, wait
    RX_PIN, TX_PIN = 0, 0
else:
    import time
    import machine
    from lms_esp32 import RX_PIN, TX_PIN

PREAMBLE = b'<$MU'


class uRemoteError(Exception):
    pass


def _as_values(data):
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


class uRemote:
    def __init__(
        self,
        port_or_uart=1,
        baudrate=115200,
        wait_recv=1000,
        uart_timeout=1000,
        rx=RX_PIN,
        tx=TX_PIN,
    ):
        """Create a uRemote UART client or server.

        wait_recv: overall frame receive timeout in ms
        uart_timeout: per-read UART timeout in ms
        byte_timeout: inter-byte gap timeout in ms (fixed at 10)
        """
        self.byte_timeout = 10
        self.wait_recv = wait_recv
        self._last_rx_error = None
        if _platform == PYBRICKS:
            self._watch = StopWatch()

        if _platform == PYBRICKS:
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
        if _platform == 2:
            return self._watch.time()
        return time.ticks_ms()

    def _elapsed(self, start):
        if _platform == 2:
            return self._watch.time() - start
        return time.ticks_diff(time.ticks_ms(), start)

    def _pause(self, ms):
        if _platform == 1:
            time.sleep_ms(ms)
        else:
            wait(ms)

    def _waiting(self):
        if _platform == 2:
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
        if _platform == 2:
            self.uart.read_all()
        else:
            self.uart.read()

    def _write(self, b):
        self.uart.write(b)

    def flush(self):
        while self._waiting():
            self._read_all()

    def send_bytes(self, payload):
        frame = PREAMBLE + payload
        if len(frame) > MAX_FRAME:
            raise uRemoteError("frame too large")
        self._write(bytes([len(frame)]) + frame)

    def receive_bytes(self):
        self._last_rx_error = None
        start = self._ticks()

        while self._elapsed(start) < self.wait_recv and self._waiting() == 0:
            self._pause(1)

        if self._waiting() == 0:
            self.flush()
            self._last_rx_error = "timeout: no length byte"
            return b''

        length = self._read_byte()
        if length is None:
            self.flush()
            self._last_rx_error = "timeout: no length byte"
            return b''
        if length < MIN_FRAME or length > MAX_FRAME:
            self.flush()
            self._last_rx_error = "invalid frame length"
            return b''

        payload = bytearray()
        total_start = self._ticks()
        byte_start = total_start
        preamble_index = 0

        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                self.flush()
                self._last_rx_error = "timeout: incomplete frame"
                return b''

            if self._waiting():
                b = self._read_byte()
                if b is None:
                    self.flush()
                    self._last_rx_error = "timeout: incomplete frame"
                    return b''

                payload.append(b)

                if preamble_index < 4:
                    if b != PREAMBLE[preamble_index]:
                        self.flush()
                        self._last_rx_error = "preamble mismatch"
                        return b''
                    preamble_index += 1

                byte_start = self._ticks()
            else:
                if self._elapsed(byte_start) > self.byte_timeout:
                    self.flush()
                    self._last_rx_error = "timeout: inter-byte gap"
                    return b''
                self._pause(1)

        return bytes(payload[4:])

    def encode(self, status, cmd, *argv):
        encoded = bytes([status, len(cmd)]) + bytes(cmd, 'utf-8')
        for arg in argv:
            if type(arg) == bool:
                encoded += bytes([66, 1, 1 if arg else 0])
            elif type(arg) == int:
                s = str(arg)
                encoded += bytes([78, len(s)]) + bytes(s, 'utf-8')
            elif type(arg) == bytes:
                encoded += bytes([65, len(arg)]) + arg
            elif type(arg) == str:
                encoded += bytes([83, len(arg)]) + bytes(arg, 'utf-8')
            else:
                raise TypeError("unsupported type")
        return encoded

    def decode(self, encoded):
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

            if t == 78:
                decoded.append(int(str(payload, 'utf-8')))
            elif t == 65:
                decoded.append(payload)
            elif t == 83:
                decoded.append(str(payload, 'utf-8'))
            elif t == 66:
                decoded.append(bool(payload[0]))
            else:
                raise ValueError("unknown type " + str(t))
        if len(decoded) == 1:
            decoded = decoded[0]
        return status, cmd, decoded

    def send_command(self, cmd, *data, status=STATUS_OK):
        self.send_bytes(self.encode(status, cmd, *data))

    def receive_command(self):
        """Receive and decode one frame. Returns (status, cmd, data)."""
        b = self.receive_bytes()
        if b:
            try:
                return self.decode(b)
            except (ValueError, IndexError, UnicodeError) as e:
                self.flush()
                return STATUS_ERR, "", "decode error: " + str(e)
        return STATUS_ERR, "", self._last_rx_error or "no bytes received"

    def exchange(self, cmd, *data):
        """Send a command and return the raw (status, reply_cmd, payload) tuple."""
        self.send_command(cmd, *data)
        return self.receive_command()

    def call(self, cmd, *data):
        self.send_command(cmd, *data)
        status, reply_cmd, payload = self.receive_command()

        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        if reply_cmd != cmd:
            raise uRemoteError("unexpected reply: " + reply_cmd)

        values = _as_values(payload)
        if len(values) == 0:
            return None
        if len(values) == 1:
            return values[0]
        return tuple(values)

    def process(self):
        status, cmd, data = self.receive_command()

        if status != STATUS_OK or not cmd:
            return
        if not isinstance(data, list):
            data = [data]
        if hasattr(__main__, cmd):
            func = getattr(__main__, cmd)
            resp = func(*data)
            if resp is None:
                resp = ()
            elif not isinstance(resp, tuple):
                resp = (resp,)
            self.send_command(cmd, *resp, status=STATUS_OK)
        else:
            self.send_command(cmd, "handler not found: " + cmd, status=STATUS_ERR)
