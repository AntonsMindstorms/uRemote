from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor, ForceSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = PrimeHub()



from microremote import MicroRemote

ur = uRemote(Port.A)


while True:
    ack, resp = ur.call('joy')
    x,y,pressed = resp
    print(x,y,pressed)
    hub.display.off()
    hub.display.pixel(x*5//256,y*5//256)
    
    but = hub.buttons.pressed()
    if Button.LEFT in but:
        print('left')
        ur.call('led',-1)
    elif Button.RIGHT in but:
        ur.call('led',1)
        print('right')
    wait(10)