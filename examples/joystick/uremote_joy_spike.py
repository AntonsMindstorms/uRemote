from pybricks.hubs import PrimeHub
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = PrimeHub()

from uremote import uRemote

ur=uRemote(Port.A)


while True:
    err,data=ur.call('joy')
    x,y,press=data
    print(x,y)
    hub.display.off()
    hub.display.pixel(x//52,y//52,100)