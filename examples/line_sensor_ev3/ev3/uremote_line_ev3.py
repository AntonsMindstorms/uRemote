from pybricks.hubs import EV3Brick
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = EV3Brick()

from uremote import uRemote

ur=uRemote(Port.S1)

s=StopWatch()
cnt=0
for i in range(1000):
    try:
        err,data=ur.call('sen')
        #print(data)
        #wait(100)
        #hex_str = ' '.join('{:02X}'.format(b) for b in data)
        #print(i,hex_str)
        cnt+=1
        #print(i,data)
    except:
        print('error -------')
print(s.time(),cnt)