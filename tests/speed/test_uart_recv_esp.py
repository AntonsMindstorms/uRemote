from time import ticks_ms,sleep_ms
from uremote import uRemote

ur = uRemote()

def test(a,b):
    print("test",a,b)
    return a==b,a+b,a*3

i=0
while True:
    ur.process()
    i+=1
    if i> 1000:
        i=0
    
