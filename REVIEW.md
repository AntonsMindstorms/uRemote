# uRemote Pre-Release Review

**Date:** 2026-06-14 (updated)  
**Audience:** Pybricks beginners  
**Platforms in focus:** EV3 ↔ LMS-ESP32, Prime/Technic hub ↔ ESP32

---

## Executive summary

All items from the pre-release checklist are addressed. The library is ready for classroom use with the README and [`examples/hello/`](examples/hello/) as entry points.

---

## Overall assessment

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Beginner-friendliness | **4 / 5** | README onboarding, hello examples, clear `call()` API |
| Wording / API consistency | **4 / 5** | uRemote naming; status-byte protocol; Python API unified |
| Code correctness | **4.5 / 5** | Core bugs fixed; `.ubp` copies synced from `library/uremote.ubl` |
| Error clarity | **4 / 5** | Distinct transport errors in Python; MicroBlocks `last error` reporter |

**Verdict:** Ready for Pybricks beginners with README + hello examples. MicroBlocks users should check `uremote last error` after failed calls.

---

## Completed in final pass

- [x] Differentiate transport error strings in `receive_bytes()` / `receive_command()`
- [x] Remove `sayIt` from preamble mismatch (embedded `.ubp` modules replaced)
- [x] Deduplicate embedded `.ubp` uremote modules from `library/uremote.ubl`
- [x] MicroBlocks `uremote last error` reporter after failed `call`
- [x] Signal unknown type codes in MicroBlocks `_decode`
- [x] Add `examples/hello/` — Prime and EV3 hub + ESP32 ping pair
- [x] Document fixed MicroBlocks timeouts in README and `.ubl` description
- [x] Fix `LineSensor()` import in `uremote_line.py`
- [x] Encode-time / send-time check for 255-byte frame limit
- [x] Remove unused platform constants (simplified to Pybricks vs ESP32)
- [x] LMS-ESP32 prerequisite notes on line sensor examples

---

## Completed earlier

- Retire MicroRemote; unify on **uRemote**
- Single Python API: `ur = uRemote(Port.A)`
- `call()` returns value / raises `uRemoteError`; `exchange()` for debugging
- Status-byte wire protocol (no `_ack` / `_err` suffixes)
- Core `process()` bugs; handler-not-found replies; README onboarding
- Examples updated for new API

---

## Optional follow-ups (not blocking)

- Auto-generate `.ubp` uremote module from `uremote.ubl` in CI to prevent drift
- Configurable MicroBlocks timeouts (would need module variables + block inputs)
- Unit tests runnable off-hub for encode/decode/framing
