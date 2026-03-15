from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor, GyroSensor, InfraredSensor, TouchSensor, UltrasonicSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = EV3Brick()

from uremote import uRemote

ur=uRemote(Port.S1)

hub.screen.clear()

while True:
    ack, resp = ur.call('joy')
    x,y,pressed = resp
    print(x,y,pressed)
    hub.screen.draw_circle(x*178//256,128-y//2,2,True)
    if pressed==1:
        hub.screen.clear()
    
    but = hub.buttons.pressed()
    if Button.LEFT in but:
        print('left')
        ur.call('led',-1)
    elif Button.RIGHT in but:
        ur.call('led',1)
        print('right')
    wait(10)