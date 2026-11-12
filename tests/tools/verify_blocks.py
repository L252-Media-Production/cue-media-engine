#!/usr/bin/env python3
"""Checks that code moved out of `if <cond>:` blocks into module bodies is the same code (docs/split-plan.md, step P2).

  verify_blocks.py OLD_REV OLD_FILE NEW_FILE:FLAG ...      e.g.  HEAD cpl/legacy.py cpl/helpers/probe.py:--probe
The body of the old top-level `if len(sys.argv) > 1 and sys.argv[1] == 'FLAG':` must equal, statement for statement (ast.dump), the body
of the new module, after removing from both sides the top-level imports and from the new module the docstring, and `os.environ.setdefault(...)` lines (the only things
step P2 adds in front of the code)."""
import ast, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def old_body(rev, path, flag):
    src = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{path}"], capture_output=True, text=True, check=True).stdout
    for n in ast.parse(src).body:
        if isinstance(n, ast.If) and ast.unparse(n.test).endswith(f"== '{flag}'"):
            return [x for x in n.body if not isinstance(x, (ast.Import, ast.ImportFrom))]      # top-level imports are compared by hand (they are re-stated per module)
    raise SystemExit(f"no block for {flag} in {rev}:{path}")


def new_body(path):
    out = []
    for i, n in enumerate(ast.parse((ROOT / path).read_text(encoding="utf-8")).body):
        if i == 0 and isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant):
            continue                                                    # docstring
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(n, ast.Expr) and ast.unparse(n).startswith('os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT"'.replace('"', "'")):
            continue
        out.append(n)
    return out


def main():
    rev, oldf, *pairs = sys.argv[1:]
    bad = 0
    for pr in pairs:
        newf, flag = pr.rsplit(":", 1)
        a, b = old_body(rev, oldf, flag), new_body(newf)
        da, db = [ast.dump(x) for x in a], [ast.dump(x) for x in b]
        ok = da == db
        bad += not ok
        print(("OK   " if ok else "FAIL ") + f"{flag}: {len(a)} statements in the old block, {len(b)} in {newf}")
        if not ok:
            for i, (x, y) in enumerate(zip(da, db)):
                if x != y:
                    print(f"   first difference at statement {i}: {ast.unparse(a[i])[:80]!r} vs {ast.unparse(b[i])[:80]!r}")
                    break
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
