"""Library scan and file operations.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import filecmp, os, re, shutil
from pathlib import Path

from cpl import cache, clock, state as S
from cpl.cache import cache_drop
from cpl.config import AUDIO_EXT, CFG, LIB, MEDIA
from cpl.persist import save
from cpl.playlists import clamp_focus, remove_from_playlist, track
from cpl.state import FOLDER_COLORS, FOLDER_FLAGS, FOLDER_ICONS, LIBDIRS, decks, library, playlists
from cpl.util import _sc, parse_size


def storage_info(force=False):
    if force or _sc["v"] is None or clock.monotonic() - _sc["t"] > 5:
        du = shutil.disk_usage(MEDIA)
        cap = parse_size(CFG["storage_limit"], du.total)
        reserve = parse_size(CFG["storage_reserve"], du.total) or 0
        used = sum(library.values())
        by_disk = max(0, du.free - reserve)
        by_cap = None if cap is None else max(0, cap - used)
        allowance = by_disk if by_cap is None else min(by_disk, by_cap)
        _sc["v"] = {"used": used, "files": len(library), "cap": cap, "reserve": reserve,
                    "disk_total": du.total, "disk_free": du.free, "allowance": allowance,
                    "limited_by": "cap" if (by_cap is not None and by_cap <= by_disk) else "disk",
                    "over": bool(cap is not None and used > cap)}
        _sc["t"] = clock.monotonic()
    return _sc["v"]


def invalidate_storage():
    _sc["t"] = 0.0
    _sc["v"] = None


# ---------------------------------------------------------------- library
def scan_library():
    """Read media/library/ from disk. Sub-folders are fine; ids are paths relative to the library."""
    found, found_dirs = {}, set()
    for root, dirs, files in os.walk(LIB):
        dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
        for d in dirs:
            found_dirs.add((Path(root) / d).relative_to(LIB).as_posix())
        for f in files:
            if f.startswith(".") or Path(f).suffix.lower() not in AUDIO_EXT:
                continue
            full = Path(root) / f
            try:
                found[full.relative_to(LIB).as_posix()] = full.stat().st_size
            except OSError:
                pass
    library.clear()
    library.update(found)
    LIBDIRS.clear()
    LIBDIRS.update(found_dirs)
    invalidate_storage()


def unique_in_lib(name):
    dest, n, p = LIB / name, 1, Path(name)
    while dest.exists():
        dest = LIB / p.parent / f"{p.stem} ({n}){p.suffix}"
        n += 1
    return dest


def _safe_rel(rel, last_is_dir):
    """Clean a path typed in the web page: no .., no hidden (.x) names, no _x folders (those are skipped when scanning).
    Returns the cleaned path relative to the library, or None if it is not allowed."""
    parts = [x for x in str(rel).replace("\\", "/").split("/") if x.strip()]
    out = []
    for i, x in enumerate(parts):
        if x in (".", ".."):
            return None
        q = re.sub(r"\s+", " ", re.sub(r"[^\w.\- ]", "_", x)).strip()
        is_dir = last_is_dir or i < len(parts) - 1
        if not q or q.startswith(".") or (is_dir and q.startswith("_")) or len(q) > 120:
            return None
        out.append(q)
    return "/".join(out) or None


def mkdir_new(path):
    """Create a library folder (and any missing parents). Folders that did not exist get the default folder icon."""
    path = Path(path)
    missing, p = [], path
    while not p.exists() and p != LIB and LIB in p.parents:
        missing.append(p)
        p = p.parent
    path.mkdir(parents=True, exist_ok=True)
    ic = str(CFG.get("default_folder_icon") or "")
    if missing and re.fullmatch(r"[a-z0-9-]{1,32}", ic):
        for m in missing:
            FOLDER_ICONS.setdefault(m.relative_to(LIB).as_posix(), ic)
        save()


def lib_mkdir(rel):
    rel = _safe_rel(rel, True)
    if not rel:
        return "that folder name is not allowed", 400
    if (LIB / rel).exists():
        return "that folder already exists", 409
    mkdir_new(LIB / rel)
    scan_library()
    return rel, 200


def lib_rmdir(rel, force=False):
    """Delete a library folder. Without force only an empty one goes; with force everything in it is deleted too
    (its tracks leave every playlist)."""
    rel = _safe_rel(rel, True)
    if not rel or not (LIB / rel).is_dir():
        return "no such folder", 404
    inside = [f for f in list(library) if f.startswith(rel + "/")]
    if inside and not force:
        return "the folder is not empty (move or delete its files first)", 409
    for f in inside:
        delete_from_library(f)                        # also takes it out of the playlists and the sound cache
    try:
        if force:
            shutil.rmtree(LIB / rel)                  # whatever else is in there (other file types, sub-folders)
        else:
            for root, dirs, files in os.walk(LIB / rel, topdown=False):
                os.rmdir(root)
    except OSError:
        return "the folder still contains other files", 409
    for k in list(FOLDER_COLORS) + list(FOLDER_ICONS) + list(FOLDER_FLAGS):
        if k == rel or k.startswith(rel + "/"):
            FOLDER_COLORS.pop(k, None)
            FOLDER_ICONS.pop(k, None)
            FOLDER_FLAGS.pop(k, None)
    scan_library()
    save()
    return "ok", 200


def lib_rename(old, new):
    """Rename or move a library file or folder. Playlists, the sound cache and the playing track follow it.
    Returns (message_or_new_id, http_status)."""
    old = str(old).strip("/")
    src = LIB / old
    is_dir = src.is_dir()
    if not old or ".." in old.split("/") or not (is_dir or old in library):
        return "no such file or folder", 404
    new = _safe_rel(new, is_dir)
    if not new:
        return "that name is not allowed", 400
    if not is_dir and Path(new).suffix.lower() != Path(old).suffix.lower():
        return "keep the same file type (" + Path(old).suffix + ")", 400
    if is_dir and (new == old or new.startswith(old + "/")):
        return "a folder can't be moved into itself", 400
    dst = LIB / new
    if new == old:
        return new, 200
    if dst.exists() and not (old.lower() == new.lower() and src.samefile(dst)):
        return "something with that name already exists there", 409
    try:
        mkdir_new(dst.parent)
        os.rename(src, dst)
    except OSError as e:
        return f"could not rename: {e}", 500

    def m(fid):
        if fid == old:
            return new
        return new + fid[len(old):] if is_dir and fid.startswith(old + "/") else fid

    for pl in playlists:
        pl["tracks"] = [m(x) for x in pl["tracks"]]
        if pl.get("end_actions"):
            pl["end_actions"] = {m(k): v for k, v in pl["end_actions"].items()}
        if pl.get("xfades"):
            pl["xfades"] = {m(k): v for k, v in pl["xfades"].items()}
        if pl.get("trims"):
            pl["trims"] = {m(k): v for k, v in pl["trims"].items()}
        if pl.get("triggers"):                           # both the track the trigger belongs to and the track it plays
            pl["triggers"] = {m(k): [{**x, "file": m(x["file"])} for x in v] for k, v in pl["triggers"].items()}
    if S.known is not None:
        S.known = {m(x) for x in S.known}
    cache.rename_path(m)                               # the decoded sounds, meter and ducking data follow the new names; trimmed copies are rebuilt by the warm-up
    for d in decks:                                    # a playing track keeps playing; just show the new name
        tr = track(*d.pt) if d.pt else None
        if tr:
            d.name = tr["name"]
    if S.pending:
        S.pending["fid"] = m(S.pending["fid"])
        tr = track(*S.pending["pt"])
        S.pending["name"] = tr["name"] if tr else S.pending["name"]
    if is_dir:
        for store in (FOLDER_COLORS, FOLDER_ICONS, FOLDER_FLAGS):
            for k in list(store):
                if k == old or k.startswith(old + "/"):
                    store[new + k[len(old):]] = store.pop(k)
    scan_library()
    save()
    return new, 200


def find_duplicate(path, size):
    """Return the id of a library file with identical contents, or None."""
    for fid, sz in list(library.items()):                # a copy: this also runs in a worker thread
        if sz == size and (LIB / fid) != Path(path):
            try:
                if filecmp.cmp(path, LIB / fid, shallow=False):
                    return fid
            except OSError:
                pass
    return None


def missing_refs():
    out = {}
    for pl in playlists:
        miss = [fid for fid in pl["tracks"] if fid not in library]
        if miss:
            out[pl["name"]] = sorted(set(miss))
    return out


def rescan_library():
    before = set(library)
    scan_library()
    S.last_scan = {"new": sorted(set(library) - before), "gone": sorted(before - set(library)), "missing": missing_refs()}
    clamp_focus()
    save()


def delete_from_library(fid):
    """Permanently delete a file and remove it from every playlist."""
    if fid not in library:
        return "invalid"
    for p, pl in enumerate(playlists):
        for t in range(len(pl["tracks"]) - 1, -1, -1):
            if pl["tracks"][t] == fid:
                remove_from_playlist(p, t, save_now=False)
    path = LIB / fid
    cache_drop(str(path))
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    library.pop(fid, None)
    invalidate_storage()
    save()
    return "ok"
