#!/usr/bin/env python3
"""verify_move.py for a whole step: compares every cpl/*.py (not helpers/) at OLD_REV with the working tree.

    python tests/tools/verify_step.py OLD_REV [--map tests/tools/maps/x.json]
"""
import argparse, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_move as V   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old_rev")
    ap.add_argument("--map")
    a = ap.parse_args()
    old = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", a.old_rev, "cpl/"], capture_output=True, text=True, check=True).stdout.split()
    old = [f for f in old if f.endswith(".py") and "/helpers/" not in f and not f.endswith("__init__.py")]
    new = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "cpl").glob("*.py") if p.name != "__init__.py")
    argv = ["verify_move.py", a.old_rev, "WORKTREE", "--old-files", *old, "--new-files", *new] + (["--map", a.map] if a.map else [])
    sys.argv = argv
    return V.main()


if __name__ == "__main__":
    sys.exit(main())
