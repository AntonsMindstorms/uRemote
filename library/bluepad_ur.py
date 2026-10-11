__author__ = "Anton Vanhoucke & Ste7an"
__copyright__ = "Copyright 2023-2026, AntonsMindstorms.com"
__license__ = "GPL"
__version__ = "2.2.0-uremote"
__status__ = "Production"

# Upload this file into your Pybricks project. It includes a Pybricks-only
# uRemote client, so uremote.py is not required.
# Talks to the BluePad32_uRemote Arduino firmware over UART.

from pybricks.iodevices import UARTDevice
from pybricks.parameters import Port, Color
from pybricks.tools import StopWatch, wait

try:
    from micropython import const
except ImportError:
    def const(arg):
        return arg

# ---------- Embedded Pybricks uRemote client ----------
# Sync client subset of library/uremote.py: encode/decode and call.
# No ESP32 UART path, no process() server, and no async.

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
    """UART RPC client for Pybricks hubs.

    Args:
        port_or_uart: Pybricks Port, or a letter like "A".
        baudrate: Serial speed in bits per second, default 115200.
        wait_recv: Overall frame receive timeout in milliseconds, default 1000.
        uart_timeout: Per-read UART timeout in milliseconds, default 1000.
        power_pin: Pybricks 8V power pin, default 2 for LMS-ESP32. Set to 0 to disable.
    """

    def __init__(self, port_or_uart, baudrate=115200, wait_recv=1000, uart_timeout=1000, power_pin=2):
        self.byte_timeout = 10
        self.wait_recv = wait_recv
        self._last_rx_error = None
        self._watch = StopWatch()
        if isinstance(port_or_uart, str):
            port_or_uart = eval("Port." + port_or_uart)
        self.uart = UARTDevice(port_or_uart, timeout=uart_timeout, power_pin=power_pin)
        self.uart.set_baudrate(baudrate)
        self.uart.read_all()
        self._ticks = self._watch.time
        self._elapsed = lambda start: self._watch.time() - start
        self._pause = wait
        self._waiting = self.uart.waiting
        self._drain = self.uart.read_all

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

    def _send_bytes(self, payload):
        self.uart.write(self._packet(payload))

    def _read_byte(self):
        b = self.uart.read(1)
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

    def _encode(self, status, cmd, *argv):
        n = len(cmd)
        if n > MAX_CMD_LEN:
            raise uRemoteError("command name too long")
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

    def _finish_call(self, cmd, status, reply_cmd, payload):
        if status != STATUS_OK or not reply_cmd:
            raise uRemoteError(payload if isinstance(payload, str) else str(payload))
        if reply_cmd != cmd:
            self.flush()
            raise uRemoteError("unexpected reply: " + reply_cmd)
        return _unwrap_result(payload)

    def exchange(self, cmd, *data):
        """Send a command and return the raw reply tuple ``(status, reply_cmd, payload)``."""
        self._send_command(cmd, *data)
        return self._recv_command()

    def call(self, cmd, *data):
        """Call a remote command and return its result."""
        self.flush()
        self._send_command(cmd, *data)
        return self._finish_call(cmd, *self._recv_command())


FILL = 0x10
ZERO = 0x20
SET = 0x30
CONFIG = 0x40
WRITE = 0x80


