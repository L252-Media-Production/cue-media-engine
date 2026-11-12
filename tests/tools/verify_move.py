#!/usr/bin/env python3
"""Move verifier (docs/split-plan.md section 3.4).

Proves that a step of the split only MOVED code. For every top-level function, class and assignment of the old
source the same name must exist in the new source with an identical AST (node for node, ignoring line numbers,
comments and imports), except for the rewrites the map allows:

  state_names   {"live_deck": "live_deck", "_pending_n": "pending_n"}   a bare name becomes S.<new>
  state_alias   "S"                                                     the module alias (default S)
  module_funcs  {"request_warm": "warm"}                                a bare reference becomes warm.request_warm
                (only where the function is NOT itself defined in that module; see "module_of")
  module_of     {"name": "module"}                                      which new module each moved name lives in; a
                                                                        reference is only rewritten across modules
  expr_rewrites [{"old": "str(Path(__file__).resolve())", "new": "str(LAUNCHER)"}]
                                                                        an exact expression (compared by ast.unparse)
  expr_rewrites_in {"fn": [{"old": "push()", "new": "S.notify()"}]}      the same, but only inside the named functions (and what they contain)
  local_names_in {"fmt_kick": ["pending"]}                              functions in which a state name is an ordinary LOCAL variable or
                                                                        function (the verifier is not scope aware): it is not rewritten there
  global statements are dropped for state_names (a `global` that becomes empty is removed)
  allowed_changed                   names whose body may differ (a REVIEWED change, listed in the report so nobody forgets it)
  allowed_added / allowed_removed   lists of top-level names that may appear only in the new / only in the old source
  allowed_other_added / allowed_other_removed   prefixes of unparse() of top-level statements that are neither a
                                                def/class/assignment nor an import (e.g. the `if __name__` block)

Anything else (an added or removed statement, a changed constant, an added `await`, a changed default) is reported
and the exit code is 1.  Imports are ignored on purpose: a move changes them.  Comments and layout are not in the
AST; for a verbatim move also read `git diff -M` (the plan does).

Usage:
  verify_move.py OLD_REV NEW_REV --old-files player.py --new-files cpl/legacy.py [--map map.json]
  verify_move.py --self-test            (runs tests/tools/test_verify_move.py)
Files are read with `git show REV:path` (REV may be WORKTREE for the working tree).
"""
import argparse, ast, copy, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _read(rev, path):
    if rev == "WORKTREE":
        return (ROOT / path).read_text(encoding="utf-8")
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{path}"], capture_output=True, text=True, check=True).stdout


