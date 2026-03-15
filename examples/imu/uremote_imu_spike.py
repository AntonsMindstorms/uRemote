from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor, ForceSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop, Axis
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

from uremote import uRemote

hub = PrimeHub()

ur = uRemote(Port.A)

#p.add_command('tst',1,1)

while True:
    x=hub.imu.acceleration(Axis.X, calibrated=True)
    y=hub.imu.acceleration(Axis.Y, calibrated=True)
    z=hub.imu.acceleration(Axis.Z, calibrated=True)
    ur.call("imu",int(x),int(y),int(z))
    #wait(10)
