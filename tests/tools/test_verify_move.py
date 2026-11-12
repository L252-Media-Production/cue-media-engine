#!/usr/bin/env python3
"""Self-test of verify_move.py:  python tests/tools/test_verify_move.py
One fixture is a moved function (allowed rewrites only); three are not: a changed function, an added statement,
an added await. Only the first may pass. Also collected by tests/test_gates.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_move import compare_sources   # noqa: E402

OLD = '''
import time
live_deck = None
_pending_n = 0

def request_warm():
    return 1

def stop_all():
    global live_deck, _pending_n
    _pending_n += 1
    live_deck = None
    request_warm()
    return time.monotonic()

async def fetch(x):
    y = await x.get()
    return y
'''
CFG = {"state_names": {"live_deck": "live_deck", "_pending_n": "pending_n"},
       "module_funcs": {"request_warm": "warm"}, "module_of": {"request_warm": "warm"},
       "allowed_added": ["warm_marker"], "expr_rewrites": [{"old": "time.monotonic()", "new": "clock.monotonic()"}]}

# the new tree: stop_all in module "transport", request_warm in module "warm"
GOOD = {"transport.py": '''
def stop_all():
    S.pending_n += 1
    S.live_deck = None
    warm.request_warm()
    return clock.monotonic()

async def fetch(x):
    y = await x.get()
    return y
''', "warm.py": '''
def request_warm():
    return 1
'''}
# the state variables themselves are moved to state.py; they are compared as assignments
GOOD["state.py"] = "live_deck = None\npending_n = 0\n"

def variant(**changes):
    d = dict(GOOD)
    for k, (a, b) in changes.items():
        assert a in d[k], (k, a)
        d[k] = d[k].replace(a, b)
    return d

CASES = [
    ("moved function, allowed rewrites only", GOOD, True),
    ("a changed function (constant 1 -> 2)", variant(**{"warm.py": ("return 1", "return 2")}), "request_warm"),
    ("an added statement", variant(**{"transport.py": ("    S.live_deck = None\n", "    S.live_deck = None\n    print('x')\n")}), "stop_all"),
    ("an added await", variant(**{"transport.py": ("    warm.request_warm()\n", "    await warm.request_warm()\n")}), "stop_all"),
    ("a dropped state rewrite (bare name left)", variant(**{"transport.py": ("S.live_deck = None", "live_deck = None")}), "stop_all"),
    ("a statement removed", variant(**{"transport.py": ("    S.pending_n += 1\n", "")}), "stop_all"),
]


def local_case():
    """a state name that is an ordinary local in one function: not rewritten there when the map says so, and the map option can fail"""
    old = "pending = None\ndef f():\n    pending = 1\n    return pending\ndef g():\n    global pending\n    pending = 2\n"
    new_ok = {"a.py": "def f():\n    pending = 1\n    return pending\ndef g():\n    S.pending = 2\n", "state.py": "pending = None\n"}
    new_bad = {"a.py": "def f():\n    S.pending = 1\n    return S.pending\ndef g():\n    S.pending = 2\n", "state.py": "pending = None\n"}
    base = {"state_names": {"pending": "pending"}}
    r = []
    r.append(("local name kept in f (map says so)", not compare_sources({"o.py": old}, new_ok, dict(base, local_names_in={"f": ["pending"]})), True))
    r.append(("local name kept in f but map silent -> fails", bool(compare_sources({"o.py": old}, new_ok, base)), True))
    r.append(("local wrongly rewritten -> fails", bool(compare_sources({"o.py": old}, new_bad, dict(base, local_names_in={"f": ["pending"]}))), True))
    return r


def main():
    bad = 0
    for name, ok, want in local_case():
        bad += ok != want
        print(("ok   " if ok == want else "FAIL ") + name)
    for name, new, expect in CASES:
        problems = compare_sources({"old.py": OLD}, new, CFG)
        ok = not problems
        expect_ok = expect is True
        good = ok if expect_ok else (len(problems) == 1 and expect in problems[0])      # a bad case must fail for the intended reason, and only that
        status = "ok  " if good else "FAIL"
        bad += not good
        print(f"{status} {name}: {'passes' if ok else 'fails (' + problems[0] + ')'}")
    print("verify_move self-test:", "PASS" if not bad else f"FAIL ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
