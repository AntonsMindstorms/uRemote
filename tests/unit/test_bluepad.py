"""BluePad methods must behave the same blocking and under run_task()."""

import asyncio
import sys
import types

import pytest

import fakes
from fakes import AsyncFakeUART, FakeUART, machine, pretend_pybricks_run_task

# bluepad_ur imports Pybricks modules at the top; stub the two names it uses.
class _AnyAttr:
    def __getattr__(self, name):
        return name

parameters = types.ModuleType("pybricks.parameters")
parameters.Port, parameters.Color = _AnyAttr(), _AnyAttr()
sys.modules.setdefault("pybricks", types.ModuleType("pybricks"))
sys.modules["pybricks.parameters"] = parameters

import bluepad_ur  # noqa: E402

PAD = bytes([1, 178, 128, 128, 128, 5, 2, 0, 0, 0])  # connected, left_x = +50


def handler(cmd, *args):
    if cmd == "pad":
        return (PAD,)
    if cmd == "status":
        return (1, 24, 12, 0)  # connected, neopixel count, pin, bt filter
    return ()


def make_bluepad(uart_class, monkeypatch=None):
    uart = uart_class(handler)
    machine.UART = lambda *a, **k: uart
    bp = bluepad_ur.BluePad(1)
    uart.client = bp.ur
    if monkeypatch:
        pretend_pybricks_run_task(monkeypatch, module=bluepad_ur, client=bp.ur)
    return bp, uart


def run_both_modes(monkeypatch, method_name, *args):
    """Run bp.<method>(*args) blocking and awaited; return both (result, requests)."""
    bp, uart = make_bluepad(FakeUART)
    blocking = (getattr(bp, method_name)(*args), uart.requests)

    bp, uart = make_bluepad(AsyncFakeUART, monkeypatch)
    result = asyncio.run(_await(getattr(bp, method_name)(*args)))
    return blocking, (result, uart.requests)


async def _await(awaitable):
    return await awaitable


def test_embedded_client_is_the_shared_one():
    # bluepad_ur must not carry its own transport; it is generated from uremote.py.
    assert "_drive_async" in vars(bluepad_ur.uRemote)


@pytest.mark.parametrize("method, args, expected_requests", [
    ("gamepad", (), [("pad", ())]),
    ("servos", ([0, 10],), [("servo", (0, 90)), ("servo", (1, 100))]),
    ("neopixel_set_multi", (0, 2, [1, 2, 3, 4, 5, 6]), [("pix", (0, 1, 2, 3)), ("pix", (1, 4, 5, 6))]),
    ("connected", (), [("status", ())]),
])
def test_same_result_and_calls_in_both_modes(monkeypatch, method, args, expected_requests):
    blocking, awaited = run_both_modes(monkeypatch, method, *args)
    assert blocking == awaited
    assert blocking[1] == expected_requests


def test_gamepad_decodes_axes():
    bp, _ = make_bluepad(FakeUART)
    assert bp.gamepad() == (50, 0, 0, 0, 5, 2)


def test_multi_call_methods_are_not_interleaved(monkeypatch):
    bp, uart = make_bluepad(AsyncFakeUART, monkeypatch)

    async def servo_task():
        await bp.servos([1, 2, 3])

    async def pad_task():
        await bp.gamepad()

    async def main():
        await asyncio.gather(servo_task(), pad_task())

    asyncio.run(main())
    # servos() holds the lock for all three calls, so "pad" comes strictly after.
    assert [cmd for cmd, _ in uart.requests] == ["servo", "servo", "servo", "pad"]


def test_forgotten_await_on_bluepad_is_reported(monkeypatch):
    bp, _ = make_bluepad(AsyncFakeUART, monkeypatch)

    async def main():
        forgotten = bp.gamepad()
        with pytest.raises(bluepad_ur.uRemoteError, match="await"):
            bp.gamepad()
        forgotten._coro.close()  # avoid the "never awaited" warning

    asyncio.run(main())
