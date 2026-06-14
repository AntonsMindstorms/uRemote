from pybricks.hubs import EV3Brick
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = EV3Brick()

from uremote import uRemote, uRemoteError

ur=uRemote(Port.S1)

s=StopWatch()
cnt=0
for i in range(1000):
    try:
        data = ur.call('sen')
        cnt += 1
    except uRemoteError:
        print('error -------')
print(s.time(),cnt)