#!/usr/bin/env python3
"""Mechanical move of named top-level definitions from cpl/legacy.py into a new module (docs/split-plan.md 3.6 / 3.7).

    move_defs.py --check spec.json                       # dependency check of ALL modules of the spec in order (writes nothing)
    move_defs.py --module cache --spec spec.json [--apply]   # move one module of the spec (dry run unless --apply)

spec.json: {"modules": [{"name": "cache", "doc": "...", "names": ["_cache", "cached", "@S.on_change.append(request_warm)"], "no_import": ["_gen"],
            "by_module": ["request_warm"], "alias": "plm"}]}
  names       top-level definitions (def / class / variable) to move, verbatim, in their original order and with the comment lines directly above
              them. "@text" selects a module-level statement whose unparse() starts with text (e.g. a registration).
  no_import   names that legacy must NOT import by name afterwards (private, rebound globals: they are handled by hand)
  by_module   names (patched by tests, or hook-registered) that legacy must reach as `<alias>.<name>` instead of importing by name (gate 6)
  alias       how legacy refers to the module for `by_module` and manual calls (default: the module name)

What it does for a move: (1) every name the moved code uses that is defined in legacy and NOT moved is an UNRESOLVED dependency: the tool
stops (a module extracted so far may never import cpl.legacy); (2) names the moved code takes from legacy's import statements are imported in the
new module with the same spelling; (3) the definitions are cut out of legacy and written to cpl/<module>.py unchanged; (4) legacy imports the
moved names it still uses by name (`from cpl.<module> import ...`), and rewrites uses of by_module names (symtable decides which occurrences
resolve to the module scope; the edit positions come from the ast offsets) to `<alias>.<name>`.
The result is checked by tests/tools/verify_move.py (module_funcs / module_of) and the gates; nothing here is trusted.
"""
import argparse, ast, builtins, json, re, symtable, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEGACY = ROOT / "cpl" / "legacy.py"
BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}


def node_names(n):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [n.name]
    if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        tg = n.targets if isinstance(n, ast.Assign) else [n.target]
        out = []

        def rec(t):
            if isinstance(t, ast.Name):
                out.append(t.id)
            elif isinstance(t, (ast.Tuple, ast.List)):
                for e in t.elts:
                    rec(e)
            elif isinstance(t, ast.Starred):
                rec(t.value)
        for t in tg:
            rec(t)                      # `S.x = ...` / `d[k] = ...` define nothing at module level
        return out
    return []


def span(src_lines, n):
    first = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])])
    i = first - 1
    while i > 0 and src_lines[i - 1].lstrip().startswith("#"):          # comment lines directly above belong to the definition
        i -= 1
    return i + 1, n.end_lineno


def globals_used(src, tree):
    """-> {top-level node index: set of names that resolve to the module scope (read or written)}"""
    top = symtable.symtable(src, "<legacy>", "exec")
    tables = {}
    for t in top.get_children():
        tables.setdefault((t.get_name(), t.get_lineno()), t)

    def rec(t, acc):
        for s in t.get_symbols():
            if s.is_global() and (s.is_referenced() or s.is_assigned()) or (s.is_declared_global()):
                acc.add(s.get_name())
        for c in t.get_children():
            rec(c, acc)
    out = {}
    for i, n in enumerate(tree.body):
        acc = set()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            t = tables.get((n.name, n.lineno))
            if t is None:                                               # decorated: symtable reports the def line
                t = next((v for (nm, ln), v in tables.items() if nm == n.name and n.lineno <= ln <= n.end_lineno), None)
            if t is not None:
                rec(t, acc)
        elif not isinstance(n, (ast.Import, ast.ImportFrom)):
            for x in ast.walk(n):
                if isinstance(x, ast.Name):
                    acc.add(x.id)
        out[i] = acc
    return out


def import_index(tree):
    """alias name -> (stmt node, spelling) for every top-level import"""
    idx = {}
    for n in tree.body:
        if isinstance(n, ast.Import):
            for a in n.names:
                idx[(a.asname or a.name).split(".")[0]] = ("import", a.name, a.asname)
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                idx[a.asname or a.name] = ("from", n.module, n.level, a.name, a.asname)
    return idx


def select(tree, names):
    chosen, missing = [], []
    for nm in names:
        hit = []
        for i, n in enumerate(tree.body):
            if nm.startswith("@"):
                if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)) and not node_names(n) or isinstance(n, ast.Expr) or isinstance(n, ast.If):
                    if ast.unparse(n).startswith(nm[1:]):
                        hit.append(i)
                elif isinstance(n, ast.Assign) and ast.unparse(n).startswith(nm[1:]):
                    hit.append(i)
            elif nm in node_names(n):
                hit.append(i)
        if not hit:
            missing.append(nm)
        chosen += hit
    return sorted(set(chosen)), missing


