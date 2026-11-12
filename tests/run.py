#!/usr/bin/env python3
"""Run the API/command tests and write tests/reports/<platform>-<date>/ (results.json, report.md, junit.xml, instance.log).

    python tests/run.py                                   # start a disposable instance from a copy of player.py and test it
    python tests/run.py -k volume                         # any pytest selection arguments are passed through
    python tests/run.py --base-url http://HOST:PORT --allow-remote --confirm-target HOST:PORT [--osc-port N]
"""
import platform, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    try:
        import pytest
    except ImportError:
        sys.exit("pytest is not installed: pip install -r tests/requirements.txt")
    args = sys.argv[1:]
    if not any(a.startswith("--report-dir") for a in args):
        out = HERE / "reports" / f"{sys.platform}-{platform.machine().lower()}-{time.strftime('%Y%m%d-%H%M%S')}"
        args += ["--report-dir", str(out)]
    else:
        out = None
    code = pytest.main([str(HERE / "api"), str(HERE / "engine"), "-p", "no:cacheprovider", "-q", "-rfEs"] + args)      # engine/ = in-process tests of the audio engine (fake clock)
    if out:
        print(f"\nreport: {out}/report.md   (results.json, junit.xml alongside)")
    if not any(a.startswith("--base-url") for a in args):          # needs its own instance (a fixed library); skipped for external targets
        import subprocess
        pe = subprocess.run([sys.executable, str(HERE / "test_pages_equal.py")]).returncode
        print("page equality (tests/test_pages_equal.py): " + ("PASS" if pe == 0 else "FAIL"))
        pc = subprocess.run([sys.executable, str(HERE / "test_static_crlf.py")]).returncode
        print("CRLF static/ (tests/test_static_crlf.py): " + ("PASS" if pc == 0 else "FAIL"))
        pg = subprocess.run([sys.executable, str(HERE / "test_gates.py")]).returncode
        print("static gates + verify_move self-test (tests/test_gates.py): " + ("PASS" if pg == 0 else "FAIL"))
        ps = subprocess.run([sys.executable, "-I", str(HERE / "test_state_identity.py")], env={**__import__("os").environ, "SDL_AUDIODRIVER": "dummy"}, capture_output=True).returncode
        print("state identity (tests/test_state_identity.py): " + ("PASS" if ps == 0 else "FAIL"))
        pn = subprocess.run([sys.executable, "-I", str(HERE / "test_no_bare_state.py")]).returncode
        print("no bare shared state (tests/test_no_bare_state.py): " + ("PASS" if pn == 0 else "FAIL"))
        ph = subprocess.run([sys.executable, "-I", str(HERE / "test_state_hooks.py")], env={**__import__("os").environ, "SDL_AUDIODRIVER": "dummy"}, capture_output=True).returncode
        print("state hooks (tests/test_state_hooks.py): " + ("PASS" if ph == 0 else "FAIL"))
        pl = subprocess.run([sys.executable, "-I", str(HERE / "test_launchers.py")], capture_output=True).returncode
        print("launchers + deploy scripts (tests/test_launchers.py): " + ("PASS" if pl == 0 else "FAIL"))
        pv = subprocess.run([sys.executable, "-I", str(HERE / "test_module_version.py")], capture_output=True).returncode
        print("player / module version (tests/test_module_version.py): " + ("PASS" if pv == 0 else "FAIL"))
        pk = subprocess.run([sys.executable, "-I", str(HERE / "test_cold_start.py")], capture_output=True).returncode
        print("cold start: clean folder, existing folder, upgrade from the previous release (tests/test_cold_start.py): " + ("PASS" if pk == 0 else "FAIL"))
        pm = module_tests()
        pe = pe or pc or pg or ps or pn or ph or pl or pv or pk or pm
        code = int(code) or pe
    return int(code)


def module_tests():
    """The Companion module's own tests (node --test), then a check that they left no tracked file modified (2.8.0 follow-up: a run once left
    companion-module/companion/manifest.json changed). The manifest is put back from a copy taken before, whatever the tests did; any other tracked
    file that is dirty afterwards, and was not before, fails the check. Skipped without node or the module's node_modules."""
    import shutil, subprocess
    root = HERE.parent
    mod = root / "companion-module"
    if not shutil.which("node") or not (mod / "node_modules" / "@companion-module").is_dir():
        print("module tests (companion-module/test): SKIPPED (node or node_modules missing)")
        return 0

    def dirty():
        r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=str(root), capture_output=True, text=True)
        return {l[3:] for l in r.stdout.splitlines() if l.strip()} if r.returncode == 0 else None
    manifest = mod / "companion" / "manifest.json"
    keep = manifest.read_bytes() if manifest.exists() else None
    before = dirty()
    files = sorted(str(f.relative_to(mod)) for f in (mod / "test").glob("*.test.mjs"))
    r = subprocess.run(["node", "--test"] + files, cwd=str(mod), capture_output=True, text=True)
    if keep is not None and manifest.read_bytes() != keep:
        manifest.write_bytes(keep)                                  # restored: the tests changed it
        print("module tests: companion/manifest.json was rewritten by the tests and has been restored")
    after = dirty()
    ok = r.returncode == 0
    print("module tests (companion-module/test): " + ("PASS" if ok else "FAIL\n" + r.stdout[-1500:]))
    left = sorted((after or set()) - (before or set())) if before is not None and after is not None else []
    print("no tracked file left modified by the module tests: " + ("PASS" if not left else "FAIL " + ", ".join(left)))
    return 0 if ok and not left else 1


if __name__ == "__main__":
    sys.exit(main())
