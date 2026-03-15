from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor, GyroSensor, InfraredSensor, TouchSensor, UltrasonicSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = EV3Brick()

from uremote import uRemote

ur = uRemote(Port.S2, wait_recv=10000)
print(ur.decode(b'\x03cmdS\x03catN\x03123'))

def test(a,b):
    print("test",a,b)
    return a==b,a+b,a*3

i=0
while True:
    ur.process()
    i+=1
    if i> 1000:
        i=0
    