def _key(node):
    """-> a stable key for a top-level node, or None for nodes that are ignored (imports, bare docstrings)."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return ("def", node.name)
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = sorted(n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name))
        return ("var", ",".join(names))
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return None
    if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) and isinstance(node.value.value, str):
        return None
    return ("other", ast.unparse(node))


class _Norm(ast.NodeTransformer):
    """Rewrites the OLD tree into what the NEW tree should contain."""
    def __init__(self, cfg, this_module):
        self.state = cfg.get("state_names", {})
        self.alias = cfg.get("state_alias", "S")
        self.mod_funcs = cfg.get("module_funcs", {})
        self.module_of = cfg.get("module_of", {})
        self.this = this_module
        self.rename = cfg.get("rename", {})
        self.local_in = cfg.get("local_names_in", {})
        self.exprs_in = {fn: {r["old"]: ast.parse(r["new"], mode="eval").body for r in lst} for fn, lst in cfg.get("expr_rewrites_in", {}).items()}
        self.stack = []
        self.exprs = {r["old"]: ast.parse(r["new"], mode="eval").body for r in cfg.get("expr_rewrites", [])}

    def generic_visit(self, node):
        if isinstance(node, ast.expr) and (self.exprs or (self.exprs_in and self.stack)):
            try:
                u = ast.unparse(node)
            except Exception:
                u = None
            if u in self.exprs:
                return copy.deepcopy(self.exprs[u])
            for fn in self.stack:
                if u in self.exprs_in.get(fn, {}):
                    return copy.deepcopy(self.exprs_in[fn][u])
        return super().generic_visit(node)

    def _func(self, node):
        self.stack.append(node.name)
        node = self.generic_visit(node)
        self.stack.pop()
        return node
    visit_FunctionDef = visit_AsyncFunctionDef = _func

    def _is_local(self, name):
        return any(name in self.local_in.get(f, ()) for f in self.stack)

    def visit_Global(self, node):
        names = [n for n in node.names if n not in self.state]
        return ast.Global(names=names) if names else None

    def visit_Name(self, node):
        if node.id in self.rename:
            return ast.copy_location(ast.Name(id=self.rename[node.id], ctx=node.ctx), node)
        if node.id in self.state and not self._is_local(node.id):
            return ast.copy_location(ast.Attribute(value=ast.Name(id=self.alias, ctx=ast.Load()), attr=self.state[node.id], ctx=node.ctx), node)
        mod = self.mod_funcs.get(node.id)
        if mod and self.module_of.get(node.id) != self.this and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Attribute(value=ast.Name(id=mod, ctx=ast.Load()), attr=node.id, ctx=node.ctx), node)
        return node


def compare_sources(old_srcs, new_srcs, cfg=None):
    """old_srcs / new_srcs: {filename: source}. -> list of problem strings (empty = a pure move).
    The new module of each definition is taken from the file it is in (module name = file stem)."""
    cfg = cfg or {}
    new_defs, new_mod = {}, {}
    for fn, src in new_srcs.items():
        mod = Path(fn).stem
        for node in ast.parse(src).body:
            k = _key(node)
            if k is None:
                continue
            new_defs.setdefault(k, []).append((mod, node))
    problems = []
    seen = set()
    allowed_removed = set(cfg.get("allowed_removed", []))
    allowed_added = set(cfg.get("allowed_added", []))
    allowed_changed = set(cfg.get("allowed_changed", []))
    reviewed = []
    other_removed = tuple(cfg.get("allowed_other_removed", []))
    other_added = tuple(cfg.get("allowed_other_added", []))
    # the module of every moved name (needed to decide whether a reference crosses modules)
    module_of = dict(cfg.get("module_of", {}))
    for (kind, name), lst in new_defs.items():
        if kind == "def" and name not in module_of:
            module_of[name] = lst[0][0]
    cfg = dict(cfg, module_of=module_of)
    for fn, src in old_srcs.items():
        for node in ast.parse(src).body:
            k = _key(node)
            if k is None:
                continue
            label = f"{k[0]} {k[1][:70]}"
            ncfg = cfg
            sn = cfg.get("state_names", {})
            if k[0] == "var" and k[1] in sn:                 # the state variable itself moves to the state module: it may be renamed, its value must not change
                k = ("var", sn[k[1]])
                ncfg = dict(cfg, state_names={}, module_funcs={}, rename=sn)
            if k not in new_defs:
                if k[0] == "other" and k[1].startswith(other_removed) and other_removed:
                    continue
                if k[1] in allowed_removed:
                    continue
                problems.append(f"missing in new: {label}")
                continue
            seen.add(k)
            cands = new_defs[k]
            ok = False
            diffs = []
            for mod, nn in cands:
                want = _Norm(ncfg, mod).visit(copy.deepcopy(node))
                want = ast.fix_missing_locations(want) if want is not None else None
                if want is not None and ast.dump(want) == ast.dump(nn):
                    ok = True
                    break
                diffs.append(mod)
            if not ok and k[1] in allowed_changed:
                reviewed.append(k[1])
                ok = True
            if not ok:
                problems.append(f"CHANGED: {label} (not identical after the allowed rewrites; compare with `git diff -M`)")
    for k, lst in new_defs.items():
        if k in seen:
            continue
        if k[0] == "other" and other_added and k[1].startswith(other_added):
            continue
        if k[1] in allowed_added:
            continue
        problems.append(f"added in new: {k[0]} {k[1][:70]}")
    compare_sources.reviewed = reviewed
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old_rev", nargs="?")
    ap.add_argument("new_rev", nargs="?")
    ap.add_argument("--old-files", nargs="+")
    ap.add_argument("--new-files", nargs="+")
    ap.add_argument("--map", help="JSON file (see above)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import test_verify_move
        return test_verify_move.main()
    if not (a.old_rev and a.new_rev and a.old_files and a.new_files):
        ap.error("OLD_REV NEW_REV --old-files ... --new-files ... are required")
    cfg = json.loads(Path(a.map).read_text(encoding="utf-8")) if a.map else {}
    old = {f: _read(a.old_rev, f) for f in a.old_files}
    new = {f: _read(a.new_rev, f) for f in a.new_files}
    problems = compare_sources(old, new, cfg)
    n_old = sum(1 for s in old.values() for nd in ast.parse(s).body if _key(nd))
    if problems:
        print(f"verify_move: {len(problems)} difference(s) ({n_old} top-level items compared)")
        for p in problems:
            print("  -", p)
        return 1
    rv = getattr(compare_sources, "reviewed", [])
    if rv:
        print("verify_move: REVIEWED CHANGES (allowed by the map, check them by hand): " + ", ".join(rv))
    print(f"verify_move: OK, {n_old} top-level items identical after the allowed rewrites ({a.old_rev}:{','.join(a.old_files)} -> {a.new_rev}:{','.join(a.new_files)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
