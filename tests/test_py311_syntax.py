#!/usr/bin/env python3
"""Every Python file of the app parses on Python 3.11, the minimum (Debian 12). Since 2.8.0 a line in cpl/legacy.py nested same-type quotes
inside an f-string expression; only Python 3.12+ accepts that, so the player did not start on Debian 12 until 2.9.1.

    python tests/test_py311_syntax.py          # exit 0 = all pass (a skip, with its reason, also exits 0)

Files checked: player.py, cpl/ (with cpl/helpers/) and any *.py under packaging/.

  * test_compiles_with_python_311: compiles every file with a real Python 3.11 interpreter and fails with file, line and message.
    The interpreter is: the one running this test if it is 3.11, else `python3.11` on PATH, else `uv python find 3.11` with downloads off
    (uses only an interpreter uv already has; no network). None found = SKIP with the reason, never a silent pass.
  * test_ast_feature_version_311: needs no extra interpreter and always runs. ast.parse(..., feature_version=(3, 11)) plus a walk for
    `type X = ...` statements and `def f[T]` / `class C[T]` generics.
    WHAT IT CANNOT CATCH: feature_version is best effort. It does NOT reject the 3.12-only f-string grammar (PEP 701): same-type quotes nested
    in an f-string expression, a backslash or a `#` comment inside an f-string expression, a multi-line expression in a single-quoted
    f-string. That is exactly the 2.8.0 bug, which is why the real-3.11 check above exists (and the .deb build compiles with Debian 12's Python).
"""
import ast, json, os, shutil, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMPILER = r"""
import json, sys
out = []
for p in sys.argv[1:]:
    try:
        with open(p, encoding="utf-8") as f:
            compile(f.read(), p, "exec", dont_inherit=True)
    except SyntaxError as e:
        out.append([p, e.lineno, e.msg])
print(json.dumps([list(sys.version_info[:2]), out]))
"""


def py_files():
    files = [ROOT / "player.py"] + sorted((ROOT / "cpl").rglob("*.py"))
    if (ROOT / "packaging").is_dir():
        files += sorted((ROOT / "packaging").rglob("*.py"))
    return [f for f in files if "__pycache__" not in f.parts]


def find_python311():
    """(argv prefix, how it was found) or (None, why not)."""
    if sys.version_info[:2] == (3, 11):
        return [sys.executable], "the running interpreter"
    exe = shutil.which("python3.11")
    if exe:
        return [exe], f"python3.11 on PATH ({exe})"
    uv = shutil.which("uv")
    if uv:
        try:
            r = subprocess.run([uv, "python", "find", "3.11", "--no-python-downloads"], capture_output=True, text=True, timeout=30,
                               env={**os.environ, "UV_OFFLINE": "1", "UV_PYTHON_DOWNLOADS": "never"})
            if r.returncode == 0 and r.stdout.strip():
                return [r.stdout.strip().splitlines()[-1]], "uv python find 3.11 (offline)"
            why = "uv is installed but has no Python 3.11 (install one with `uv python install 3.11`)"
        except (OSError, subprocess.TimeoutExpired) as e:
            why = f"uv python find failed: {e}"
    else:
        why = "neither python3.11 on PATH nor uv installed"
    return None, why


def compile_with(argv, paths):
    r = subprocess.run(argv + ["-I", "-c", COMPILER] + [str(p) for p in paths], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise AssertionError(f"the Python 3.11 compile run failed: {r.stderr.strip()}")
    version, errors = json.loads(r.stdout.strip().splitlines()[-1])
    return tuple(version), errors


def ast_problems(source, name, parse=ast.parse):
    """[(line, message)] for what Python 3.11 cannot parse, as far as ast can tell (see the module doc for what it misses)."""
    try:
        tree = parse(source, name, feature_version=(3, 11))
    except SyntaxError as e:
        return [(e.lineno, e.msg)]
    found = []
    for node in ast.walk(tree):
        if type(node).__name__ == "TypeAlias":
            found.append((node.lineno, "`type X = ...` statement needs Python 3.12"))
        elif getattr(node, "type_params", None):
            found.append((node.lineno, f"generic syntax ({type(node).__name__} with [T]) needs Python 3.12"))
    return found


class Py311Syntax(unittest.TestCase):
    def test_files_found(self):
        files = py_files()
        self.assertIn(ROOT / "cpl" / "legacy.py", files)
        self.assertTrue(any(f.parent.name == "helpers" for f in files), "cpl/helpers/ not covered")

    def test_compiles_with_python_311(self):
        argv, how = find_python311()
        if argv is None:
            self.skipTest(f"no Python 3.11 interpreter: {how}. The ast check below still ran; it cannot see the f-string nesting bug")
        version, errors = compile_with(argv, py_files())
        self.assertEqual(version, (3, 11), f"{how} is Python {version}, not 3.11")
        print(f"\n  Python 3.11 found via {how}: {len(py_files())} files compiled", file=sys.stderr)
        self.assertEqual(errors, [], "Python 3.11 cannot parse:\n" + "\n".join(f"  {os.path.relpath(p, ROOT)}:{line}: {msg}" for p, line, msg in errors))

    def test_compile_check_catches_nested_quotes(self):
        argv, how = find_python311()
        if argv is None:
            self.skipTest(f"no Python 3.11 interpreter: {how}")
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.py"
            bad.write_text("x = 'a'\ns = f'{x.replace('a', 'b')}'\n", encoding="utf-8")
            _, errors = compile_with(argv, [bad])
        self.assertEqual(len(errors), 1, "a nested same-type quote in an f-string was not rejected by Python 3.11")
        self.assertEqual(errors[0][1], 2)

    def test_ast_feature_version_311(self):
        bad = []
        for f in py_files():
            for line, msg in ast_problems(f.read_text(encoding="utf-8"), str(f)):
                bad.append(f"  {f.relative_to(ROOT)}:{line}: {msg}")
        self.assertEqual(bad, [], "not valid Python 3.11:\n" + "\n".join(bad))

    def test_ast_check_catches_type_and_generics(self):
        for src in ("type X = int\n", "def f[T](x: T) -> T:\n    return x\n", "class C[T]:\n    pass\n"):
            self.assertTrue(ast_problems(src, "<snippet>"), f"ast check missed: {src!r}")
        self.assertEqual(ast_problems("def f(x):\n    return f'{x!r:>4}'\n", "<snippet>"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