def import_line(name, spec):
    if spec[0] == "import":
        return f"import {spec[1]}" + (f" as {spec[2]}" if spec[2] else "")
    _k, mod, level, orig, asn = spec
    return f"from {'.' * level}{mod or ''} import {orig}" + (f" as {asn}" if asn else "")


def analyse_module(src, tree, used, imports, mod, taken_by_earlier):
    """-> (indices to move, unresolved {name: [moved names that use it]}, imports needed {alias: spec})"""
    idx, missing = select(tree, mod["names"])
    if missing:
        raise SystemExit(f"move_defs: {mod['name']}: names not found in legacy: {missing}")
    moved_names = {nm for i in idx for nm in node_names(tree.body[i])}
    defined = {}
    for i, n in enumerate(tree.body):
        for nm in node_names(n):
            defined.setdefault(nm, []).append(i)
    unresolved, needs = {}, {}
    for i in idx:
        who = (node_names(tree.body[i]) or [ast.unparse(tree.body[i])[:40]])[0]
        for r in used[i]:
            if r in BUILTINS or r in moved_names:
                continue
            if r in defined and not (set(defined[r]) <= set(idx)):
                if r in imports and all(isinstance(tree.body[j], (ast.Import, ast.ImportFrom)) for j in defined[r]):
                    needs[r] = imports[r]
                else:
                    unresolved.setdefault(r, []).append(who)
            elif r in imports:
                needs[r] = imports[r]
            elif r not in defined:
                unresolved.setdefault(r, []).append(who)
    return idx, moved_names, unresolved, needs


def build(mod, src, tree, idx, needs):
    lines = src.splitlines(keepends=True)
    parts = []
    last_end = None
    for i in idx:
        a, b = span(lines, tree.body[i])
        gap = ""
        if last_end is not None:
            gap = "".join(lines[last_end:a - 1]) if a - 1 - last_end <= 3 and "".join(lines[last_end:a - 1]).strip() == "" else "\n\n"
        parts.append((gap, "".join(lines[a - 1:b])))
        last_end = b
    body = "".join(g + t for g, t in parts)
    std, third, cpl = [], [], []
    froms = {}
    for alias, spec in sorted(needs.items()):
        m = spec[1] if spec[0] == "import" else (spec[1] or "")
        bucket = cpl if m.startswith("cpl") else third if m.split(".")[0] in ("pygame", "aiohttp", "pythonosc", "numpy", "scipy") else std
        if spec[0] == "from":
            froms.setdefault((id(bucket), spec[1], spec[2]), (bucket, [])) [1].append(spec[3] + (f" as {spec[4]}" if spec[4] else ""))
        else:
            bucket.append(import_line(alias, spec))
    for (_b, mod_, level), (bucket, names_) in froms.items():
        bucket.append(f"from {'.' * level}{mod_ or ''} import {', '.join(sorted(names_))}")
    # merge `import a` lines into one `import a, b` for readability
    def merge(ls):
        plain = sorted(l[7:] for l in ls if l.startswith("import ") and " as " not in l)
        rest = sorted(l for l in ls if not (l.startswith("import ") and " as " not in l))
        return (["import " + ", ".join(plain)] if plain else []) + rest
    blocks = ["\n".join(b) for b in (merge(std), merge(third), sorted(cpl)) if b]
    head = f'"""{mod["doc"]}\n\nMoved verbatim from cpl/legacy.py in split step {mod.get("step", "P5/P6")} (docs/split-plan.md 2.1); nothing here imports cpl.legacy.\n"""\n'
    return head + ("\n".join(b + "\n" for b in blocks)) + "\n\n" + body.rstrip("\n") + "\n"


def module_scope_edits(src, tree, rewrite):
    """positions of Name occurrences in legacy (outside any removed code) that resolve to the module scope and are in `rewrite` {name: text}"""
    top = symtable.symtable(src, "<legacy>", "exec")
    # reuse the scope pairing of state_rewrite (it also copes with inlined comprehensions)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import state_rewrite as R
    mapping = {tree: top}
    R._pair(tree, top, mapping)
    starts = R._byte_offsets(src)
    edits = []

    def walk(node, scope):
        for c in ast.iter_child_nodes(node):
            if isinstance(c, R.SCOPES):
                if mapping[c] is None:
                    walk(c, scope)
                else:
                    walk(c, c)
                continue
            if isinstance(c, ast.Name) and c.id in rewrite:
                tab = mapping[scope]
                if tab.get_type() == "module" or tab.lookup(c.id).is_global():
                    s = starts[c.lineno - 1] + c.col_offset
                    e = starts[c.end_lineno - 1] + c.end_col_offset
                    edits.append((s, e, rewrite[c.id]))
            walk(c, scope)
    walk(tree, tree)
    return edits


