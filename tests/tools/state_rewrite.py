#!/usr/bin/env python3
"""Mechanical rewrite of module-level state names to `S.<name>` (docs/split-plan.md 4.5).

    state_rewrite.py [--dry-run] [--diff] --names old[:new] [old[:new] ...] [--file cpl/legacy.py] [--state cpl/state.py]

For every name in --names (old name, optionally `:new` name on S; leading underscores are normally dropped there):
  * symtable decides, per scope, which occurrences resolve to the MODULE scope (explicit `global`, implicit global, or the module
    body itself). Local variables, parameters and nested-function names that happen to be spelled the same are never touched.
  * each such occurrence (load, store, delete, augmented assignment) is replaced in place by `S.<new>`, located by the ast
    line / column offsets (bytes); there is no regex over the source.
  * the name is removed from every `global` statement; a `global` that becomes empty is deleted (its whole line).
  * the module-level definition (`name = value  # comment`, one statement on its own line(s)) is cut out of the file and
    appended, unchanged apart from the name, to --state. Any other module-level use is an error (the tool refuses).
  * the line `from cpl import state as S` must already be in the file.
Dry-run prints a summary (and with --diff a unified diff) and writes nothing. The summary lists, per name, the reads and writes per
function: the writes are the writer table for tests/test_no_bare_state.py.
After applying, prove the result with tests/tools/verify_move.py (state_names map) and run the gates.
"""
import argparse, ast, difflib, symtable, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _scope_children(node):
    """nested scope nodes directly below `node` (not below a nested scope), in source order."""
    out = []

    def rec(n):
        for c in ast.iter_child_nodes(n):
            if isinstance(c, SCOPES):
                out.append(c)
            else:
                rec(c)
    rec(node)
    return sorted(out, key=lambda n: (n.lineno, n.col_offset))


def _sym_children(tab):
    return sorted(tab.get_children(), key=lambda t: t.get_lineno())


def _pair(node, tab, mapping, path=""):
    """map ast scope node -> symtable table, checking that both trees agree (a mismatch aborts: never guess).
    Python 3.12 inlines list/dict/set comprehensions (PEP 709): symtable then has no table for them and they count as part of
    the enclosing scope (mapping value None); analyse() refuses a comprehension whose target is a state name."""
    kids_a, kids_s = _scope_children(node), _sym_children(tab)
    i = 0
    queue = list(kids_a)
    while queue:
        a = queue.pop(0)
        s = kids_s[i] if i < len(kids_s) else None
        nm = getattr(a, "name", None)
        want = nm or {ast.Lambda: "lambda", ast.ListComp: "listcomp", ast.SetComp: "setcomp", ast.DictComp: "dictcomp", ast.GeneratorExp: "genexpr"}[type(a)]
        if s is not None and s.get_lineno() == a.lineno and want == s.get_name():
            mapping[a] = s
            _pair(a, s, mapping, f"{path}/{nm or type(a).__name__}:{a.lineno}")
            i += 1
        elif isinstance(a, (ast.ListComp, ast.SetComp, ast.DictComp)):
            mapping[a] = None
            queue = sorted(queue + _scope_children(a), key=lambda n: (n.lineno, n.col_offset))     # its nested scopes belong to the enclosing symtable table
        else:
            raise SystemExit(f"state_rewrite: scope mismatch: ast {type(a).__name__} {nm or ''} at line {a.lineno} vs symtable {s and (s.get_name(), s.get_lineno())}")
    if i != len(kids_s):
        raise SystemExit(f"state_rewrite: {len(kids_s) - i} symtable scope(s) without an ast scope under {path or 'module'}")


def _byte_offsets(src):
    starts, pos = [0], 0
    for line in src.splitlines(keepends=True):
        pos += len(line.encode("utf-8"))
        starts.append(pos)
    return starts


def analyse(src, names):
    """-> (edits, global_stmts, defs, report). edits: [(start_byte, end_byte, text)]."""
    tree = ast.parse(src)
    top = symtable.symtable(src, "<src>", "exec")
    mapping = {tree: top}
    _pair(tree, top, mapping)
    new = {o: n for o, n in names.items()}
    starts = _byte_offsets(src)
    b = src.encode("utf-8")
    edits, globals_, defs = [], [], []
    report = defaultdict(lambda: {"read": defaultdict(int), "write": defaultdict(int), "module": 0})

    def walk(node, scope_node, fname):
        for c in ast.iter_child_nodes(node):
            if isinstance(c, SCOPES):
                if mapping[c] is None:                      # inlined comprehension: part of this scope, but its targets must not be state names
                    for g in c.generators:
                        for x in ast.walk(g.target):
                            if isinstance(x, ast.Name) and x.id in new:
                                raise SystemExit(f"state_rewrite: comprehension variable {x.id} at line {x.lineno} shadows a state name")
                    walk(c, scope_node, fname)
                    continue
                walk(c, c, getattr(c, "name", None) or fname or "<lambda>")
                continue
            if isinstance(c, ast.Global):
                if any(n in new for n in c.names):
                    globals_.append(c)
            if isinstance(c, ast.Name) and c.id in new:
                tab = mapping[scope_node]
                resolves_to_module = tab.get_type() == "module" or (lambda s: s.is_global())(tab.lookup(c.id))
                if resolves_to_module:
                    if tab.get_type() == "module":
                        defs.append(c)
                    else:
                        s = starts[c.lineno - 1] + c.col_offset
                        e = starts[c.end_lineno - 1] + c.end_col_offset
                        edits.append((s, e, f"S.{new[c.id]}"))
                        kind = "read" if isinstance(c.ctx, ast.Load) else "write"
                        report[c.id][kind][fname] += 1
            walk(c, scope_node, fname)
    walk(tree, tree, None)
    return tree, edits, globals_, defs, report, starts, b


