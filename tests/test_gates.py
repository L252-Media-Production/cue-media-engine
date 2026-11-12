#!/usr/bin/env python3
"""Static gates for the split (docs/split-plan.md section 4.5). Standard library only; no server is started.

    python tests/test_gates.py          # exit 0 = every gate passes

Implemented now (they pass trivially on today's single file; the split steps add the others):
  gate 7  no function-local `import cpl...` (all cpl imports at module top, so the first Play never reads from disk)
  gate 10 the child-process helpers (cpl/helpers) import only stdlib, pygame, numpy, cpl.dsp, cpl.helpers.common, cpl.helpers.ring
  gate 5  time.monotonic/time/sleep only through cpl.clock; no `from cpl.clock import ...`
  gate 9  the module-to-module imports found by ast equal tests/gates/import_allowlist.json and contain no cycle;
          nothing imports cpl.legacy
  plus    the self-test of tests/tools/verify_move.py
Later steps add: 1-4 (no bare state names / globals, writer table), 6 (no
by-name import of a patched function), 8 (hooks registered after `import cpl.app`).
"""
import ast, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def app_files(root=ROOT):
    files = [root / "player.py"]
    cpl = root / "cpl"
    if cpl.is_dir():
        files += sorted(p for p in cpl.rglob("*.py") if "__pycache__" not in p.parts)
    return [f for f in files if f.is_file()]


def modname(f, root=ROOT):
    rel = f.relative_to(root / "cpl").with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _cpl_target(node, cur_pkg):
    """-> list of cpl module names (relative to cpl) that an import node refers to."""
    out = []
    if isinstance(node, ast.Import):
        for a in node.names:
            if a.name == "cpl" or a.name.startswith("cpl."):
                out.append(a.name[4:] if a.name != "cpl" else "")
    elif isinstance(node, ast.ImportFrom):
        mod = node.module or ""
        if node.level:                                           # relative import: resolve against the package of the file (cur_pkg is relative to cpl)
            base = (["cpl"] + list(cur_pkg))
            base = base[:len(base) - (node.level - 1)]
            mod = ".".join(base + ([mod] if mod else []))
        if mod == "cpl":
            out += [a.name for a in node.names]                  # from cpl import state as S -> cpl.state
        elif mod.startswith("cpl."):
            out.append(mod[4:])
    return out


def gate7_no_local_cpl_imports(files=None):
    bad = []
    for f in files or app_files():
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for n in ast.walk(fn):
                    if isinstance(n, (ast.Import, ast.ImportFrom)) and _cpl_target(n, []):
                        bad.append(f"{f.name}:{n.lineno} function-local import of cpl in {fn.name}()")
    return bad


def import_graph(files=None, root=ROOT):
    g = {}
    for f in files or app_files(root):
        if f.name == "player.py" and f.parent == root:
            continue                                             # the launcher is not a cpl module
        m = modname(f, root)
        pkg = m.split(".")[:-1] if f.name != "__init__.py" else m.split(".")
        deps = set()
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for t in _cpl_target(n, pkg):
                    if t and t != m:
                        deps.add(t)
        g[m] = deps
    return g


def find_cycle(g):
    state, stack = {}, []

    def visit(v):
        state[v] = 1
        stack.append(v)
        for w in sorted(g.get(v, ())):
            if state.get(w) == 1:
                return stack[stack.index(w):] + [w]
            if state.get(w) is None and w in g:
                c = visit(w)
                if c:
                    return c
        stack.pop()
        state[v] = 2
        return None

    for v in sorted(g):
        if state.get(v) is None:
            c = visit(v)
            if c:
                return c
    return None


def gate9_import_graph(files=None, root=ROOT, allow=None):
    bad = []
    g = import_graph(files, root)
    allow = (allow if allow is not None else json.loads((HERE / "gates" / "import_allowlist.json").read_text(encoding="utf-8")).get("modules", {}))
    for m, deps in sorted(g.items()):
        if m == "legacy":
            continue                                             # may import anything; nothing may import it (below)
        if m == "":                                              # cpl/__init__.py must stay empty of imports
            if deps:
                bad.append(f"cpl/__init__.py imports {sorted(deps)} (it must stay empty)")
            continue
        if m not in allow:
            bad.append(f"module cpl.{m} is not in tests/gates/import_allowlist.json")
            continue
        extra = deps - set(allow[m])
        if extra:
            bad.append(f"cpl.{m} imports {sorted(extra)}, not allowed by the allow-list")
    for m, deps in g.items():
        if "legacy" in deps and m != "legacy":
            bad.append(f"cpl.{m} imports cpl.legacy (nothing may)")
    cyc = find_cycle(g)
    if cyc:
        bad.append("import cycle: " + " -> ".join(cyc))
    return bad


CLOCK_FUNCS = {"monotonic", "time", "sleep"}


