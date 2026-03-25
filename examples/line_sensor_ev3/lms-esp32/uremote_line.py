import line_sensor
from uremote import uRemote

# callback for uremote
def sen():
    data = sensor.data()
    # format as bytes for efficiency
    return bytes(data)


ur = uRemote()
# Initialize sensor
sensor = LineSensor()

sensor.ir_power(True)

# # # Optionally start calibration
# sensor.rgb_mode(sensor.LEDS_VALUES_INVERTED)
# sensor.start_calibration()
# sleep(5)
# sensor.stop_calibration()
sensor.mode_calibrated()

sensor.rgb_mode(sensor.LEDS_VALUES)

# Read just light values
cnt=0
while 1:
    ur.process()
    cnt+=1
    if cnt==100:
        cnt=0
    # pos = sensor.position()
    # der = sensor.position_derivative()
        print(sensor.data())
        print(sensor.position_and_shape())
        
    