def rewrite(src, state_src, names):
    """-> (new_src, new_state_src, report, notes)"""
    tree, edits, globals_, defs, report, starts, b = analyse(src, names)
    notes = []
    # ---- module-level definitions: `name = value` as a whole statement
    cut_lines = set()
    moved = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            tg = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            hit = [t.id for t in tg if isinstance(t, ast.Name) and t.id in names]
            if hit:
                if len(tg) != 1 or len(hit) != 1:
                    raise SystemExit(f"state_rewrite: refusing a chained definition at line {stmt.lineno}")
                lines = src.splitlines(keepends=True)[stmt.lineno - 1:stmt.end_lineno]
                text = "".join(lines)
                old = hit[0]
                import re
                text = re.sub(r"^%s\b" % re.escape(old), names[old], text, count=1) if old != names[old] else text
                moved.append((old, names[old], text.rstrip("\n")))
                cut_lines.update(range(stmt.lineno, stmt.end_lineno + 1))
                report[old]["module"] += 1
    module_uses = [d for d in defs if d.lineno not in cut_lines]
    if module_uses:
        raise SystemExit("state_rewrite: module-level use other than the definition: " + ", ".join(f"{d.id}@{d.lineno}" for d in module_uses))
    missing = [o for o in names if not any(m[0] == o for m in moved)]
    if missing:
        raise SystemExit(f"state_rewrite: no module-level definition found for {missing}")
    # ---- global statements
    glines = set()
    for g in globals_:
        keep = [n for n in g.names if n not in names]
        line = src.splitlines(keepends=True)[g.lineno - 1]
        if g.lineno != g.end_lineno or line.strip().startswith("global") is False or ";" in line:
            raise SystemExit(f"state_rewrite: unusual global statement at line {g.lineno}; do it by hand")
        indent = line[:len(line) - len(line.lstrip())]
        if keep:
            s = starts[g.lineno - 1] + g.col_offset
            e = starts[g.end_lineno - 1] + g.end_col_offset
            edits.append((s, e, "global " + ", ".join(keep)))
        else:
            if "#" in line:
                raise SystemExit(f"state_rewrite: a comment on the global statement at line {g.lineno}; do it by hand")
            glines.add(g.lineno)
    # ---- apply: name edits (from the end), then whole-line deletions
    out = b
    for s, e, t in sorted(edits, reverse=True):
        out = out[:s] + t.encode("utf-8") + out[e:]
    text = out.decode("utf-8")
    # line numbers shift only through same-line edits, so deletions are applied on the ORIGINAL numbering via a mapped pass
    lines_old = src.splitlines(keepends=True)
    lines_new = text.splitlines(keepends=True)
    assert len(lines_old) == len(lines_new)
    keep_lines = [l for i, l in enumerate(lines_new, 1) if i not in glines and i not in cut_lines]
    new_src = "".join(keep_lines)
    add = "".join(t + "\n" for _, _, t in moved)
    new_state = state_src.rstrip("\n") + "\n" + add if not state_src.endswith("\n\n") else state_src + add
    return new_src, new_state, report, {"moved": moved, "globals_removed": len(glines), "globals_edited": len(globals_) - len(glines)}


def summary(report, notes, names, file):
    out = []
    out.append(f"state_rewrite summary for {file}")
    tot_r = tot_w = 0
    for old, new in names.items():
        r = report[old]
        nr, nw = sum(r["read"].values()), sum(r["write"].values())
        tot_r += nr
        tot_w += nw
        out.append(f"  {old} -> S.{new}: {nr} read site(s) in {len(r['read'])} function(s), {nw} write site(s) in {len(r['write'])} function(s), {r['module']} module-level definition moved")
        out.append(f"      readers: {', '.join(f'{k}({v})' for k, v in sorted(r['read'].items())) or '-'}")
        out.append(f"      writers: {', '.join(f'{k}({v})' for k, v in sorted(r['write'].items())) or '-'}")
    out.append(f"  total: {tot_r} read sites, {tot_w} write sites; `global` statements deleted: {notes['globals_removed']}, shortened: {notes['globals_edited']}; definitions moved to the state module: {len(notes['moved'])}")
    for old, new, text in notes["moved"]:
        out.append(f"      moved: {text}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--names", nargs="+", required=True)
    ap.add_argument("--file", default="cpl/legacy.py")
    ap.add_argument("--state", default="cpl/state.py")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--diff", action="store_true")
    a = ap.parse_args()
    names = {}
    for n in a.names:
        o, _, nw = n.partition(":")
        names[o] = nw or o
    f, st = ROOT / a.file, ROOT / a.state
    src, ssrc = f.read_text(encoding="utf-8"), st.read_text(encoding="utf-8")
    if "from cpl import state as S" not in src:
        raise SystemExit("state_rewrite: `from cpl import state as S` is missing in " + a.file)
    new_src, new_state, report, notes = rewrite(src, ssrc, names)
    compile(new_src, a.file, "exec")
    compile(new_state, a.state, "exec")
    print(summary(report, notes, names, a.file))
    if a.diff:
        for fn, o, n in ((a.file, src, new_src), (a.state, ssrc, new_state)):
            sys.stdout.writelines(difflib.unified_diff(o.splitlines(keepends=True), n.splitlines(keepends=True), "a/" + fn, "b/" + fn, n=0))
    if a.dry_run:
        print("(dry run: nothing written)")
        return 0
    f.write_text(new_src, encoding="utf-8")
    st.write_text(new_state, encoding="utf-8")
    print("written:", a.file, a.state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
