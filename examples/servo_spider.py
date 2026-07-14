# Spider Using an LMS-ESP32 board and four Geekservos
# Get the board here:
# https://antonsmindstorms.com/product/wifi-python-esp32-board-for-mindstorms/
# Get the model here:
# https://www.antonsmindstorms.com/product/servo-inventor-spider-pdf-building-instructions/

from pybricks.hubs import InventorHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch
from motor_sync import linear_interpolation, AMHTimer
from umath import sin

from bluepad_ur import BluePad

w = StopWatch()
hub = InventorHub()
timer = AMHTimer()
us = UltrasonicSensor(Port.C)
us.lights.on()

bp = BluePad(Port.D)

# Remember which upper leg servo is where. CHECK!!
FRS = 3  # 3 = Pin 22 Front Right Servo and so on.
FLS = 2  # 2 = Pin 21
BRS = 1  # 1 = Pin 20
BLS = 0  # 0 = Pin 19

# Make a walking animation loop 2500ms long.
# Due to the build of the model, servos in front can move between 10 and -10 degrees.
# This moves slowly from -60 to 10 whil the leg is on the ground
# and then fast from 10 back to -60 while the leg is up.
servo_keyframes_b = [
    (0, -40),
    (2000, 10),
    (2500, -40),
]

# In the back servos can move between positions -10 and 60 without colliding with the model.
servo_keyframes_f = [
    (0, -10),
    (2000, 40),
    (2500, -10),
]

# The legs are on the ground, -40, during the first 2000ms, then up for the last 500ms.
lower_leg_keyframes = [(0, 50), (2000, 50), (2250, -10), (2500, 50)]

frll = Motor(Port.E)  # f.ront r.ight l.ower l.eg
flll = Motor(Port.F)  # inverted direction
brll = Motor(Port.A)  # inverted direction
blll = Motor(Port.B)

# Create interpolation functions to calculate intermediate animation points
# Revers and offset animations per leg, as needed.
# flul = front left upper leg and so on. 625 = 2500 /4.
blul_function = linear_interpolation(
    servo_keyframes_b, smoothing=1, time_offset=1 * 625
)
blll_function = linear_interpolation(
    lower_leg_keyframes, smoothing=1, time_offset=1 * 625
)

flul_function = linear_interpolation(
    servo_keyframes_f, smoothing=1, time_offset=0 * 625
)
flll_function = linear_interpolation(
    lower_leg_keyframes, smoothing=1, time_offset=0 * 625, scale=-1
)

brul_function = linear_interpolation(
    servo_keyframes_b, smoothing=1, time_offset=3 * 625
)
brll_function = linear_interpolation(
    lower_leg_keyframes, smoothing=1, time_offset=3 * 625, scale=-1
)

frul_function = linear_interpolation(
    servo_keyframes_f, smoothing=1, time_offset=2 * 625
)
frll_function = linear_interpolation(
    lower_leg_keyframes, smoothing=1, time_offset=2 * 625
)



# Scale motor positions left and right differently to allow for turns
l_scale = r_scale = 1
prev_servo_targets = servo_targets = [0, 0, 0, 0]

# Set servos to initial positions
servo_targets[FRS] = int(frul_function(0, scale=r_scale))
servo_targets[BRS] = int(brul_function(0, scale=r_scale))
servo_targets[BLS] = int(blul_function(0, scale=l_scale))
servo_targets[FLS] = int(flul_function(0, scale=l_scale))

for i in range(4):
    bp.servo(i, servo_targets[i])
    wait(1000)

# Unlike the regular stopwatch, you can slow this one down.
timer = AMHTimer()
while 1:
    t = timer.time()

    # Get remote control stick values (-127, 127)

    left_x, left_y, right_x, right_y, _, _ = bp.gamepad()

    # Connect stick values to steering
    speed = left_y if abs(left_y) > 10 else 0
    turn = left_x if abs(left_x) > 10 else 0

    if abs(turn) < 100:  # We're moving straight, or with a slight cruve
        if speed > 0:
            timer.rate((speed**2 + turn**2) ** 0.5 * 10)
        else:  # Speed is negative
            timer.rate((speed**2 + turn**2) ** 0.5 * -10)

        left_t = right_t = t

        if turn > 0:  # Set servo scaling for the next control loop.
            r_scale = 1 - turn / 100
            l_scale = 1
        else:
            l_scale = 1 + turn / 100
            r_scale = 1

    else:  # We're rotating in place.
        timer.rate(turn * 15)
        left_t = -t
        right_t = t
        l_scale = r_scale = 1

    # Calculate leg positions for the current time, and send them to the motors.

    frll.track_target(frll_function(right_t))
    flll.track_target(flll_function(left_t))
    blll.track_target(blll_function(left_t))
    brll.track_target(brll_function(right_t))

    servo_targets[FRS] = int(frul_function(right_t, scale=r_scale))
    servo_targets[BRS] = int(brul_function(right_t, scale=r_scale))
    servo_targets[BLS] = int(blul_function(left_t, scale=l_scale))
    servo_targets[FLS] = int(flul_function(left_t, scale=l_scale))

    # Limit the rate of change of servo targets to limit current draw.
    for i in range(4):
        diff = servo_targets[i] - prev_servo_targets[i]
        if abs(diff) > 5:
            servo_targets[i] = prev_servo_targets[i] + (5 if diff > 0 else -5)

    bp.servos(servo_targets)
    prev_servo_targets = list(servo_targets)
