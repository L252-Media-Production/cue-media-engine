#!/usr/bin/env python3
"""Gate: no bare shared state (docs/split-plan.md 4.5, items 1-4). Standard library only (ast + symtable); no server is started.

    python tests/test_no_bare_state.py          # exit 0 = the gates pass (and the self-test proves they can fail)

Outside cpl/state.py:
  1  no `global` statement names a moved scalar or a stable container
  2  no bare name that resolves to the module scope is a moved scalar (read, write, delete, augmented assignment, import)
  3  no `from cpl.state import <scalar>`; `cpl.state` is only ever bound to the name S
  4  a stable container is never assigned, deleted, imported under another binding or redefined (it may be imported by name);
     `S.<scalar> = ...` / `S.<scalar> += ...` appears only in the functions of the writer table WRITERS (a new writer must be added on purpose)
  1b (the closing check of P4) a `global` statement may name only the module-private names of MODULE_PRIVATE: the 7 names that stay in
     legacy until their module is split out (to localise in P5/P6/P8), and clock._src. Any other rebound module global is a new shared name
     that belongs in cpl/state.py.
  6  no `from cpl.<module> import <function a test patches>` (PATCHED): such a copy would bypass the test's spy; call module.func(...)
Gate 8 (hooks registered after the import) is tests/test_state_hooks.py; gates 5, 7, 9, 10 of the plan are in tests/test_gates.py.
Local variables that happen to be spelled like a state name (focus, decks, library, pending ...) are fine: resolution is done with symtable.

SCALARS grows group by group during P4 (old module-level name -> its name in cpl.state).
"""
import ast, symtable, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

# old module-level name -> name on S.  Moved so far:
SCALARS = {"rev": "rev", "cue_cleared": "cue_cleared", "known": "known", "last_scan": "last_scan", "_boot_done": "boot_done", "LAST_LOAD_ERR": "LAST_LOAD_ERR", "MONITOR": "MONITOR",
           "pending": "pending", "_pending_n": "pending_n", "live_deck": "live_deck", "notify": "notify"}
CONTAINERS = ["playlists", "FOLDER_COLORS", "FOLDER_ICONS", "FOLDER_FLAGS", "LIBDIRS", "library", "focus", "decks", "ISSUES", "DEV_MISSING", "DURS"]
# the module-private rebound globals (docs/split-plan.md 4.1 rows 12-18): file -> names. Remove an entry when its module is split out and the name becomes a plain module attribute.
MODULE_PRIVATE = {
    "cpl/legacy.py": {"osc_out", "_list_keys", "_ui_cache", "_dl_task"},    # to localise in P5 (_gen -> cache), P6 (_dur_* -> durations), P8 (osc_out, _list_keys -> stateout; _ui_cache -> ui_assets; _dl_task -> download)
    "cpl/clock.py": {"_src"},
    "cpl/durations.py": {"_dur_busy", "_dur_booted"},                                                              # written by the worker thread and durations(); read by health() through durations.status()
    "cpl/cache.py": {"_gen"},                                                                                      # private to the cache; cache.invalidate_all() rebinds it
}
PATCHED = {"request_warm", "request_loudness", "_warm_loop", "_play_on_top", "push", "loud_pending"}      # functions that tests replace (plan 4.4): always called as module.func()
# S.<scalar> may be written (outside cpl/state.py) only in these functions (the writer table of 4.1, as data).  rev is written by state.bump itself.
WRITERS = {"rev": set(), "cue_cleared": {"command"}, "known": {"lib_rename", "load"}, "last_scan": {"load", "rescan_library"},
           "_boot_done": {"main"}, "LAST_LOAD_ERR": {"_start_when_ready"}, "MONITOR": {"monitor_set"},
           "pending": {"_live_restore", "_play_on_top", "_start_when_ready", "fade_out", "play", "stop_all", "try_resume"},
           "_pending_n": {"_live_restore", "_play_on_top", "play", "try_resume"},
           "live_deck": {"_start", "stop_all", "tick"},
           "notify": {"<module>"}}                      # set once at import by the module that owns push()


def _is_state_file(name):
    return name.replace("\\", "/").endswith("cpl/state.py")


def _walk_tables(t):
    yield t
    for c in t.get_children():
        yield from _walk_tables(c)