class BluePad:
    """
    Class for using LMS-ESP32 / ESP32 running the BluePad32 uRemote firmware.

    The public methods follow the old BluePad LPF2 library as closely as
    possible, but the transport is now uRemote:

        self.ur.call("pad")
        self.ur.call("pix", n, r, g, b)
        self.ur.call("servo", n, angle)

    :param port: The port to which the BluePad32 uRemote board is connected.
    :type port: Port, for example Port.A
    """

    def __init__(self, port):
        self.ur = uRemote(port)
        self.nr_leds = 24
        self.arr_servos = [0] * 8

    # ---------- Generic uRemote helpers ----------

    def call(self, cmd, *args):
        """Call a raw uRemote command on the BluePad32 board."""
        return self.ur.call(cmd, *args)

    def _items(self, value):
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        return (value,)

    def _one(self, value):
        if isinstance(value, (tuple, list)):
            if len(value) == 0:
                return None
            return value[0]
        return value

    def _as_bytes(self, value):
        # uRemote byte-array replies usually arrive as bytes/bytearray. Some
        # versions wrap a single return value in a tuple/list.
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, (tuple, list)):
            if len(value) == 1 and isinstance(value[0], (bytes, bytearray)):
                return bytes(value[0])
            return bytes([int(v) & 0xFF for v in value])
        if value is None:
            return bytes([])
        return bytes([int(value) & 0xFF])

    def _bytes_arg(self, data):
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        if isinstance(data, int):
            return bytes([data & 0xFF])
        return bytes([int(v) & 0xFF for v in data])

    def _axis_signed(self, value, deadzone=10):
        v = int(value-128)
        if abs(v) < deadzone:
            return 0
        return v

    def _rgb(self, color):
        r, g, b = color
        return int(r), int(g), int(b)

    # ---------- Basic device status ----------

    def ping(self):
        """Return the remote board millis() value."""
        return self._one(self.call("ping"))

    def version(self):
        """Return the BluePad32 uRemote firmware version string."""
        return self._one(self.call("ver"))

    def status(self):
        """
        Return a tuple:
            connected, neopixel_count, neopixel_pin, bt_filter
        """
        return self._items(self.call("status"))

    def connected(self):
        """Return True when a gamepad is connected."""
        vals = self.status()
        return len(vals) > 0 and int(vals[0]) != 0

    # ---------- Gamepad reads ----------

    def gamepad(self, raw=False, deadzone=10, **kwargs):
        """
        Read the gamepad state. Joystick values are approximately -128..127 with 0 near center.

        Args:
            raw: When False (default), return decoded values. When True, return
                the firmware's 10-byte packet.
            **kwargs: Accepted for backwards compatibility; ``mode`` is ignored.

        Returns:
            raw=False:
                (left_x, left_y, right_x, right_y, buttons, dpad)
            raw=True:
                (connected, lx, ly, rx, ry, buttons, dpad, misc, brake, throttle)
        """
        data = self._as_bytes(self.call("pad"))
        if raw:
            return data
        if len(data) >= 7 and data[0]: # Enough data AND gamepad connected
            return (
                self._axis_signed(data[1], deadzone),
                self._axis_signed(data[2], deadzone),
                self._axis_signed(data[3], deadzone),
                self._axis_signed(data[4], deadzone),
                int(data[5]),
                int(data[6]),
            )
        return (0, 0, 0, 0, 0, 0)

    def joy(self, raw=False):
        """Return both sticks as lx, ly, rx, ry. Set raw=True for 0..255 values."""
        vals = self._items(self.call("joy"))
        vals = tuple([int(v) for v in vals[:4]])
        if raw:
            return vals
        return tuple([self._axis_signed(v) for v in vals])

    def joyl(self, raw=False):
        """Return left stick as lx, ly. Set raw=True for 0..255 values."""
        vals = self._items(self.call("joyl"))
        vals = tuple([int(v) for v in vals[:2]])
        if raw:
            return vals
        return tuple([self._axis_signed(v) for v in vals])

    def joyr(self, raw=False):
        """Return right stick as rx, ry. Set raw=True for 0..255 values."""
        vals = self._items(self.call("joyr"))
        vals = tuple([int(v) for v in vals[:2]])
        if raw:
            return vals
        return tuple([self._axis_signed(v) for v in vals])

    def btn(self):
        """Return buttons, dpad, misc."""
        vals = self._items(self.call("btn"))
        while len(vals) < 3:
            vals = vals + (0,)
        return int(vals[0]), int(vals[1]), int(vals[2])

    def imu(self):
        """
        Return six IMU values from the connected gamepad:
            gyro_x, gyro_y, gyro_z, accel_x, accel_y, accel_z

        The firmware returns six zeroes when no gamepad is connected.
        """
        vals = self._items(self.call("imu"))
        while len(vals) < 6:
            vals = vals + (0,)
        return tuple([int(v) for v in vals[:6]])

    def btns_pressed(self, btns, nintendo=False):
        """
        Decode the buttons word to a list of pressed button names.
        """
        bits_btns = [int(i) for i in bin(int(btns))[2:]]
        bits_btns.reverse()
        if nintendo:
            btn_val = ["B", "A", "Y", "X", "L", "R", "ZL", "ZR"]
        else:
            btn_val = ["X", "O", "[]", "V"]
        return [j for i, j in zip(bits_btns, btn_val) if i]

    def dpad_pressed(self, btns, nintendo=False):
        """
        Decode the dpad word to a list containing L, R, U, and/or D.
        """
        bits_btns = [int(i) for i in bin(int(btns))[2:]]
        bits_btns.reverse()
        if nintendo:
            btn_val = ["U", "D", "R", "L"]
        else:
            btn_val = ["D", "R", "L", "U"]
        return [j for i, j in zip(bits_btns, btn_val) if i]

    # ---------- NeoPixel helpers, compatible with the old library ----------

    def send(self, byte_vals):
        """
        Backwards-compatible helper for old 16-byte NeoPixel command packets.

        The old LPF2 library wrote packets directly to a PUPDevice mode. This
        uRemote version decodes the same packet command bytes and calls the
        corresponding remote functions.
        """
        vals = [int(v) & 0xFF for v in byte_vals]
        if len(vals) < 1:
            return None

        cmd = vals[0] & 0x70

        if cmd == CONFIG:
            count = vals[1] if len(vals) > 1 else self.nr_leds
            pin = vals[2] if len(vals) > 2 else 12
            return self.neopixel_init(count, pin)

        if cmd == FILL:
            if len(vals) < 4:
                return None
            return self.neopixel_fill((vals[1], vals[2], vals[3]), True)

        if cmd == ZERO:
            return self.neopixel_zero(True)

        if cmd == SET:
            if len(vals) < 6:
                return None
            nr_led = vals[1]
            start_led = vals[2]
            rgb = vals[3:3 + nr_led * 3]
            return self.neopixel_set_multi(start_led, nr_led, rgb, True)

        return None

    def neopixel_init(self, nr_leds, pin):
        """
        Initialize a NeoPixel string with the given number of LEDs and GPIO pin.
        """
        self.nr_leds = int(nr_leds)
        return self.call("np_cfg", int(nr_leds), int(pin))

    def neopixel_fill(self, color, write=True):
        """Fill all NeoPixels with color=(r,g,b)."""
        r, g, b = self._rgb(color)
        return self.call("fill", r, g, b)

    def neopixel_zero(self, write=True):
        """Clear all NeoPixels."""
        return self.call("clear")

    def neopixel_set(self, led_nr, color, write=True):
        """Set one NeoPixel at led_nr to color=(r,g,b)."""
        led_nr = int(led_nr)
        if led_nr >= self.nr_leds:
            print("error neopixel_set: led_nr larger than number of leds!")
            return None
        r, g, b = self._rgb(color)
        return self.call("pix", led_nr, r, g, b)

    def neopixel_set_multi(self, start_led, nr_led, led_arr, write=True):
        """
        Set multiple NeoPixels.

        led_arr should contain r,g,b,r,g,b,... values. The uRemote firmware
        exposes one-pixel writes, so this method sends one pix command per LED.
        """
        start_led = int(start_led)
        nr_led = int(nr_led)
        if len(led_arr) != 3 * nr_led:
            print("error neopixel_set_multi: nr_led does not correspond with led_arr")
            return None
        result = None
        for i in range(nr_led):
            r = int(led_arr[3 * i])
            g = int(led_arr[3 * i + 1])
            b = int(led_arr[3 * i + 2])
            result = self.neopixel_set(start_led + i, (r, g, b), True)
        return result

    # ---------- Servo helpers ----------

    def servo(self, servo_nr, pos, zero_is_mid=True):
        """Sets servo motor to the specified positions.

        Args:
            servo_nr (int): Servo to set. 0 is the first servo on the LMS-ESP32 board, so IO19.
            pos (int): Target position in range -90,90 (unless zero_is_mid is False)
            zero_is_mid (bool, optional): If True, 0 maps to 90° (midpoint). Defaults to True.
        """
        offset = 90 if zero_is_mid else 0
        pos = (pos + offset) % 181
        return self.call("servo", int(servo_nr), int(pos))

    def servo_off(self, servo_nr=None):
        """Detach one servo, or all servos when servo_nr is omitted."""
        if servo_nr is None:
            return self.call("servo_off")
        return self.call("servo_off", int(servo_nr))

    def servos(self, positions, zero_is_mid=True):
        """Sets multiple servo motors to the specified positions.

        Args:
            servo_tgts (list of int): Target positions for each servo motor.
            zero_is_mid (bool, optional): If True, 0 maps to 90° (midpoint). Defaults to True.
        """
        for i in range(len(positions)):
            self.servo(i, positions[i], zero_is_mid)

    # ---------- I2C helpers ----------

    def i2c_scan(self):
        """Return a list of 7-bit I2C addresses found on SDA=5, SCL=4."""
        reply = self._items(self.call("i2c_scan"))
        if len(reply) >= 2:
            count = int(reply[0])
            addresses = self._as_bytes(reply[1])
            return [int(v) for v in addresses[:count]]
        return []

    def i2c_read(self, address, length):
        """Read length bytes from an I2C device."""
        return self._as_bytes(self.call("i2c_read", int(address), int(length)))

    def i2c_read_reg(self, address, reg, length):
        """Write one register byte, then read length bytes from an I2C device."""
        return self._as_bytes(self.call("i2c_read_reg", int(address), int(reg), int(length)))

    def i2c_write(self, address, data):
        """
        Write data bytes to an I2C device.
        Returns (error, bytes_written). error=0 means ACK/success.
        """
        reply = self._items(self.call("i2c_write", int(address), self._bytes_arg(data)))
        while len(reply) < 2:
            reply = reply + (0,)
        return int(reply[0]), int(reply[1])

    def i2c_write_reg(self, address, reg, data):
        """
        Write one register byte followed by data bytes to an I2C device.
        Returns (error, bytes_written). error=0 means ACK/success.
        """
        reply = self._items(self.call("i2c_write_reg", int(address), int(reg), self._bytes_arg(data)))
        while len(reply) < 2:
            reply = reply + (0,)
        return int(reply[0]), int(reply[1])

    # Small I2C conveniences.
    def i2c_read_u8(self, address, reg):
        data = self.i2c_read_reg(address, reg, 1)
        if len(data) == 0:
            return None
        return int(data[0])

    def i2c_write_u8(self, address, reg, value):
        return self.i2c_write_reg(address, reg, bytes([int(value) & 0xFF]))

    # ---------- Bluetooth allow-list helpers ----------

    def bt_mac(self):
        """Return the currently connected controller MAC as XX:XX:XX:XX:XX:XX."""
        return self._one(self.call("bt_mac"))

    def bluetooth_address(self):
        """Alias for bt_mac()."""
        return self.bt_mac()

    def bt_allow(self, mac=None):
        """
        Read or set the allowed Bluetooth MAC address.
        mac must be in the form "xx:xx:xx:xx:xx:xx".
        """
        if mac is None:
            return self._one(self.call("bt_allow"))
        return self._one(self.call("bt_allow", str(mac)))

    def bt_filter(self, enabled=None):
        """Read or set the Bluetooth allow-list filter."""
        if enabled is None:
            return bool(int(self._one(self.call("bt_filter"))))
        return bool(int(self._one(self.call("bt_filter", bool(enabled)))))

    def bt_clear(self):
        """Clear the allowed Bluetooth address and disable the filter in RAM."""
        return self._one(self.call("bt_clear"))

    def bt_forget(self):
        """Tell Bluepad32 to forget stored Bluetooth pairing keys."""
        return self._one(self.call("bt_forget"))

    def save(self):
        """Save Bluetooth settings to EEPROM."""
        return self._one(self.call("save"))

    def load(self):
        """Load Bluetooth settings from EEPROM and apply them."""
        return self._one(self.call("load"))

    def defaults(self):
        """Reset Bluetooth settings in RAM to defaults. Call save() to persist."""
        return self._one(self.call("defaults"))


