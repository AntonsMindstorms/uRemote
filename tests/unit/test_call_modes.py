"""Desktop tests for uRemote.call() in blocking and auto-detected async mode.

Run with ``python -m pytest tests/unit`` on a PC. A fake UART answers every
request frame, so no hardware is needed.
"""

import asyncio
import sys
import types
from pathlib import Path

machine = types.ModuleType("machine")
machine.UART = None
machine.Pin = lambda pin: pin
sys.modules.setdefault("machine", machine)

time_module = types.ModuleType("time")
time_module.ticks_ms = lambda: 0
time_module.ticks_diff = lambda a, b: a - b
time_module.sleep_ms = lambda ms: None
sys.modules["time"] = time_module

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "library"))
import uremote  # noqa: E402


class FakeUART:
    """Answers each request with the reply ``handler(cmd, *args)``."""

    def __init__(self, handler):
        self.handler = handler
        self.rx = bytearray()
        self.client = None

    def any(self):
        return len(self.rx)

    def read(self, n=None):
        n = len(self.rx) if n is None else n
        data, self.rx = bytes(self.rx[:n]), self.rx[n:]
        return data

    def write(self, frame):
        status, cmd, data = self.client._decode(frame[1 + uremote.PREAMBLE_LEN:])
        args = data if isinstance(data, list) else [data]
        reply = self.handler(cmd, *args)
        self.rx += self.client._packet(self.client._encode(uremote.STATUS_OK, cmd, *reply))


class AsyncFakeUART(FakeUART):
    """Pybricks UARTDevice under run_task(): read and write must be awaited."""

    async def read(self, n=None):
        return FakeUART.read(self, n)

    async def write(self, frame):
        FakeUART.write(self, frame)


def make_client(uart_class, handler=lambda cmd, *args: (sum(args),)):
    uart = uart_class(handler)
    machine.UART = lambda *a, **k: uart
    client = uremote.uRemote()
    uart.client = client
    return client


def test_call_blocks_and_returns_value():
    client = make_client(FakeUART)
    assert client.call("add", 2, 3) == 5
    assert client.exchange("add", 1, 1) == (uremote.STATUS_OK, "add", 2)


def test_call_returns_awaitable_under_run_task(monkeypatch):
    client = make_client(AsyncFakeUART)
    client._drain = lambda: FakeUART.read(client.uart)  # read_all() stays sync on Pybricks

    async def wait(ms):
        await asyncio.sleep(0)

    monkeypatch.setattr(uremote, "_IS_PYBRICKS", True)
    monkeypatch.setattr(uremote, "run_task", lambda: True, raising=False)
    monkeypatch.setattr(uremote, "wait", wait, raising=False)

    async def main():
        pending = client.call("add", 4, 5)
        assert not isinstance(pending, int)
        assert await pending == 9
        # Two tasks sharing one uRemote do not interleave transactions.
        results = await asyncio.gather(client.call("add", 1, 2), client.call_async("add", 10, 20))
        assert results == [3, 30]

    asyncio.run(main())
