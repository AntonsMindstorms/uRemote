# Hardware fun

Small, playful programs that double as the **hardware release checks** for
uRemote. Each prints `PASS` or `FAIL: <what to do>` and shows a face on the hub.
Run them on real hardware before merging transport changes or tagging a release;
the desktop tests (`python -m pytest tests/unit`) cannot cover real UARTs.

## Setup

- Pybricks hub (SPIKE Prime / Technic) on `Port.A`, wired to an LMS-ESP32.
- LMS-ESP32 runs `esp32_playground.py`. Copy `library/uremote.py` to both the
  ESP32 and the hub as `uremote.py`.
- For pb_g_gamepad_rave the ESP32 runs the BluePad32 uRemote firmware instead, and the hub
  needs `library/bluepad_ur.py`. After editing `uremote.py` run
  `python tools/sync_bluepad.py` first.

## The checks

| Example | What it checks | Must pass before merge |
|---|---|---|
| `pb_a_ping_pong.py` | Blocking `call()`; calls/s within ~10% of the baseline from `main` | yes |
| `pb_b_two_dancers.py` | Two tasks share one `uRemote` under `multitask()`; the lock holds | yes |
| `pb_c_oops_forgot_await.py` | A forgotten `await` raises a clear error, and parallel awaits don't false-trigger | yes |
| `pb_e_pulled_plug.py` | Slow/crashing handlers and an unplugged cable give clear errors; the hub stays responsive and recovers | yes |
| `pb_f_async_esp32.py` | ESP32 server runs asyncio (`esp32_async_server.py`) and keeps its own tasks running while serving; run this one with that server instead of `esp32_playground.py` | yes |
| `pb_g_gamepad_rave.py` | `BluePad` under `run_task()`; set `SYNC = True` to check the blocking path too | yes (both variants) |
| `esp32_client_ping.py` | ESP32 / OpenMV as a blocking client; no `run_task` needed; memory not worse | yes |

For OpenMV AE3 see also `../hello/openmv_ae3_ping.py`.

## Baseline

Before changing the transport, run pb_a_ping_pong and `esp32_client_ping.py` on `main` and
write down calls/s and `gc.mem_free()` so later runs have something to compare to.
