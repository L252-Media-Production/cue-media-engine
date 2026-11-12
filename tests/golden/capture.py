#!/usr/bin/env python3
"""Write the golden files and tests/golden/SHA256SUMS from a fresh disposable test instance (WAV-only fixed library).

    python tests/golden/capture.py            # writes tests/golden/*
    python tests/golden/capture.py --out DIR  # writes somewhere else (used to prove two captures are identical)
"""
import argparse, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from harness import client, golden                      # noqa: E402
from harness.instance import Instance                   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE))
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    with Instance(wav_only=True) as inst:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        golden.setup(api)
        got = golden.capture(inst.base_url)
    lines = []
    for name, data in sorted(got.items()):
        (out / name).write_bytes(data)
        lines.append(f"{golden.sha(data)}  {name}")
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