# Simple functions to import as blocks, kept compatible with the old file.

rgb_values = {
    Color.WHITE: (255, 255, 255),
    Color.RED: (255, 0, 0),
    Color.ORANGE: (255, 127, 0),
    Color.BLACK: (0, 0, 0),
    Color.NONE: (0, 0, 0),
    Color.YELLOW: (255, 255, 0),
    Color.GREEN: (0, 255, 0),
    Color.CYAN: (0, 255, 255),
    Color.BLUE: (0, 0, 255),
    Color.VIOLET: (127, 127, 255),
    Color.MAGENTA: (255, 0, 255),
    Color.GRAY: (127, 127, 127),
}


def bluepad_init(port_letter, nintendo=True):
    global _bp
    global _nintendo
    port = getattr(Port, port_letter)
    _bp = BluePad(port)
    _nintendo = nintendo


def get_left_stick_vertical():
    return _bp.gamepad()[1] / 128 * -100


def get_left_stick_horizontal():
    return _bp.gamepad()[0] / 128 * 100


def get_right_stick_horizontal():
    return _bp.gamepad()[2] / 128 * 100


def get_right_stick_vertical():
    return _bp.gamepad()[3] / 128 * -100


def get_direction_pad():
    return _bp.gamepad()[5]


def get_buttons():
    return _bp.gamepad()[4]


