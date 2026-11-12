"""The one time source of the player (docs/split-plan.md 5.3): tests replace it with a fake clock via install().

Always call it as `clock.monotonic()`, `clock.time()`, `clock.sleep(s)`. Never `from cpl.clock import monotonic`: that copies the
function and the fake clock would be ignored (a gate in tests/test_gates.py checks this).
`asyncio.sleep` and `time.time_ns` (names of temp files) are not part of the seam.
"""
import time as _time

_src = _time


def monotonic():
    return _src.monotonic()


def time():
    return _src.time()


def sleep(seconds):
    return _src.sleep(seconds)


def install(src):
    """Tests only: use `src` (an object with monotonic / time / sleep) as the clock; None restores the real one."""
    global _src
    _src = src or _time
