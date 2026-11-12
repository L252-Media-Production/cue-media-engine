#!/usr/bin/env python3
"""Crawl player.py and cpl/**/*.py (command grammar, HTTP routes, OSC, variables, and the embedded web UI) and write tests/controls.csv.

    python tests/gen_controls.py [--player PATH] [--out PATH]

What it reads:
  * command()            every keyword of the grammar (compared with controls_meta.COMMANDS: unknown keywords are UNCLASSIFIED)
  * app.add_routes()     every HTTP endpoint (compared with controls_meta.HTTP)
  * VAR_INFO/snapshot()  every Companion variable
  * the UI string        every <button>/<input>/<select>/<textarea>, their handler functions and the API calls those make, and the delegated listeners
  * tests/api/*.py       the @pytest.mark.covers(...) ids, for the status column
"""
import argparse, ast, csv, re, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import controls_meta as M                       # noqa: E402

COLS = ["id", "area", "kind", "where", "control", "expected_result", "how_to_verify", "preconditions", "api_calls", "tests", "status"]


# ------------------------------------------------------------------ coverage markers
def covered_ids():
    cov = defaultdict(set)
    for f in sorted((HERE / "api").glob("test_*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in node.decorator_list:
                    if isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "covers":
                        for a in d.args:
                            if isinstance(a, ast.Constant):
                                cov[a.value].add(f"{f.stem}::{node.name}")
    return cov


def status_for(cid, cov, default):
    hit = cov.get(cid)
    via = ""
    if not hit:
        parts = cid.split(".")
        for n in range(len(parts) - 1, 0, -1):          # a test that covers cmd.duck also covers cmd.duck.ratio
            p = ".".join(parts[:n])
            if cov.get(p):
                hit, via = cov[p], f" (via {p})"
                break
    if hit:
        return "api-tested" + via, "; ".join(sorted(hit))[:300]
    return default, ""


# ------------------------------------------------------------------ source readers
def _parts(text, markers):
    """Split text at the markers (each exactly once, in order) -> the pieces in between."""
    out = []
    for mk in markers:
        assert text.count(mk) == 1, f"marker {mk!r} must occur exactly once"
        a, text = text.split(mk)
        out.append(a)
    return out + [text]


_SRC_STARTS = [(1, "player.py")]       # (first line in the joined source, file): filled by read_sources


def read_sources(path):
    """player.py plus cpl/**/*.py (sorted), joined into ONE text for the crawl below, with a line map for sloc().
    On today's single-file layout this is exactly player.py, so the output is unchanged."""
    path = Path(path)
    files = [path] + sorted((path.parent / "cpl").rglob("*.py")) if (path.parent / "cpl").is_dir() else [path]
    parts, starts, line = [], [], 1
    for f in files:
        text = f.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            text += "\n"
        rel = f.name if f == path else f.relative_to(path.parent).as_posix()
        starts.append((line, rel))
        parts.append(text)
        line += text.count("\n")
    _SRC_STARTS[:] = starts
    return "".join(parts)


def sloc(n):
    """line n of the joined source -> 'file:line'"""
    first, name = max((st for st in _SRC_STARTS if st[0] <= n), key=lambda st: st[0])
    return f"{name}:{n - first + 1}"


def load_player(path):
    """-> (player.py source, the raw UI page text, locate(offset) -> 'file:line').
    The page is assembled from static/ the way player.py's build_ui() does it, but WITHOUT the four generated replacements (as the old
    `UI = r\"\"\"...\"\"\"` string was). Falls back to the old embedded string for a player.py that has none."""
    path = Path(path)
    src = read_sources(path)
    st = path.parent / "static"
    if (st / "index.html").exists():
        rd = lambda n: (st / n).read_text(encoding="utf-8")
        ix = _parts(rd("index.html"), ["<!--@include style.css-->", "<!--@include app.js-->"])
        ap = _parts(rd("app.js"), ["//@include icons.js\n", "//@include tour.js\n"])
        # (text, file, first line or None = continue the file, extra lines taken by the marker that follows: a //@include line of app.js)
        segs = [(ix[0], "index.html", 1, 0), (rd("style.css"), "style.css", 1, 0), (ix[1], "index.html", None, 0),
                (ap[0], "app.js", 1, 1), (rd("icons.js"), "icons.js", 1, 0), (ap[1], "app.js", None, 1), (rd("tour.js"), "tour.js", 1, 0),
                (ap[2], "app.js", None, 0), (ix[2], "index.html", None, 0)]
        done, mapping, ui = {"index.html": 0, "app.js": 0}, [], ""      # done = lines of the file used so far
        for text, fn, first, extra in segs:
            if first is None:
                first = 1 + done[fn]
            mapping.append((len(ui), fn, first))
            ui += text
            if fn in done:
                done[fn] += text.count("\n") + extra
        def locate(off):
            for start, fn, first in reversed(mapping):
                if off >= start:
                    return f"static/{fn}:{first + ui[start:off].count(chr(10))}"
            return "static/index.html:1"
        return src, ui, locate
    m = re.search(r'^UI = r"""(.*?)"""', src, re.S | re.M)
    line0 = src[: m.start()].count("\n") + 1
    return src, m.group(1), (lambda off: f"player.py:{line0 + m.group(1)[:off].count(chr(10))}")


def command_words(src):
    tree = ast.parse(src)
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == "command":
            words = {}
            for c in ast.walk(n):
                if isinstance(c, ast.Constant) and isinstance(c.value, str) and re.fullmatch(r"[a-z_]+", c.value):
                    words.setdefault(c.value, c.lineno)
            return words, n.lineno
    raise SystemExit("command() not found in player.py / cpl/")


def routes(src):
    out = []
    for m in re.finditer(r'web\.(get|post|delete|put)\("([^"]+)",\s*(\w+)\)', src):
        path = re.sub(r"\{(\w+):[^}]*\}", r"{\1}", m.group(2))
        out.append((m.group(1).upper(), path, m.group(3), src[: m.start()].count("\n") + 1))
    return out


def handler_doc(src, name):
    m = re.search(r'(?:async )?def %s\(.*?\):\s*\n\s*"""(.*?)"""' % name, src, re.S)
    return " ".join(m.group(1).split()) if m else ""


def var_info(src):
    m = re.search(r"^VAR_INFO = \{(.*?)^\}", src, re.S | re.M)
    d = {}
    if m:
        for k, v in re.findall(r'^\s+"(\w+)":\s*(.+?),?\s*$', m.group(1), re.M):
            d[k] = v.strip().strip('"').strip("'")
    snap = re.search(r"^def snapshot\(\):(.*?)^def ", src, re.S | re.M)
    keys = re.findall(r'^\s+"(\w+)":', snap.group(1), re.M) if snap else []
    return d, keys


# ------------------------------------------------------------------ UI crawl
ATTR = re.compile(r'([\w:-]+)(?:=("[^"]*"|\'[^\']*\'|[^\s>]+))?')
ELEM = re.compile(r'<(button|input|select|textarea|summary)\b((?:[^>"\']|"[^"]*"|\'[^\']*\')*)>', re.S)


def attrs(s):
    d = {}
    for k, v in ATTR.findall(s):
        d[k.lower()] = (v or "").strip("\"'")
    return d


def matching(text, i):
    """index just after the brace block that opens at text[i] == '{'"""
    depth, j, n = 0, i, len(text)
    q = None
    while j < n:
        c = text[j]
        if q:
            if c == "\\":
                j += 1
            elif c == q:
                q = None
        elif c in "'\"`":
            q = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return n


def js_functions(script):
    fns = {}
    for m in re.finditer(r"(?:async\s+)?function\s+(\w+)\s*\(", script):
        b = script.find("{", m.end())
        if b > 0:
            fns[m.group(1)] = script[m.start(): matching(script, b)]
    for m in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([\w,\s=]*\)|\w+)\s*=>", script):
        if m.group(1) in fns:
            continue
        rest = script[m.end(): m.end() + 1]
        if script[m.end():].lstrip().startswith("{"):
            b = script.find("{", m.end())
            fns[m.group(1)] = script[m.start(): matching(script, b)]
        else:
            e = script.find(";\n", m.end())
            fns[m.group(1)] = script[m.start(): e if e > 0 else m.end() + 400]
    return fns


API_RE = re.compile(r"""(?:\bj|fetch|postJSON|api)\(\s*(?:`|'|")(/api/[^`'"?$]*)""")
CMD_RE = re.compile(r"""\bcmd\(\s*(?:`|'|")([^`'"?]*)""")


REFRESH = ("GET /api/state", "GET /api/library", "GET /api/playlists", "GET /api/devices", "GET /api/scan", "GET /api/storage", "GET /api/formats", "GET /api/meters", "GET /api/triggers", "GET /api/preview", "GET /api/settings", "GET /api/ffmpeg", "GET /api/monitor", "GET /api/download")


def drop_refresh(calls):
    """A handler that changes something usually ends by re-reading the lists; those reads are not what the control does."""
    act = [c for c in calls if c not in REFRESH and not c.startswith(REFRESH[0] + "…")]
    return act or calls


def calls_in(body, fns, seen=None, depth=0, maxdepth=2):
    """API endpoints and commands a piece of JS reaches (following the functions it calls, 2 levels)."""
    seen = seen if seen is not None else set()
    out = []
    for m in API_RE.finditer(body):
        method = re.search(r"method\s*:\s*['\"](\w+)", body[m.start(): m.start() + 200])
        path = m.group(1)
        tail = body[m.end(): m.end() + 1]
        out.append(f"{method.group(1).upper() if method else 'GET'} {path}{'…' if path.endswith('/') else ''}")
    for m in CMD_RE.finditer(body):
        out.append("cmd " + re.sub(r"\$\{[^}]*\}", "<x>", m.group(1)))
    if depth < maxdepth:
        for name in set(re.findall(r"\b([A-Za-z_]\w*)\(", body)):
            if name in fns and name not in seen:
                seen.add(name)
                out += calls_in(fns[name], fns, seen, depth + 1, maxdepth)
    return out


def ui_crawl(ui, locate):
    cut = ui.rfind("<script>")
    html, script = ui[:cut], ui[cut:]
    fns = js_functions(script)
    rows, base_count = [], Counter()
    containers = [(m.start(), m.group(1)) for m in re.finditer(r"<(?:dialog|div|section|aside)\b[^>]*\bid=(\w+)", html)]
    fn_pos = sorted((m.start(), m.group(1)) for m in re.finditer(r"(?:async\s+)?function\s+(\w+)\s*\(|(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\(?[\w,\s]*\)?\s*=>",
                                                                  script) for m in [m] if True and (m.group(1) or m.group(2))) if False else []
    fn_pos = []
    for m in re.finditer(r"(?:async\s+)?function\s+(\w+)\s*\(", script):
        fn_pos.append((m.start(), m.group(1)))

    def where_of(pos, in_script):
        if in_script:
            prev = [n for p, n in fn_pos if p <= pos]
            return "script:" + (prev[-1] if prev else "top level")
        prev = [n for p, n in containers if p <= pos]
        return "page:#" + prev[-1] if prev else "page"

    listeners = script
    for source, text, off in (("page", html, 0), ("script", script, cut)):
        for m in ELEM.finditer(text):
            tag, a = m.group(1), attrs(m.group(2))
            if tag == "input" and a.get("type") == "hidden":
                continue
            inner = ""
            if tag in ("button", "summary"):
                e = text.find("</", m.end())
                inner = re.sub(r"\$\{[^}]*\}", "", re.sub(r"<[^>]+>", "", text[m.end(): e if e > 0 else m.end() + 80]))
                inner = " ".join(inner.split())[:40]
            label = inner or a.get("aria-label") or a.get("title") or a.get("placeholder") or a.get("id") or a.get("data-act") or tag
            label = re.sub(r"\$\{[^}]*\}", "…", label)[:70]
            handler_attrs = {k: v for k, v in a.items() if k in ("onclick", "onchange", "oninput", "onkeydown", "ondblclick")}
            code = " ".join(handler_attrs.values())
            calls, kind = [], ""
            if code:
                called = [n for n in re.findall(r"\b([A-Za-z_]\w*)\(", code) if n in fns]
                calls = calls_in(code, fns, set(called))
                for n in called:
                    calls += calls_in(fns[n], fns, {n})
                kind = "handler"
            elif a.get("data-act") or a.get("data-info") or a.get("data-tip") or a.get("data-hint") or a.get("data-d") or a.get("data-s") or a.get("data-f"):
                key = a.get("data-act") or ("info" if "data-info" in a else "tip" if "data-tip" in a else "hint" if "data-hint" in a else "ltb")
                kind = "delegated"
                for mm in re.finditer(r"""['"]%s['"]""" % re.escape(key), script):
                    seg = script[mm.start(): mm.start() + 700]
                    calls += calls_in(seg, fns)
                    break
            elif a.get("id") and re.search(r"\b%s\.(?:addEventListener|onclick|onchange|oninput)|getElementById\(['\"]%s['\"]\)\.(?:addEventListener|on)|#%s\b" % ((re.escape(a["id"]),) * 3), script):
                kind = "listener"
                mm = re.search(r"\b%s\.(?:addEventListener|onclick|onchange|oninput)[^\n]*" % re.escape(a["id"]), script)
                if mm:
                    calls = calls_in(script[mm.start(): mm.start() + 600], fns)
            elif a.get("data-v"):
                kind = "delegated"
            if not kind and source == "script":                 # a button drawn by a function whose container has one delegated listener
                enc = [n for p, n in fn_pos if p <= m.start()]
                body = fns.get(enc[-1], "") if enc else ""
                for cont in re.findall(r"(\w+)\.innerHTML", body):
                    lm = re.search(r"\b%s\.addEventListener\(\s*'(?:click|change)'[^\n]*" % re.escape(cont), script)
                    if lm:
                        kind = "delegated"
                        calls = calls_in(script[lm.start(): lm.start() + 700], fns)
                        break
            calls = drop_refresh(list(dict.fromkeys(calls)))
            base = a.get("id") or (re.sub(r"\W+", "_", (code.split("(")[0] if code else "") or a.get("data-act") or tag) or tag)
            base_count[base] += 1
            cid = f"ui.{base}" + ("" if base_count[base] == 1 else f".{base_count[base]}")
            loc = locate(off + m.start())
            rows.append({"id": cid, "tag": tag, "label": label, "where": where_of(m.start(), source == "script") + f" ({loc})", "code": code[:140], "kind": kind,
                         "calls": calls, "dyn": source == "script", "attrs": a})
    # delegated click listeners of the script (rows of their own)
    for m in re.finditer(r"([\w.$#\[\]'\"()-]+)\.addEventListener\(\s*'(click|change|keydown|input|drop|pointerdown)'", script):
        pos = m.start()
        target = m.group(1)
        seg = script[pos: pos + 900]
        if m.group(2) in ("click", "change", "drop"):
            rows.append({"id": f"ui.listener.{m.group(2)}.{re.sub(r'[^a-zA-Z0-9_]+', '_', target)[:30]}", "tag": "listener", "label": f"{target} {m.group(2)} listener", "where":
                         f"script ({locate(cut + pos)})", "code": seg.split("\n")[0][:140], "kind": "listener",
                         "calls": list(dict.fromkeys(calls_in(seg, fns))), "dyn": True, "attrs": {}})
    return rows, fns


CMD_AREA = {"play": "transport", "take": "transport", "xfade": "transport", "cut": "transport", "stop": "transport", "stopall": "transport", "pause": "transport",
            "resume": "transport", "playpause": "transport", "fadeout": "transport", "seek": "transport", "toggle": "transport", "top": "ducking", "volume": "volume",
            "solo": "preview", "preview": "preview", "mode": "play mode", "next": "cue", "prev": "cue", "clear": "cue", "focus": "cue", "go_transition": "transport",
            "device": "output", "rescan": "library", "resend": "companion", "loop": "end action", "end": "end action", "duck": "ducking"}


def ui_area(calls, label, where):
    s = " ".join(calls)
    for key, area in (("/api/library", "library"), ("/api/download", "library"), ("/api/waveform", "library"), ("/api/playlists", "playlists"), ("/api/move", "playlists"),
                      ("/api/preview", "preview"), ("/api/mirror", "output"), ("/api/device", "output"), ("/api/triggers", "triggers"), ("/api/settings/top", "ducking"),
                      ("/api/settings", "settings"), ("/api/restart", "lifecycle")):
        if key in s:
            return area
    for c in calls:
        if c.startswith("cmd "):
            w = c[4:].strip("/").split("/")
            w = [x for x in w if x and not x.startswith("<")]
            for x in w[:3]:
                if x in CMD_AREA:
                    return CMD_AREA[x]
    if "dialog" in where or "#lxdlg" in where or "#lidlg" in where or "#trdlg" in where:
        return "dialogs"
    return "ui-local"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", default=str(HERE.parent / "player.py"))
    ap.add_argument("--out", default=str(HERE / "controls.csv"))
    a = ap.parse_args()
    src, ui, locate = load_player(a.player)
    cov = covered_ids()
    rows, unclassified = [], []

    def add(**k):
        r = {c: "" for c in COLS}
        r.update(k)
        rows.append(r)

    # ---- commands
    words, cline = command_words(src)
    known = set(M.WORDS_IGNORE)
    for cid, area, grammar, ws, exp, ver, pre in M.COMMANDS:
        known |= set(ws)
        st, tests = status_for(cid, cov, "untested")
        add(id=cid, area=area, kind="command", where=f"{sloc(cline)} command()", control=grammar + "   [HTTP GET /api" + grammar.split()[0] + "; OSC " + grammar.split()[0] + "]",
            expected_result=exp, how_to_verify=ver, preconditions=pre, tests=tests, status=st)
    for w, ln in sorted(words.items(), key=lambda x: x[1]):
        if w not in known and not w.startswith(("duck_", "top_", "preview_", "live_", "audio_", "go_")):
            unclassified.append(("command word", w, sloc(ln)))
            add(id=f"cmd.UNCLASSIFIED.{w}", area="?", kind="command", where=f"{sloc(ln)} command()", control=f"keyword '{w}'", expected_result="(not in controls_meta)", status="UNCLASSIFIED")

    # ---- HTTP
    for method, path, handler, ln in routes(src):
        key = f"{method} {path}"
        cid = "http." + key
        meta = M.HTTP.get(key)
        doc = handler_doc(src, handler)
        if meta:
            area, exp, ver, pre = meta
            st, tests = status_for(cid, cov, "untested")
            add(id=cid, area=area, kind="http", where=f"{sloc(ln)} {handler}()", control=key, expected_result=exp, how_to_verify=ver, preconditions=pre, tests=tests, status=st)
        else:
            unclassified.append(("http endpoint", key, sloc(ln)))
            add(id=cid, area="?", kind="http", where=f"{sloc(ln)} {handler}()", control=key, expected_result=doc[:150] or "(not in controls_meta)", status="UNCLASSIFIED")
    seen = {f"{m} {p}" for m, p, _, _ in routes(src)}
    for k in M.HTTP:
        if k not in seen:
            unclassified.append(("controls_meta entry with no route", k, "controls_meta.HTTP"))

    # ---- OSC
    for cid, area, ctl, exp, ver, pre in M.OSC:
        st, tests = status_for(cid, cov, "untested")
        add(id=cid, area=area, kind="osc", where="player.py osc_default() / push()", control=ctl, expected_result=exp, how_to_verify=ver, preconditions=pre, tests=tests, status=st)

    # ---- variables
    info, keys = var_info(src)
    for k in sorted(set(info) | set(keys)):
        doc = info.get(k)
        st, tests = status_for("var.*", cov, "untested")
        add(id=f"var.{k}", area="variables", kind="variable", where="player.py snapshot() / VAR_INFO", control=f"OSC out /custom-variable/<prefix>{k}/value; GET /api/variables",
            expected_result=doc or "(undocumented)", how_to_verify="/api/variables value equals /api/state; OSC sink receives it", preconditions="-", tests=tests, status=st if doc else "undocumented")
        if not doc:
            unclassified.append(("variable without a description", k, "VAR_INFO"))
    for pat, desc in (("pl<N>_name", "Name of playlist N"), ("pl<N>_count", "Number of tracks of playlist N"), ("pl<N>_t<K>", "Name of track K of playlist N"),
                      ("focus_t0..focus_t31", "Name of track K of the cued playlist ('-' when unused); focus_count")):
        st, tests = status_for("var.*", cov, "untested")
        add(id="var.dyn." + re.sub(r"\W+", "_", pat), area="variables", kind="variable", where="player.py list_vars()", control=pat, expected_result=desc, how_to_verify="/api/variables",
            preconditions="playlists exist", tests=tests, status=st)

    # ---- UI
    urows, fns = ui_crawl(ui, locate)
    for r in urows:
        calls = r["calls"]
        area = ui_area(calls, r["label"], r["where"])
        if r["kind"] in ("handler", "delegated", "listener"):
            if calls:
                exp = f"{r['label']}: calls " + "; ".join(calls[:4]) + ("…" if len(calls) > 4 else "")
                ver = "Playwright: click it, then check the matching API state (" + ", ".join(sorted({c.split()[-1] for c in calls[:3]})) + ")"
            else:
                exp = f"{r['label']}: changes the page only (no API call found)"
                ver = "Playwright: DOM / class / localStorage change"
            st = "ui-pending (phase 2)"
        else:
            if r["tag"] in ("input", "select", "textarea") and not r["code"]:
                exp, ver, st = f"{r['label']}: input read by other code (value used when a button runs)", "Playwright: enter a value, run the button that reads it", "ui-pending (phase 2)"
                r["kind"] = "input-field"
            else:
                exp, ver, st = "(no handler found in the page script)", "", "UNCLASSIFIED"
                unclassified.append(("UI control with no handler found", f"{r['tag']} {r['label']}", r["where"]))
        add(id=r["id"], area=area, kind="ui", where=r["where"], control=f"<{r['tag']}> {r['label']}" + (f"   [{r['code']}]" if r["code"] else ""), expected_result=exp, how_to_verify=ver,
            preconditions="page loaded" + ("; row rendered from data" if r["dyn"] else ""), api_calls="; ".join(calls[:6]), status=st)

    # ---- dangling covers() ids
    ids = {r["id"] for r in rows}
    for cid in cov:
        if cid not in ids and cid != "var.*" and not any(i.startswith(cid + ".") for i in ids):
            unclassified.append(("test covers an id that is not in the map", cid, "; ".join(sorted(cov[cid]))[:80]))

    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    # ---- summary
    print(f"wrote {a.out}: {len(rows)} rows")
    by = Counter((r["kind"], r["area"]) for r in rows)
    print("\nrows per kind / area")
    for (k, ar), n in sorted(by.items()):
        print(f"  {k:9} {ar:14} {n}")
    print("\nstatus")
    for k, n in Counter(r["status"].split(" (")[0] for r in rows).most_common():
        print(f"  {k:22} {n}")
    if unclassified:
        print(f"\nUNCLASSIFIED / needs attention ({len(unclassified)}):")
        for kind, what, where in unclassified:
            print(f"  [{kind}] {what}   <- {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