def color_convert(color, intensity):
    c = (0, 0, 0)
    if color in rgb_values:
        color = rgb_values[color]
    if isinstance(color, tuple):
        c = tuple([int(val * intensity) for val in color])
    return c


def set_neopixel(led_nr, color, intensity=1, write=True):
    return _bp.neopixel_set(led_nr, color_convert(color, intensity), write)


def init_neopixel(nr_leds, pin):
    return _bp.neopixel_init(nr_leds, pin)


def fill_neopixel(color, intensity=1, write=True):
    return _bp.neopixel_fill(color_convert(color, intensity), write)


def set_servo(servo_nr, angle):
    return _bp.servo(int(servo_nr), int(angle))


def servo_off(servo_nr=None):
    return _bp.servo_off(servo_nr)


def gamepad():
    return _bp.gamepad()


def joyl():
    return _bp.joyl()


def joyr():
    return _bp.joyr()


def imu():
    return _bp.imu()


def i2c_scan():
    return _bp.i2c_scan()


def i2c_read(address, length):
    return _bp.i2c_read(address, length)


def i2c_read_reg(address, reg, length):
    return _bp.i2c_read_reg(address, reg, length)


def i2c_write(address, data):
    return _bp.i2c_write(address, data)


def i2c_write_reg(address, reg, data):
    return _bp.i2c_write_reg(address, reg, data)


def bt_mac():
    return _bp.bt_mac()


def bt_allow(mac=None):
    return _bp.bt_allow(mac)


def bt_filter(enabled=None):
    return _bp.bt_filter(enabled)


def bt_clear():
    return _bp.bt_clear()


def bt_forget():
    return _bp.bt_forget()


def bt_save():
    return _bp.save()


def bt_load():
    return _bp.load()