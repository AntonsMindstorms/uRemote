from uremote import uRemote

ur = uRemote()

i=0

def motor():
    value = i*2 
    return value

def Kp():
    value = i*3
    return value

def spike_data(x, y, z):
    print(x,y,z)
    return

while True:
    ur.process()
    i+=1
    if i>1000:
        i=0