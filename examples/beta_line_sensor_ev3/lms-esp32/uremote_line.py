# LMS-ESP32 MicroPython — run on the ESP32 with LMS-ESP32 firmware.
# Requires the line sensor driver and uremote.py from library/ on the board.
from line_sensor import LineSensor
from uremote import uRemote


def sen():
    return bytes(sensor.data())


ur = uRemote()
sensor = LineSensor()

sensor.ir_power(True)
sensor.mode_calibrated()
sensor.rgb_mode(sensor.LEDS_VALUES)

while True:
    ur.process()
