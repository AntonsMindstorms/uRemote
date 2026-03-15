from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor, GyroSensor, InfraredSensor, TouchSensor, UltrasonicSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = EV3Brick()


from uremote import uRemote

ur = uRemote(Port.S2)

i=0
s=StopWatch()
for j in range(100):
    #uu.send_command('test',i,i+2)
    #cmd,data = ur.receive_command()
    cmd,data = ur.call('test',i,i+2)
    print(cmd,data)
    #wait(1)
    i+=1
    if i> 255:
        i=0
print(i,s.time())
