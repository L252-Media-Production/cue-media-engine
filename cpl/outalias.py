"""Output aliases (2.8.0 output-alias): a label, a group, a "hidden" flag and a "live only" flag for output names the player already sees.

Pure bookkeeping around the raw SDL names. Nothing here opens a device, and the saved Live / Preview / Mirror outputs stay the raw
names (matching, health and the Companion variable `output` all use them). The table is `CFG["output_aliases"]` (state.json): None =
never saved, the built-in default applies; a saved list (even an empty one) replaces the default completely.

Each entry: {"match": exact SDL name (case-sensitive), "label": text shown instead (optional), "hidden": bool (default false),
"group": menu heading (optional), "live_only": bool (default false)}.
"""
from cpl.config import CFG

MAX_ENTRIES = 32
MAX_TEXT = 80
LIVE_ONLY_MSG = "Only one program can use Dante over IP. Use it for Live."

# The ALSA loopback card that Inferno (Dante over IP) uses: the player plays into device 0, Inferno reads the other end (device 1).
DEFAULT_ALIASES = [
    {"match": "Loopback, Loopback PCM", "label": "Dante over IP", "hidden": False, "group": "Network audio", "live_only": True},
    {"match": "Loopback, Loopback PCM (2)", "label": "", "hidden": True, "group": "", "live_only": False},
]


def _text(v, what, required=False):
    if v is None:
        v = ""
    if not isinstance(v, str):
        raise ValueError(f"{what} must be text")
    if len(v) > MAX_TEXT:
        raise ValueError(f"{what} can be at most {MAX_TEXT} characters")
    if required and not v:
        raise ValueError(f"{what} is needed")
    return v


def _flag(v, what):
    if v is None:
        return False
    if not isinstance(v, bool):
        raise ValueError(f"{what} must be true or false")
    return v


def clean_entry(e):
    """One entry, checked and normalised. Raises ValueError with a plain message."""
    if not isinstance(e, dict):
        raise ValueError("each alias must be an object with a \"match\" name")
    match = _text(e.get("match"), "\"match\"", True)
    return {"match": match, "label": _text(e.get("label"), "\"label\"").strip(), "hidden": _flag(e.get("hidden"), "\"hidden\""),
            "group": _text(e.get("group"), "\"group\"").strip(), "live_only": _flag(e.get("live_only"), "\"live_only\"")}


def clean_aliases(v):
    """The whole table, checked as it is saved: a list of at most MAX_ENTRIES entries, no match twice. Raises ValueError."""
    if not isinstance(v, list):
        raise ValueError("output_aliases must be a list")
    if len(v) > MAX_ENTRIES:
        raise ValueError(f"at most {MAX_ENTRIES} aliases")
    out, seen = [], set()
    for i, e in enumerate(v, 1):
        try:
            c = clean_entry(e)
        except ValueError as ex:
            raise ValueError(f"alias {i}: {ex}") from None
        if c["match"] in seen:
            raise ValueError(f"alias {i}: \"{c['match']}\" is listed twice")
        seen.add(c["match"])
        out.append(c)
    return out


def table():
    """The table in use: the saved one, or the default while nothing was ever saved. A saved table that was damaged by hand in
    state.json is read entry by entry: a bad entry is skipped, it never breaks the device list."""
    v = CFG.get("output_aliases")
    if v is None:
        return [dict(e) for e in DEFAULT_ALIASES]
    if not isinstance(v, list):
        return []
    out, seen = [], set()
    for e in v[:MAX_ENTRIES]:
        try:
            c = clean_entry(e)
        except ValueError:
            continue
        if c["match"] not in seen:
            seen.add(c["match"])
            out.append(c)
    return out


def is_default():
    return CFG.get("output_aliases") is None


def lookup(name, tbl=None):
    for e in (table() if tbl is None else tbl):
        if e["match"] == name:
            return e
    return None


def label_of(name, tbl=None):
    """What the user sees for a raw name: the alias label, else the raw name."""
    e = lookup(name, tbl)
    return (e["label"] if e and e["label"] else name)


def live_only(name, tbl=None):
    e = lookup(name, tbl)
    return bool(e and e["live_only"])


def shown(name, tbl=None):
    """The label first, the raw name in brackets, for an aliased output (health panel and report); an unaliased name exactly as it is."""
    lab = label_of(name, tbl)
    return name if lab == name else f"{lab} ({name})"


def info(names, tbl=None):
    """One object per device, in the order given: {name, label, hidden, group, live_only}."""
    t = table() if tbl is None else tbl
    out = []
    for n in names:
        e = lookup(n, t)
        out.append({"name": n, "label": e["label"] if e and e["label"] else n, "hidden": bool(e and e["hidden"]),
                    "group": e["group"] if e else "", "live_only": bool(e and e["live_only"])})
    return out
