"""Desktop tests for uRemote.call() in blocking and auto-detected async mode.

Run with ``python -m pytest tests/unit`` on a PC. A fake UART answers every
request frame, so no hardware is needed.
"""

import asyncio

import pytest

from fakes import AsyncFakeUART, FakeUART, make_client, pretend_pybricks_run_task, uremote


def test_call_blocks_and_returns_value():
    client = make_client(FakeUART)
    assert client.call("add", 2, 3) == 5
    assert client.exchange("add", 1, 1) == (uremote.STATUS_OK, "add", 2)


def test_esp32_path_never_touches_run_task():
    # On ESP32 run_task is None; calling it would raise TypeError.
    assert uremote.run_task is None
    client = make_client(FakeUART)
    assert client.call("add", 1, 1) == 2


def test_call_returns_awaitable_under_run_task(monkeypatch):
    client = make_client(AsyncFakeUART)
    pretend_pybricks_run_task(monkeypatch, client=client)

    async def main():
        pending = client.call("add", 4, 5)
        assert not isinstance(pending, int)
        assert await pending == 9
        # Two tasks sharing one uRemote do not interleave transactions.
        async def task(a, b):
            return await client.call("add", a, b)

        results = await asyncio.gather(task(1, 2), task(10, 20))
        assert results == [3, 30]

    asyncio.run(main())


def test_forgotten_await_is_reported_on_next_call(monkeypatch):
    client = make_client(AsyncFakeUART)
    pretend_pybricks_run_task(monkeypatch, client=client)

    async def main():
        forgotten = client.call("add", 1, 1)  # no await: nothing is sent
        with pytest.raises(uremote.uRemoteError, match="await"):
            client.call("add", 2, 2)
        forgotten._coro.close()  # avoid the "never awaited" warning
        # The error clears itself, so correct code works straight after.
        assert await client.call("add", 3, 3) == 6

    asyncio.run(main())


def test_process_refuses_to_run_under_run_task(monkeypatch):
    client = make_client(AsyncFakeUART)
    pretend_pybricks_run_task(monkeypatch, client=client)
    with pytest.raises(uremote.uRemoteError, match="run_task"):
        client.process()


@pytest.mark.parametrize("hint", ["wiring", "process()"])
def test_no_reply_error_says_what_to_check(hint):
    client = make_client(FakeUART, handler=lambda cmd, *a: ())
    client.uart.write = lambda frame: None  # remote never answers
    client.wait_recv = 0
    with pytest.raises(uremote.uRemoteError, match=hint):
        client.call("add", 1, 1)


def test_unawaited_result_explains_itself_when_printed(monkeypatch):
    # print(ur.call(...)) inside run_task() must not show an opaque generator.
    client = make_client(AsyncFakeUART)
    pretend_pybricks_run_task(monkeypatch, client=client)

    async def main():
        pending = client.call("add", 1, 2)
        assert "Use await" in str(pending) and "Use await" in repr(pending)
        assert "add" in str(pending)
        assert await pending == 3

    asyncio.run(main())


def test_attribute_call_is_shorthand_for_call():
    client = make_client(FakeUART)
    assert client.add(2, 3) == 5
    sent = []
    client.uart.write = lambda frame, w=client.uart.write: (sent.append(frame), w(frame))[1]
    client.add(1, 2)
    client.call("add", 1, 2)
    assert sent[0] == sent[1]


def test_attribute_call_leaves_real_and_private_names_alone():
    client = make_client(FakeUART)
    assert client.flush.__func__ is uremote.uRemote.flush
    with pytest.raises(AttributeError):
        client._missing
    with pytest.raises(AttributeError):
        client.__await__


def test_attribute_call_is_awaitable_under_run_task(monkeypatch):
    client = make_client(AsyncFakeUART)
    pretend_pybricks_run_task(monkeypatch, client=client)

    async def main():
        assert await client.add(4, 5) == 9

    asyncio.run(main())
