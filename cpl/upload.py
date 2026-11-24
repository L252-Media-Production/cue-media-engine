"""Upload plumbing: import, space checks, save_upload.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import asyncio, os, re, shutil, time
from pathlib import Path

from cpl.config import AUDIO_EXT, BASE, CFG, LIB, MEDIA
from cpl.ffmpeg import CONVERT_EXT, FF, ff_check, ff_convert, ff_probe, needs_normalising
from cpl.library import find_duplicate, invalidate_storage, mkdir_new, storage_info, unique_in_lib
from cpl.state import LIBDIRS, library
from cpl.util import fmt_bytes


# ---------------------------------------------------------------- migration from older layouts
def import_file(src):
    """Bring a file from an older layout into the library (moving it, or copying if it lives outside media/)."""
    src = Path(src)
    try:
        return src.resolve().relative_to(LIB.resolve()).as_posix()      # already in the library
    except ValueError:
        pass
    size = src.stat().st_size
    inside = True
    try:
        src.resolve().relative_to(MEDIA.resolve())
    except ValueError:
        inside = False
    dup = find_duplicate(src, size)
    if dup:                                       # identical audio already in the library: reuse it
        if inside:
            src.unlink()
        return dup
    dest = unique_in_lib(src.name)
    (shutil.move if inside else shutil.copy2)(str(src), str(dest))
    fid = dest.relative_to(LIB).as_posix()
    library[fid] = size
    return fid


class NoSpace(Exception):
    pass


async def drain(part):
    while await part.read_chunk(1 << 20):
        pass


def space_error(need, info):
    why = "the library size limit" if info["limited_by"] == "cap" else "free disk space; a reserve is kept free"
    return f"Not enough space: {fmt_bytes(need)} needed, {fmt_bytes(info['allowance'])} available ({why})"


IMPORT_DIR = BASE / "_import"                  # working copies while converting; emptied at start
shutil.rmtree(IMPORT_DIR, ignore_errors=True)


async def save_upload(part, total_len, folder=""):
    """Store one uploaded file in the library (in a sub-folder if given). Returns {"id", "duplicate"} or {"error", "status"}.
    Other audio and video formats are converted by ffmpeg to 48 kHz FLAC; wav/flac the mixer would have to resample are converted too."""
    safe = re.sub(r"[^\w.\- ]", "_", part.filename)
    ext = Path(safe).suffix.lower()
    convert = ext in CONVERT_EXT and bool(CFG["import_convert"])
    if ext not in AUDIO_EXT and not convert:
        await drain(part)
        return {"error": "unsupported file type (use wav, mp3, ogg or flac" + (", or turn on import_convert to bring in other formats)" if ext in CONVERT_EXT else ")"), "status": 400}
    if convert and not ff_check():
        await drain(part)
        return {"error": f"{ext} files need ffmpeg to be imported, and {FF['err']}. Or convert the file to wav, mp3 or flac first.", "status": 415}
    info = storage_info(True)
    if total_len and total_len > info["allowance"] + 8192:      # small allowance for the multipart framing
        await drain(part)
        return {"error": space_error(total_len, info), "status": 507}
    mkdir_new(LIB / folder)
    stem = Path(safe).stem
    dest = unique_in_lib(f"{folder}/{stem}.flac" if folder else f"{stem}.flac") if convert else unique_in_lib(f"{folder}/{safe}" if folder else safe)
    work = dest
    if convert:
        IMPORT_DIR.mkdir(exist_ok=True)
        work = IMPORT_DIR / f"{os.getpid()}-{time.time_ns()}{ext}"
    written = 0
    loop = asyncio.get_running_loop()
    try:
        with open(work, "wb") as f:
            while chunk := await part.read_chunk(1 << 20):
                written += len(chunk)
                if written > info["allowance"]:
                    raise NoSpace()
                await loop.run_in_executor(None, f.write, chunk)      # keep disk waits off the event loop
    except NoSpace:
        work.unlink(missing_ok=True)
        await drain(part)
        return {"error": space_error(written, info), "status": 507}
    except Exception:
        work.unlink(missing_ok=True)             # interrupted upload: don't leave a partial file
        raise
    try:
        if convert:
            err = await ff_convert(work, dest, "flac")
            if err:
                return {"error": f"could not convert {Path(safe).name}: {err}", "status": 422}
            written = dest.stat().st_size
    finally:
        if convert:
            work.unlink(missing_ok=True)
    return await finish_import(dest, written, folder, normalise=not convert)


async def finish_import(dest, written, folder, normalise=True):
    """The common end of every import into the library (an upload, and since 2.9.0 a track made with ElevenLabs): `dest` is
    already in its library folder. wav/flac the mixer would have to resample are normalised (when ffmpeg is there); identical
    audio already in the library is reused (dest is deleted); otherwise the library entry is added. Duration, waveform, format
    check, loudness and the RAM cache follow from the library entry as for any file. Returns {"id", "duplicate"}."""
    ext = dest.suffix.lower()
    loop = asyncio.get_running_loop()
    if normalise and CFG["import_normalise"] and ext in (".wav", ".flac") and ff_check():
        probe = await ff_probe(dest)
        if needs_normalising(probe):
            tmp = IMPORT_DIR / f"{os.getpid()}-{time.time_ns()}{ext}"
            IMPORT_DIR.mkdir(exist_ok=True)
            os.replace(dest, tmp)
            err = await ff_convert(tmp, dest, ext[1:])
            if err:                           # keep the original rather than lose the upload
                os.replace(tmp, dest)
                print("import: could not normalise", dest.name, "-", err)
            else:
                tmp.unlink(missing_ok=True)
                written = dest.stat().st_size
    dup = await loop.run_in_executor(None, find_duplicate, dest, written)
    if dup:                                      # identical audio is already in the library: reuse it
        dest.unlink(missing_ok=True)
        return {"id": dup, "duplicate": True}
    fid = dest.relative_to(LIB).as_posix()
    library[fid] = written
    if folder:
        parts = folder.split("/")
        for i in range(1, len(parts) + 1):
            LIBDIRS.add("/".join(parts[:i]))
    invalidate_storage()
    return {"id": fid, "duplicate": False}


async def import_path(src, folder, stem):
    """Bring a file the player made itself (an ElevenLabs generation, 2.9.0) into library folder `folder` as `stem` + its
    extension, through the same steps as an upload (finish_import). `src` is moved. Returns {"id", "duplicate"} or {"error", "status"}."""
    src = Path(src)
    size = src.stat().st_size
    info = storage_info(True)
    if size > info["allowance"]:
        return {"error": space_error(size, info), "status": 507}
    mkdir_new(LIB / folder)
    dest = unique_in_lib(f"{folder}/{stem}{src.suffix.lower()}" if folder else f"{stem}{src.suffix.lower()}")
    await asyncio.get_running_loop().run_in_executor(None, shutil.move, str(src), str(dest))
    return await finish_import(dest, size, folder)
