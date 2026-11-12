#!/usr/bin/env python3
"""A checkout of static/ with CRLF line endings (Windows autocrlf) must serve the identical pages: the sha256 of GET / and /help equals the golden ones.
    python tests/test_static_crlf.py"""
import shutil, sys, tempfile, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import golden                       # noqa: E402
from harness.appcopy import copy_app            # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden"


def main():
    want = {l.split()[1]: l.split()[0] for l in (GOLDEN / "SHA256SUMS").read_text().splitlines() if l.strip()}
    tmp = Path(tempfile.mkdtemp(prefix="cptest-crlf-"))
    try:
        copy_app(tmp, PROJECT)                       # player.py + cpl/ + static/ ...
        shutil.rmtree(tmp / "static")                # ... then static/ again, with CRLF line endings
        (tmp / "static").mkdir()
        n = 0
        for f in (PROJECT / "static").iterdir():
            data = f.read_bytes()
            assert b"\r" not in data, f"{f.name} has CR in the repository copy"
            (tmp / "static" / f.name).write_bytes(data.replace(b"\n", b"\r\n"))
            n += 1
        fails = []
        with Instance(wav_only=True, project_dir=tmp) as inst:
            for name, path in (("root.html", "/"), ("help.html", "/help"), ("stage.html", "/stage"), ("variables.html", "/variables")):
                h = golden.sha(urllib.request.urlopen(inst.base_url + path).read())
                ok = h == want[name]
                print(("PASS " if ok else "FAIL ") + f"CRLF static/ ({n} files): GET {path} equals the golden page")
                if not ok:
                    fails.append(path)
        sys.exit(1 if fails else 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_crlf_static_serves_identical_pages():
    import subprocess
    assert subprocess.run([sys.executable, __file__]).returncode == 0


if __name__ == "__main__":
    main()
