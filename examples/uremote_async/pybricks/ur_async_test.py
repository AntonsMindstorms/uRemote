from pybricks.hubs import PrimeHub
from pybricks.parameters import Axis, Direction, Port
from pybricks.pupdevices import Motor
from pybricks.tools import multitask, run_task, wait

from uremote_async import uRemote
import uremote_async

print(uremote_async.__version__)

prime_hub = PrimeHub()
ur = uRemote(Port.C)

#motor = Motor(Port.F, Direction.CLOCKWISE)
dc_pct = 0


async def main1():
    while True:
        await ur.call_async(
            "spike_data",
            round(prime_hub.imu.rotation(Axis.X)),
            round(prime_hub.imu.rotation(Axis.Y)),
            round(prime_hub.imu.rotation(Axis.Z)),
        )

        print("kp",await ur.call_async("Kp"))

        # Give another RPC task an opportunity to acquire uRemote.
        await wait(0)


async def main2():
    global dc_pct

    prime_hub.imu.reset_heading(0)

    while True:
        dc_pct = await ur.call_async("motor")
        print("motor",dc_pct)

        # Give another RPC task an opportunity to acquire uRemote.
        await wait(0)


async def main():
    await multitask(
        main1(),
        main2(),
    )


run_task(main())