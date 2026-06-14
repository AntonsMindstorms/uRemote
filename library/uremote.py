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

_EV3=const(0x01)
_ESP32=const(0x02)
_ESP32_S2=const(0x03)
_ESP8266=const(0x04)
_SPIKE=const(0x05)
_MAC=const(0x06)
_H7=const(0x07)
_K210=const(0x08)
_PYBRICKS=const(0x09)

platforms = {
    'linux':_EV3, # EV3. TODO This might not be precise enough for python3 running on Linux laptops
    'esp32':_ESP32,
    'Espressif ESP32-S2':_ESP32_S2,
    'esp8266':_ESP8266,
    'OpenMV4P-H7':_H7,
    'OpenMV3-M7':_H7,
    'LEGO Learning System Hub':_SPIKE,
    'darwin':_MAC,
    'MaixPy':_K210,
}
try:
    _platform = platforms[sys.platform]
    del(platforms)
except KeyError:
    _,_,_platform,_=sys.implementation
    if "EV3" in _platform or "Prime" in _platform or "LEGO" in _platform:
        _platform=_PYBRICKS
    del(platforms)

# ---------- Platform detection ----------

if _platform ==_PYBRICKS:
    from pybricks.iodevices import UARTDevice
    from pybricks.parameters import Port
    from pybricks.tools import StopWatch
    RX_PIN, TX_PIN = 0,0
elif _platform == _ESP32:
    import time
    import machine
    from lms_esp32 import RX_PIN, TX_PIN

# ---------- Constants ----------

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

        if _platform==_PYBRICKS:
            self.uart = UARTDevice(port_or_uart, timeout=uart_timeout)
            self.uart.set_baudrate(baudrate)
        elif _platform==_ESP32:
            self.uart = machine.UART(
                port_or_uart,
                baudrate=baudrate,
                rx=machine.Pin(rx),
                tx=machine.Pin(tx),
                timeout=uart_timeout,
            )

    def _now(self):
        if _platform==_PYBRICKS:
            return StopWatch()
        elif _platform==_ESP32:
            return time.ticks_ms()

    def _elapsed(self, start):
        if _platform==_PYBRICKS:
            return start.time()
        elif _platform==_ESP32:
            return time.ticks_diff(time.ticks_ms(), start)

    def _waiting(self):
        if _platform==_PYBRICKS:
            return self.uart.waiting()
        elif _platform==_ESP32:
            return self.uart.any()

    def _read(self, n=1):
        return self.uart.read(n)

    def _read_all(self):
        if _platform==_PYBRICKS:
            self.uart.read_all()
        elif _platform==_ESP32:
            self.uart.read()

    def _write(self, b):
        self.uart.write(b)

    def flush(self):
        while self._waiting():
            self._read_all()

    def send_bytes(self, payload):
        b = PREAMBLE + payload
        b = bytes([len(b)]) + b
        self._write(b)

    def receive_bytes(self):
        start = self._now()

        while self._elapsed(start) < self.wait_recv and self._waiting() == 0:
            if _platform == _ESP32:
                time.sleep_ms(1)

        if self._waiting() == 0:
            self.flush()
            return b''

        length = self._read(1)[0]

        payload = bytearray()
        total_start = self._now()
        byte_start = self._now()
        preamble_index = 0

        while len(payload) < length:
            if self._elapsed(total_start) > self.wait_recv:
                self.flush()
                return b''

            if self._waiting():
                b = self._read(1)
                if b:
                    payload.append(b[0])

                    if preamble_index < 4:
                        if b[0] != PREAMBLE[preamble_index]:
                            self.flush()
                            return b''
                        preamble_index += 1

                    byte_start = self._now()
            else:
                if self._elapsed(byte_start) > self.byte_timeout:
                    self.flush()
                    return b''
                if _platform==_ESP32:
                    time.sleep_ms(1)

        return bytes(payload[4:])

    def encode(self, cmd, *argv):
        encoded=bytes([len(cmd)])+bytes(cmd,'utf-8')
        for arg in argv:
            if type(arg)==bool:
                encoded+=bytes([66,1, 1 if arg else 0])
            elif type(arg)==int:
                s=str(arg)
                encoded+=bytes([78,len(s)])+bytes(s,'utf-8')
            elif type(arg)==bytes:
                encoded+=bytes([65,len(arg)])+arg
            elif type(arg)==str:
                encoded+=bytes([83,len(arg)])+bytes(arg,'utf-8')
            else:
                raise TypeError("unsupported type")
        return encoded

    def decode(self, encoded):
        cmd_len = encoded[0]
        cmd = str(encoded[1:1 + cmd_len],"utf-8")

        decoded = []
        p = 1 + cmd_len

        while p < len(encoded):
            t = encoded[p]
            length = encoded[p + 1]
            p += 2

            payload = encoded[p:p + length]
            p += length

            if t == 78:
                decoded.append(int(str(payload,'utf-8')))
            elif t == 65:
                decoded.append(payload)
            elif t == 83:
                decoded.append(str(payload,'utf-8'))
            elif t == 66:
                decoded.append(bool(payload[0]))
            else:
                raise ValueError("Unknown type code")
        if len(decoded)==1:
            decoded = decoded[0]
        return cmd, decoded

    def send_command(self, cmd, *data):
        self.send_bytes(self.encode(cmd, *data))

    def receive_command(self):
        """Receive and decode one frame. Advanced/debug use."""
        b = self.receive_bytes()
        if b:
            try:
                return self.decode(b)
            except (ValueError, IndexError, UnicodeError):
                self.flush()
                return "!ERROR", "decode error"
        return "!ERROR", "no bytes received"

    def exchange(self, cmd, *data):
        """Send a command and return the raw (reply_cmd, payload) tuple."""
        self.send_command(cmd, *data)
        return self.receive_command()

    def call(self, cmd, *data):
        self.send_command(cmd, *data)
        reply_cmd, payload = self.receive_command()

        if reply_cmd == "!ERROR":
            raise uRemoteError(payload)
        if reply_cmd == cmd + "_err":
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        if reply_cmd != cmd + "_ack":
            raise uRemoteError("unexpected reply: " + reply_cmd)

        values = _as_values(payload)
        if len(values) == 0:
            return None
        if len(values) == 1:
            return values[0]
        return tuple(values)

    def process(self):
        cmd, data = self.receive_command()
        if cmd == "!ERROR":
            self.send_command(cmd + "_err", "recv error")
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
            self.send_command(cmd + "_ack", *resp)
        else:
            self.send_command(cmd + "_err", "handler not found: " + cmd)
