from pybricks.hubs import PrimeHub
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = PrimeHub()

from uremote import uRemote

ur = uRemote(Port.A)


while True:
    but = hub.buttons.pressed()
    if Button.LEFT in but:
        print('left')
        ur.call('led',-1)
    elif Button.RIGHT in but:
        ur.call('led',1)
        print('right')
    wait(100)