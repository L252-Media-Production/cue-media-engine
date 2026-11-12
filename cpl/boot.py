"""Start-up data loading: migrate_old and load.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import json, re
from pathlib import Path

from cpl import clock, state as S
from cpl.cache import resolve_path
from cpl.config import AUDIO_EXT, DATA, MEDIA
from cpl.library import invalidate_storage, missing_refs, scan_library, storage_info
from cpl.persist import save
from cpl.playlists import clamp_focus
from cpl.state import FOLDER_COLORS, FOLDER_FLAGS, FOLDER_ICONS, library, playlists
from cpl.upload import import_file
from cpl.util import fmt_bytes


def migrate_old(data):
    """Earlier versions kept one folder per playlist (media/<name>/) or loose files in media/."""
    out, done, folders = [], {}, []
    for pl in data.get("playlists", []):
        srcs = [Path(resolve_path(t["path"])) for t in pl.get("tracks", []) if isinstance(t, dict) and t.get("path")]
        folder = MEDIA / pl["folder"] if pl.get("folder") else None
        if folder and folder.is_dir():
            folders.append(folder)
            have = {s.resolve() for s in srcs if s.exists()}
            srcs += [f for f in sorted(folder.iterdir(), key=lambda f: f.name.lower())
                     if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in AUDIO_EXT
                     and f.resolve() not in have]
        ids = []
        for s in srcs:
            if str(s) in done:
                ids.append(done[str(s)])
            elif s.exists():
                done[str(s)] = import_file(s)
                ids.append(done[str(s)])
            else:
                print(f"  [{pl['name']}] skipped missing file {s.name}")
        out.append({"name": pl["name"], "tracks": ids})
        print(f"Migrated playlist '{pl['name']}': {len(ids)} track(s) now reference the shared library")
    for f in folders:
        try:
            f.rmdir()                             # only succeeds if empty
        except OSError:
            pass
    return out


def load():
    data = {}
    if DATA.exists():
        try:
            data = json.loads(DATA.read_text())
        except Exception as e:
            bad = DATA.with_name(f"playlists.corrupt-{int(clock.time())}.json")
            try:
                DATA.replace(bad)                    # keep it: the next save must not overwrite what was there
            except OSError:
                pass
            print(f"playlists.json could not be read ({e}); it was kept as {bad.name}")
            bak = DATA.with_suffix(".bak")
            try:
                data = json.loads(bak.read_text())
                print("Restored the playlists from playlists.bak")
            except Exception:
                data = {}
    FOLDER_COLORS.clear()
    FOLDER_COLORS.update({k: v for k, v in (data.get("folder_colors") or {}).items()
                          if isinstance(k, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", str(v))})
    FOLDER_ICONS.clear()
    FOLDER_ICONS.update({k: v for k, v in (data.get("folder_icons") or {}).items()
                         if isinstance(k, str) and re.fullmatch(r"[a-z0-9-]{1,32}", str(v))})
    FOLDER_FLAGS.clear()
    fl = data.get("folder_flags")
    for k, v in (fl.items() if isinstance(fl, dict) else ()):
        if isinstance(k, str) and isinstance(v, dict):
            keep = {f: True for f in ("fav", "hidden") if v.get(f) is True}
            if keep:
                FOLDER_FLAGS[k] = keep
    scan_library()
    if data.get("playlists") and data.get("version") != 2:
        DATA.with_name("playlists.pre-library.json").write_text(DATA.read_text())   # safety copy
        playlists[:] = migrate_old(data)
        S.known = None
        invalidate_storage()
    else:
        playlists[:] = data.get("playlists", [])
        S.known = set(data["known"]) if "known" in data else None
    for pl in playlists:                 # looping one track used to be a playlist mode; it is now a switch on each track
        if pl.get("mode") == "loop_track":
            pl["mode"] = "stop"
            pl["loops"] = list(pl.get("tracks", []))
    if any("loops" in pl for pl in playlists):          # the old per-track loop list becomes end_actions (loop)
        if DATA.exists():
            DATA.with_name("playlists.pre-endactions.json").write_text(DATA.read_text())   # safety copy
        for pl in playlists:
            old = pl.pop("loops", None)
            if old:
                ea = pl.setdefault("end_actions", {})
                for fid in old:
                    ea.setdefault(fid, "loop")
    new = sorted(set(library) - S.known) if S.known is not None else []
    gone = sorted(S.known - set(library)) if S.known is not None else []
    S.last_scan = {"new": new, "gone": gone, "missing": missing_refs()}
    if new:
        print(f"Library: {len(new)} file(s) added since last run: {', '.join(new)}")
    if gone:
        print(f"Library: {len(gone)} file(s) were removed since last run: {', '.join(gone)}")
    for name, ids in S.last_scan["missing"].items():
        print(f"[{name}] references file(s) missing from the library: {', '.join(ids)}")
    clamp_focus()
    save()
    si = storage_info(True)
    print(f"Library: {len(library)} file(s), {fmt_bytes(si['used'])}"
          + (f" of {fmt_bytes(si['cap'])} cap" if si["cap"] else "") + f" | disk free {fmt_bytes(si['disk_free'])}")
