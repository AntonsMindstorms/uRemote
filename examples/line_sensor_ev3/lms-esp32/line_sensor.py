"""MicroPython driver for the LMS Line Sensor over I2C."""

from machine import I2C, Pin
from time import sleep, ticks_ms, ticks_diff
from collections import deque

__all__ = ["LineSensor"]
__version__ = "0.1.0"


class LineSensor:
    """
    MicroPython class for line following sensor via I2C.

    Args:
        scl_pin: SCL pin number (default 4)
        sda_pin: SDA pin number (default 5)
        device_addr: I2C device address (default 51)
    """

    # Command constants
    MODE_RAW = 0
    MODE_CALIBRATED = 1
    MODE_SAVING = 2
    MODE_CALIBRATING = 3
    CMD_GET_VERSION = 2
    CMD_DEBUG = 3
    CMD_CALIBRATE = 4
    CMD_IS_CALIBRATED = 5
    CMD_LOAD_CAL = 6  # load calibrated values from eeprom
    CMD_SAVE_CAL = 7  # save calibrated values to eeprom
    CMD_GET_MIN = 8
    CMD_GET_MAX = 9
    CMD_SET_MIN = 10
    CMD_SET_MAX = 11
    CMD_NEOPIXEL = 12  # neopixel: lednr, r, g, b, write
    CMD_LEDS = 13
    CMD_SET_EMITTER = 14  # optional for qtr sensors, 1 for on, 0 for zero.
    MAX_CMDS = 15

    # LED Modes
    LEDS_OFF = 0
    LEDS_VALUES = 1  # Firmware TODO: implement better thresholds.
    LEDS_VALUES_INVERTED = 2
    LEDS_POSITION = 3
    LEDS_MAX = 4

    POSITION = 8
    MIN = 9
    MAX = 10
    DERIVATIVE = 11
    SHAPE = 12
    VALUES = -1

    SHAPE_NONE = " "
    SHAPE_STRAIGHT = "|"
    SHAPE_T = "T"
    SHAPE_L_LEFT = "<"
    SHAPE_L_RIGHT = ">"
    SHAPE_Y = "Y"

    # Firmware TODO: This should be configurable so you can then weigh the outer sensors more.
    POSITION_WEIGHTS = (-127, -91, -54, -18, 18, 54, 91, 127)

    def __init__(self, scl_pin=4, sda_pin=5, device_addr=51):
        self.device_addr = device_addr
        self.i2c = I2C(1, scl=Pin(scl_pin), sda=Pin(sda_pin))
        self.pos_history = deque([(0, 0)] * 5, 5)
        self.current_rgb_mode = self.LEDS_OFF
        self.save_start_time = 0
        self.load_calibration()
        self.mode_calibrated()
        self.check_line_type() # Firmware TODO: implement auto-inversion after calibration.

    def position_and_shape(self):
        """
        Calculate the position, derivative, and shape of the line based on the calibrated/raw sensor values.
        """
        # Firmware TODO: implement this for faster performance.
        # Firmware TODO: implement auto-inversion after calibration. see check_inverted() for current placeholder implementation.
        values = self.data(self.VALUES)

        # Single pass: calculate min, max, sum
        min_value = values[0]
        max_value = values[0]
        total = 0
        for v in values:
            if v < min_value:
                min_value = v
            if v > max_value:
                max_value = v
            total += v

        # First check if we're off the line.
        # To do this we find out if the average is low and if the max is not much higher than the average. This is a sign of being off the line,
        if total < 160 and max_value < total // 4:
            self.pos_history.append((0, ticks_ms()))
            return 0, 0, self.SHAPE_NONE

        # Build an 8-bit mask where bit i is 1 when sensor i is above threshold.
        # 14% above average threshold: v > (total / 8) * 1.14 <=> v * 7 > total.
        mask = 0
        for i, v in enumerate(values):
            if v * 7 > total:
                mask |= 1 << i

        shape = self.SHAPE_STRAIGHT
        if (mask & 0b00111100) == 0b00111100:  # bits 2..5 set, regardless of other bits
            shape = self.SHAPE_T
        elif (mask & 0b00001110) == 0b00001110:  # bits 1..3 set, regardless of other bits
            shape = self.SHAPE_L_RIGHT
        elif (mask & 0b01110000) == 0b01110000:  # bits 4..6 set, regardless of other bits
            shape = self.SHAPE_L_LEFT
        # Y-shape placeholder: middle bits 3 and 4 should be off,
        # and both left and right sides should have signal.
        elif (mask & 0b00011000) == 0 and (mask & 0b00000111) != 0 and (mask & 0b11100000) != 0:
            shape = self.SHAPE_Y

        # Calculate weighted sum directly in the -127..127 domain.
        weighted_sum = 0
        total_adjusted = 0
        for i in range(8):
            v = values[i]
            adjusted = v - min_value
            weighted_sum += self.POSITION_WEIGHTS[i] * adjusted
            total_adjusted += adjusted

        if total_adjusted == 0:
            self.pos_history.append((0, ticks_ms()))
            return 0, 0, self.SHAPE_NONE

        # This is a sign-safe integer step for: round(weighted_sum/total_light)
        # which keeps position estimates balanced left vs right and is 6x - 10x faster.
        if weighted_sum >= 0:
            pos = (weighted_sum + (total_adjusted // 2)) // total_adjusted
        else:
            pos = -((-weighted_sum + (total_adjusted // 2)) // total_adjusted)

        # Age is about 7ms per item in deque. -2 = 14ms ago.
        der = pos - self.pos_history[-2][0]

        self.pos_history.append((pos, ticks_ms()))
        return pos, der, shape

    def data(self, *indices):
        """
        Read sensor data of choice.
        
        Args:
            indices: Optional list of indices to read. If empty, returns all values.
        
        Returns:
            list: Sensor data values.
        
        Example:
            sensor.data(sensor.VALUES, sensor.POSITION)  # returns light values and position
        """
        if self.current_mode < 2: # Not calibrating or saving, safe to read from sensor.
            # Try twice. Sometimes it fails. Firmware TODO.
            try:
                d = list(self.i2c.readfrom(self.device_addr, 13))
            except:
                d = list(self.i2c.readfrom(self.device_addr, 13))
        elif self.current_mode == self.MODE_SAVING:
            # Avoid reading from the sensor while it's saving, which can cause it to crash.
            # Firmware TODO.
            if ticks_diff(ticks_ms(), self.save_start_time + 1500) > 0:
                self.write_command(self.last_mode)
                self.current_mode = self.last_mode
                print("Calibration stored in EEPROM")
            d = [0] * 13
        else:
            d = [0] * 13

        if not indices:
            return d
        else:
            retval = []
            for idx in indices:
                if idx == self.VALUES:
                    if self.black_line:
                        retval += [255 - v for v in d[0:8]]
                    else:
                        retval += d[0:8]
                else:
                    retval.append(d[idx])
            return retval

    def position(self):
        """
        Read the position value.
        """
        return self.data(self.POSITION)

    def position_derivative(self):
        """
        Read the position derivative value.
        """
        return self.data(self.DERIVATIVE)

    def shape(self):
        """
        Read the shape value.
        """
        return self.data(self.SHAPE)

    def write_command(self, command):
        """
        Write a 1-byte command to the sensor.
        """
        if type(command) is int:
            command = [command]
        self.i2c.writeto(self.device_addr, bytes(command))

    def mode_raw(self):
        """Set sensor to raw mode."""
        self.current_mode = self.last_mode = self.MODE_RAW
        self.write_command(self.MODE_RAW)

    def mode_calibrated(self):
        """Set sensor to calibrated mode."""
        self.current_mode = self.last_mode = self.MODE_CALIBRATED
        self.write_command(self.MODE_CALIBRATED)

    def start_calibration(self):
        """Start sensor calibration."""
        # Firmware TODO: turn off LEDs during calibration, which can interfere with light readings.
        # Firmware TODO: implement calibration timer
        # so you can self.write_command((self.CMD_CALIBRATE, 5)) to calibrate for 5 seconds,
        # then automatically switch back to the previous mode.
        print("Starting calibration")
        self.last_mode = self.current_mode
        self.current_mode = self.MODE_CALIBRATING
        self.write_command((self.CMD_LEDS, self.LEDS_OFF))
        self.write_command(self.CMD_CALIBRATE)

    def stop_calibration(self, save=True):
        """Persist calibration values to the sensor EEPROM."""
        # Firmware TODO: output 0 values while saving to avoid read timouts.
        print("Stopping calibration, save new values:", save)
        self.write_command(self.MODE_CALIBRATED)
        self.write_command(self.current_rgb_mode)
        self.check_line_type()
        self.write_command(self.last_mode)
        if save:
            self.write_command(self.CMD_SAVE_CAL)
            self.save_start_time = ticks_ms()
            self.current_mode = self.MODE_SAVING
        else:
            self.current_mode = self.last_mode
            
    def check_line_type(self):
        """Check if the line is black or white after calibration."""
        # Firmware TODO: implement auto-inversion after calibration 
        values = list(self.i2c.readfrom(self.device_addr, 8))
        avg = sum(values) // len(values)
        self.black_line = avg > 128 # Most sensors return white, lots of light.
        print("Line is", "black" if self.black_line else "white")

    def calibrate(self, duration=5, save=True):
        """
        Convenience method to calibrate for a certain duration and then save if desired.
        
        Args:
            duration: Duration in seconds to run the calibration (default 5)
            save: Whether to save the calibration values to EEPROM after calibration (default True)
        """
        self.start_calibration()
        sleep(duration)
        self.stop_calibration(save=save)
        if save: 
            sleep(1.5)
            print("Calibration stored in EEPROM")
            self.current_mode = self.last_mode

    def ir_power(self, power):
        """Set the IR emitter power."""
        # Firmware TODO: implement power levels for emitters, not just on/off.
        self.write_command((self.CMD_SET_EMITTER, 1 if power else 0))

    def rgb_mode(self, mode):
        """Set the onboard RGB LED mode."""
        self.current_rgb_mode = mode
        self.write_command((self.CMD_LEDS, mode))

    def load_calibration(self):
        """Load previously saved calibration values from EEPROM."""
        self.write_command(self.CMD_LOAD_CAL)


# Example usage:
if __name__ == "__main__":
    # Initialize sensor
    sensor = LineSensor()

    sensor.ir_power(True)

    # # # Optionally start calibration
    # sensor.rgb_mode(sensor.LEDS_INVERTED)
    # sensor.start_calibration()
    # sleep(5)
    # sensor.mode_calibrated()

    sensor.rgb_mode(sensor.LEDS_VALUES)

    # Read just light values
    for i in range(1000):
        # pos = sensor.position()
        # der = sensor.position_derivative()
        print(sensor.position_and_shape())
        sleep(0.5)