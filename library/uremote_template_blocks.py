from pybricks.parameters import Port
from uremote import uRemote


def test(a, b):
    return a + b


ur = uRemote(Port.A)
print('Hello, Pybricks!')
while True:
    ur.call('imu', 100, 2000, 300)
