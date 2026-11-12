#!/usr/bin/env python3
"""Rendered-page equality: fetch the pages and API outputs of a fresh test instance, normalise them (tests/harness/golden.py) and compare
their sha256 with tests/golden/SHA256SUMS. The regression check for the file split (no change in any hash allowed).

    python tests/test_pages_equal.py            # exit 0 = every hash equal
    python tests/test_pages_equal.py --update   # rewrite tests/golden (only when a change of the pages is intended)
Also collected by pytest (test_pages_equal). Normalisation: tests/golden/README.md.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import client, golden                       # noqa: E402
from harness.instance import Instance                    # noqa: E402

GOLDEN = HERE / "golden"


def compare():
    """-> list of problems (empty = equal)"""
    want = {}
    for line in (GOLDEN / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if line.strip():
            h, name = line.split(None, 1)
            want[name.strip()] = h
    with Instance(wav_only=True) as inst:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        golden.setup(api)
        got = golden.capture(inst.base_url)
    problems = []
    for name in sorted(set(want) | set(got)):
        if name not in got:
            problems.append(f"{name}: not captured")
        elif name not in want:
            problems.append(f"{name}: no golden hash")
        elif golden.sha(got[name]) != want[name]:
            old = (GOLDEN / name).read_bytes() if (GOLDEN / name).exists() else b""
            first = next((i for i, (a, b) in enumerate(zip(old, got[name])) if a != b), min(len(old), len(got[name])))
            problems.append(f"{name}: hash differs (golden {len(old)} bytes, now {len(got[name])}; first difference at byte {first}: "
                            f"golden {old[max(0, first - 30):first + 40]!r} vs now {got[name][max(0, first - 30):first + 40]!r})")
    return problems


def test_pages_equal():
    problems = compare()
    assert not problems, "\n".join(problems)


if __name__ == "__main__":
    if "--update" in sys.argv:
        import runpy
        sys.argv = [str(GOLDEN / "capture.py")]
        runpy.run_path(str(GOLDEN / "capture.py"), run_name="__main__")
        sys.exit(0)
    p = compare()
    print("\n".join(("FAIL " + x) for x in p) if p else "PASS all %d pages / outputs equal the golden hashes" % len(golden.TARGETS))
    sys.exit(1 if p else 0)
