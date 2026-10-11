"""Shared desktop fakes: a UART that answers requests, and stubbed hardware modules.

Importing this module stubs ``machine`` and ``time`` (so ``library/uremote.py``
imports on a PC) and puts ``library/`` on ``sys.path``.
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "library"))
import uremote  # noqa: E402


class FakeUART:
    """Answers each request with the reply ``handler(cmd, *args)``.

    Every request is also recorded in ``self.requests`` as ``(cmd, args)``.
    """

    def __init__(self, handler):
        self.handler = handler
        self.rx = bytearray()
        self.client = None
        self.requests = []

    def any(self):
        return len(self.rx)

    def read(self, n=None):
        n = len(self.rx) if n is None else n
        data, self.rx = bytes(self.rx[:n]), self.rx[n:]
        return data

    def write(self, frame):
        status, cmd, data = self.client._decode(frame[1 + uremote.PREAMBLE_LEN:])
        args = data if isinstance(data, list) else [data]
        self.requests.append((cmd, tuple(args)))
        reply = self.handler(cmd, *args)
        self.rx += self.client._packet(self.client._encode(uremote.STATUS_OK, cmd, *reply))


class AsyncFakeUART(FakeUART):
    """Pybricks UARTDevice under run_task(): read and write must be awaited."""

    # Each I/O call suspends once, like real UART I/O, so tasks can interleave.
    async def read(self, n=None):
        await asyncio.sleep(0)
        return FakeUART.read(self, n)

    async def write(self, frame):
        await asyncio.sleep(0)
        FakeUART.write(self, frame)


def add_handler(cmd, *args):
    return (sum(args),)


def make_client(uart_class, handler=add_handler):
    uart = uart_class(handler)
    machine.UART = lambda *a, **k: uart
    client = uremote.uRemote()
    uart.client = client
    return client


def pretend_pybricks_run_task(monkeypatch, module=uremote, client=None):
    """Make ``module`` behave as on Pybricks inside run_task()."""

    async def wait(ms):
        await asyncio.sleep(0)

    monkeypatch.setattr(module, "_IS_PYBRICKS", True)
    monkeypatch.setattr(module, "run_task", lambda: True, raising=False)
    monkeypatch.setattr(module, "wait", wait, raising=False)
    if client is not None:
        # uart.read_all() stays synchronous on Pybricks.
        client._drain = lambda: FakeUART.read(client.uart)
