__author__ = "Anton Vanhoucke & Ste7an"
__copyright__ = "Copyright 2023-2026, AntonsMindstorms.com"
__license__ = "GPL"
__version__ = "2.2.0-uremote"
__status__ = "Production"

# Upload this file into your Pybricks project together with uremote.py.
# This version talks to the BluePad32_uRemote Arduino firmware by using
# Pybricks uRemote instead of LPF2 PUPDevice modes.

from pybricks.parameters import Port, Color
from uremote import uRemote


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
        if abs(value) < deadzone:
            return 0
        return int(value) - 128

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

    def set_servo(self, servo_nr, pos, zero_is_mid=True):
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

    def servos(self, positions):
        for i in range(len(positions)):
            self.set_servo(i, positions[i])

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
    return _bp.set_servo(int(servo_nr), int(angle))


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