def apply_move(mod, src, tree, used, imports, idx, moved_names):
    lines = src.splitlines(keepends=True)
    spans = [span(lines, tree.body[i]) for i in idx]
    keep_nodes = [n for i, n in enumerate(tree.body) if i not in idx]
    # which moved names does the REMAINING legacy code still use?
    rest_used = set()
    for i, n in enumerate(tree.body):
        if i not in idx:
            rest_used |= used[i]
    alias = mod.get("alias") or mod["name"]
    by_mod = [n for n in mod.get("by_module", []) if n in moved_names]
    no_imp = set(mod.get("no_import", []))
    to_import = sorted(n for n in moved_names if n in rest_used and n not in by_mod and n not in no_imp)
    # rewrite uses of by_module / no_import names in the remaining code -> alias.name (the no_import ones must not be used by legacy at all)
    clash = [n for n in no_imp if n in rest_used]
    if clash:
        print(f"  NOTE: legacy still uses {clash} (private to the new module): edit by hand after the move")
    rewrite = {n: f"{alias}.{n}" for n in by_mod}
    edits = module_scope_edits(src, tree, rewrite) if rewrite else []
    # remove the moved spans (end first) and apply the rewrites on the remaining text
    b = src.encode("utf-8")
    starts = []
    pos = 0
    for l in lines:
        starts.append(pos)
        pos += len(l.encode("utf-8"))
    starts.append(pos)
    ops = [(starts[a - 1], starts[b_], "") for a, b_ in spans] + [(s, e, t) for s, e, t in edits]
    # an edit inside a removed span is dropped
    ops = [o for o in ops if o[2] == "" and o[1] > o[0] or not any(sp[0] <= o[0] < sp[1] for sp in [(starts[a - 1], starts[b_]) for a, b_ in spans])]
    for s, e, t in sorted(ops, key=lambda o: (o[0], o[1]), reverse=True):
        b = b[:s] + t.encode("utf-8") + b[e:]
    text = b.decode("utf-8")
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # imports in legacy: after the last `from cpl...` import line
    new_imp = ""
    if to_import:
        new_imp += f"from cpl.{mod['name']} import ({', '.join(to_import)})      # moved to cpl/{mod['name']}.py in split step {mod.get('step', 'P5/P6')}\n"
    if by_mod or mod.get("force_module_import"):
        new_imp += f"from cpl import {mod['name']}" + (f" as {alias}" if alias != mod["name"] else "") + f"      # reached as {alias}.<name> (patched by tests / registered in a hook list)\n"
    if new_imp:
        m = list(re.finditer(r"^from cpl[^\n]*\n", text, re.M))
        at = m[-1].end() if m else 0
        text = text[:at] + new_imp + text[at:]
    return text, to_import, by_mod


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--module")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text())
    src = LEGACY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    used = globals_used(src, tree)
    imports = import_index(tree)
    if a.check:
        # simulate the moves in order on names only: a module may use legacy-defined names only if an EARLIER module of the spec took them
        owner = {}
        bad = 0
        for mod in spec["modules"]:
            idx, moved, unresolved, needs = analyse_module(src, tree, used, imports, mod, None)
            problems = {}
            for r, who in unresolved.items():
                if r in owner and owner[r] != mod["name"]:
                    continue                                   # taken by an earlier module: importable
                problems[r] = who
            # names that are unresolved only because they live in a LATER module (or nowhere) are the real problems
            print(f"{mod['name']:14s} {len(idx):3d} statements, {len(moved):3d} names -> " + ("OK" if not problems else "UNRESOLVED: " + "; ".join(f"{r} (used by {', '.join(sorted(set(w))[:3])})" for r, w in sorted(problems.items()))))
            bad += bool(problems)
            for nm in moved:
                owner[nm] = mod["name"]
        return 1 if bad else 0
    mod = next(m for m in spec["modules"] if m["name"] == a.module)
    idx, moved, unresolved, needs = analyse_module(src, tree, used, imports, mod, None)
    earlier = {}
    if unresolved:
        print("UNRESOLVED dependencies (defined in legacy, not moved):")
        for r, who in sorted(unresolved.items()):
            print(f"  {r}: used by {', '.join(sorted(set(who)))}")
        return 1
    new_src = build(mod, src, tree, idx, needs)
    out_text, to_import, by_mod = apply_move(mod, src, tree, used, imports, idx, moved)
    ast.parse(new_src)
    ast.parse(out_text)
    print(f"{mod['name']}: {len(idx)} statements, {len(moved)} names moved; legacy imports {len(to_import)} by name, {len(by_mod)} via module")
    print("  imports in the new module:", ", ".join(sorted(needs)) or "-")
    print("  legacy imports by name:", ", ".join(to_import) or "-")
    print("  via module:", ", ".join(by_mod) or "-")
    if a.apply:
        (ROOT / "cpl" / (mod["name"] + ".py")).write_text(new_src, encoding="utf-8")
        LEGACY.write_text(out_text, encoding="utf-8")
        print("written cpl/%s.py and cpl/legacy.py" % mod["name"])
    else:
        print("(dry run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