def gate5_clock_only(files=None, root=ROOT):
    """Plan 4.5 item 5: outside cpl/clock.py and the child-process helpers (separate processes, real time only), no code calls
    time.monotonic / time.time / time.sleep, or imports them by name from `time`; and nobody does `from cpl.clock import <function>`
    (a copy of the function would bypass the fake clock). time.time_ns is allowed (names of temp files)."""
    bad = []
    for f in files or app_files(root):
        rel = f.relative_to(root).as_posix()
        if rel in ("cpl/clock.py", "player.py") or rel.startswith("cpl/helpers/"):
            continue
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "time" and n.attr in CLOCK_FUNCS:
                bad.append(f"{rel}:{n.lineno} uses time.{n.attr} (use cpl.clock)")
            elif isinstance(n, ast.ImportFrom) and not n.level and n.module == "time" and any(a.name in CLOCK_FUNCS for a in n.names):
                bad.append(f"{rel}:{n.lineno} imports a clock function from time")
            elif isinstance(n, ast.ImportFrom) and not n.level and n.module == "cpl.clock":
                bad.append(f"{rel}:{n.lineno} 'from cpl.clock import ...' (call clock.monotonic() etc. through the module)")
            elif isinstance(n, ast.ImportFrom) and not n.level and n.module == "cpl" and any(a.name == "clock" and a.asname not in (None, "clock") for a in n.names):
                bad.append(f"{rel}:{n.lineno} cpl.clock imported under another name")
    return bad


HELPER_THIRD_PARTY = {"pygame", "numpy"}


def gate10_helpers_import_no_app(files=None, root=ROOT):
    """cpl/helpers/*.py (the four child-process entry points) import only the standard library, pygame, numpy, cpl.dsp,
    cpl.helpers.common and cpl.helpers.ring (the Live input's capture ring: stdlib + numpy only): never aiohttp, python-osc, scipy, yt_dlp at module level of anything but dl, cpl.config or cpl.legacy.
    (yt_dlp is imported by dl.py itself, inside its try block.)"""
    bad = []
    std = set(sys.stdlib_module_names)
    for f in files or sorted((root / "cpl" / "helpers").glob("*.py")):
        if f.name == "__init__.py":
            continue
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = []
            if isinstance(n, ast.Import):
                names = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and not n.level:
                names = [n.module or ""]
            for nm in names:
                top = nm.split(".")[0]
                if top == "cpl":
                    if nm not in ("cpl.dsp", "cpl.helpers.common", "cpl.helpers.ring"):
                        bad.append(f"{f.name}:{n.lineno} imports {nm}")
                elif top not in std and top not in HELPER_THIRD_PARTY and not (f.name == "dl.py" and top in ("yt_dlp", "youtube_dl")):
                    bad.append(f"{f.name}:{n.lineno} imports {nm}")
    return bad


def self_test_gates():
    """The gates must really fail on bad input (so that 'passes trivially' is not 'checks nothing')."""
    import tempfile
    bad = []
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "cpl").mkdir()
        (r / "player.py").write_text("x = 1\n")
        (r / "cpl" / "__init__.py").write_text("")
        (r / "cpl" / "a.py").write_text("from cpl import b\n\ndef f():\n    import cpl.b\n")
        (r / "cpl" / "b.py").write_text("from cpl import a\n")
        (r / "cpl" / "legacy.py").write_text("from cpl import a\n")
        (r / "cpl" / "c.py").write_text("from cpl import legacy\n")
        files = app_files(r)
        if not gate7_no_local_cpl_imports(files):
            bad.append("gate 7 did not flag a function-local cpl import")
        out = gate9_import_graph(files, r, allow={"a": ["b"], "b": ["a"], "c": ["legacy"]})
        if not any("cycle" in x for x in out):
            bad.append("gate 9 did not flag an import cycle")
        if not any("imports cpl.legacy" in x for x in out):
            bad.append("gate 9 did not flag an import of cpl.legacy")
        out = gate9_import_graph(files, r, allow={"a": [], "b": ["a"], "c": ["legacy"]})
        if not any("not allowed" in x for x in out):
            bad.append("gate 9 did not flag an import outside the allow-list")
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "cpl").mkdir()
        (r / "cpl" / "x.py").write_text("import time\nfrom time import sleep\nfrom cpl.clock import monotonic\nt = time.monotonic()\nu = time.time_ns()\n")
        out = gate5_clock_only(root=r)
        if len(out) != 3:
            bad.append(f"gate 5 should flag 3 things, got {out}")
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "cpl" / "helpers").mkdir(parents=True)
        (r / "cpl" / "helpers" / "x.py").write_text("import aiohttp\nfrom cpl.config import CFG\nimport os\n")
        out = gate10_helpers_import_no_app(root=r)
        if len(out) != 2:
            bad.append(f"gate 10 should flag aiohttp and cpl.config, got {out}")
    return bad


def main():
    sys.path.insert(0, str(HERE / "tools"))
    problems = []
    for name, fn in (("gate 7 (no function-local cpl import)", gate7_no_local_cpl_imports),
                     ("gate 9 (import graph = allow-list, acyclic, no cpl.legacy import)", gate9_import_graph),
                     ("gate 5 (time only through cpl.clock)", gate5_clock_only),
                     ("gate 10 (helpers import no app, no aiohttp / python-osc / config)", gate10_helpers_import_no_app),
                     ("gate self-test (the gates fail on bad input)", self_test_gates)):
        res = fn()
        print(("PASS " if not res else "FAIL ") + name)
        problems += res
    import test_verify_move
    rc = test_verify_move.main()
    print(("PASS " if rc == 0 else "FAIL ") + "verify_move self-test")
    for p in problems:
        print("  -", p)
    return 1 if problems or rc else 0


if __name__ == "__main__":
    sys.exit(main())