def check(sources, scalars=None, containers=None, writers=None, private=None, patched=None):
    """sources: {filename: source text}. -> list of problems."""
    scalars = SCALARS if scalars is None else scalars
    containers = CONTAINERS if containers is None else containers
    writers = WRITERS if writers is None else writers
    private = MODULE_PRIVATE if private is None else private
    patched = PATCHED if patched is None else patched
    sset = set(scalars)
    new_names = set(scalars.values())
    problems = []
    for fn, src in sources.items():
        tree = ast.parse(src)
        in_state = _is_state_file(fn)
        # ---- gate 3 (applies to state.py too)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "cpl.state":
                    for a in node.names:
                        if a.name in new_names or a.name in sset:
                            problems.append(f"{fn}:{node.lineno}: gate 3: `from cpl.state import {a.name}` copies a rebindable scalar (use S.{a.name})")
                if node.module and node.module.startswith("cpl.") and node.module != "cpl.state":
                    for a in node.names:
                        if a.name in patched:
                            problems.append(f"{fn}:{node.lineno}: gate 6: `from {node.module} import {a.name}` (a copy bypasses a test's patch; use {node.module.split('.')[-1]}.{a.name}(...))")
                if node.module == "cpl":
                    for a in node.names:
                        if a.name == "state" and (a.asname or "state") != "S":
                            problems.append(f"{fn}:{node.lineno}: gate 3: cpl.state must be imported as S")
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name == "cpl.state" and a.asname != "S":
                        problems.append(f"{fn}:{node.lineno}: gate 3: `import cpl.state` must be `from cpl import state as S`")
        if in_state:
            continue
        # ---- gate 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                for n in node.names:
                    if n in sset or n in containers:
                        problems.append(f"{fn}:{node.lineno}: gate 1: `global {n}` (a shared name; use S.{scalars.get(n, n)})")
                    elif n not in private.get(fn.replace("\\", "/"), set()):
                        problems.append(f"{fn}:{node.lineno}: gate 1b: `global {n}` is not a listed module-private name (a new shared name belongs in cpl/state.py)")
        # ---- gate 2 + container rebinding, by symbol resolution
        for t in _walk_tables(symtable.symtable(src, fn, "exec")):
            is_module = t.get_type() == "module"
            for sym in t.get_symbols():
                nm = sym.get_name()
                if nm in sset:
                    if is_module and (sym.is_assigned() or sym.is_referenced() or sym.is_imported() or sym.is_declared_global()):
                        problems.append(f"{fn}: gate 2: module-level use of the moved scalar `{nm}` (use S.{scalars[nm]})")
                    elif not is_module and sym.is_global():
                        problems.append(f"{fn}:{t.get_lineno()}: gate 2: `{t.get_name()}` uses the module-scope name `{nm}` (use S.{scalars[nm]})")
                if nm in containers:
                    if is_module and (sym.is_assigned() and not sym.is_imported() or sym.is_namespace()):
                        problems.append(f"{fn}: gate 4: the container `{nm}` is assigned or defined outside cpl/state.py")
                    elif not is_module and sym.is_global() and sym.is_assigned():
                        problems.append(f"{fn}:{t.get_lineno()}: gate 4: `{t.get_name()}` rebinds the container `{nm}`")
        # ---- gate 4: where S.<scalar> is written
        stack = []

        class V(ast.NodeVisitor):
            def visit_FunctionDef(self, n):
                stack.append(n.name)
                self.generic_visit(n)
                stack.pop()
            visit_AsyncFunctionDef = visit_FunctionDef

            def check_target(self, tgt, lineno):
                for x in ast.walk(tgt):
                    if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) and x.value.id == "S" and isinstance(x.ctx, (ast.Store, ast.Del)):
                        old = next((o for o, nw in scalars.items() if nw == x.attr), None)
                        if old is not None and not ((set(stack) or {"<module>"}) & writers.get(old, set())):
                            problems.append(f"{fn}:{lineno}: gate 4: S.{x.attr} is written in `{'.'.join(stack) or '<module>'}`, which is not in the writer table")

            def visit_Assign(self, n):
                for tg in n.targets:
                    self.check_target(tg, n.lineno)
                self.generic_visit(n)

            def visit_AugAssign(self, n):
                self.check_target(n.target, n.lineno)
                self.generic_visit(n)

            def visit_AnnAssign(self, n):
                self.check_target(n.target, n.lineno)
                self.generic_visit(n)

            def visit_Delete(self, n):
                for tg in n.targets:
                    self.check_target(tg, n.lineno)

            def visit_For(self, n):
                self.check_target(n.target, n.lineno)
                self.generic_visit(n)

        V().visit(tree)
    return problems


def selftest():
    sc, co, wr = {"rev": "rev", "pending": "pending"}, ["playlists", "decks"], {"rev": set(), "pending": {"play"}}
    ok = "from cpl import state as S\nfrom cpl.state import playlists\ndef f():\n    pending = 1\n    decks = []\n    return S.rev, playlists, decks, pending\ndef play():\n    S.pending = 3\n"
    cases = {
        "global of a scalar": ("def f():\n    global rev\n    rev += 1\n", "gate 1"),
        "global of a container": ("def f():\n    global playlists\n    playlists = []\n", "gate 1"),
        "bare read of a scalar": ("def f():\n    return rev\n", "gate 2"),
        "bare module-level scalar": ("rev = 0\n", "gate 2"),
        "scalar imported by name": ("from cpl.state import rev\n", "gate 3"),
        "state imported under another name": ("from cpl import state as ST\n", "gate 3"),
        "import cpl.state": ("import cpl.state\n", "gate 3"),
        "container redefined": ("playlists = []\n", "gate 4"),
        "container rebound in a function": ("def f():\n    global playlists\n    playlists = []\n", "gate 4"),
        "a new rebound global": ("def f():\n    global fresh\n    fresh = 1\n", "gate 1b"),
        "a patched function imported by name": ("from cpl.warm import request_warm\n", "gate 6"),
        "writer not in the table": ("from cpl import state as S\ndef g():\n    S.pending = 1\n", "gate 4"),
        "augmented write not in the table": ("from cpl import state as S\ndef g():\n    S.rev += 1\n", "gate 4"),
    }
    fails = []
    p = check({"cpl/x.py": ok}, sc, co, wr, {}, {"request_warm"})
    if p:
        fails.append(f"self-test: the clean sample was flagged: {p}")
    for name, (src, gate) in cases.items():
        p = check({"cpl/x.py": src}, sc, co, wr, {}, {"request_warm"})
        if not any(gate in x for x in p):
            fails.append(f"self-test: '{name}' was not caught by {gate}: {p}")
    return fails


def main():
    from test_gates import app_files
    fails = selftest()
    files = app_files(ROOT)
    problems = check({str(f.relative_to(ROOT)): f.read_text(encoding="utf-8") for f in files})
    for x in fails + problems:
        print("FAIL", x)
    print(f"no-bare-state gates 1-6: {len(files)} files, {len(SCALARS)} scalar(s) + {len(CONTAINERS)} containers: " + ("FAIL" if fails or problems else "PASS (self-test with 13 planted violations passed)"))
    return 1 if fails or problems else 0


if __name__ == "__main__":
    sys.exit(main())
