"""What the player would hold in RAM for its library: a read-only breakdown, for the NUC, the Pi or any install folder.

    python3 tests/tools/ram_breakdown.py <install folder> [--url http://127.0.0.1:8080]

Reads (never writes) config.json, state.json, playlists.json and durations.json from the install folder, lists media/library, and
prints, per file type: the files, their size on disk, their length, and the size of the decoded audio the player keeps in RAM
(48 kHz, 16-bit, stereo = 192,000 bytes per second, whatever the file is), with the factor decoded / on disk. Then the cache limits:
cache_mb, the machine's RAM (/proc/meminfo MemTotal) and the limit the player uses (the smallest of cache_mb, 25 % of the RAM and the
RAM minus 1 GB). With --url it also asks the running player for its process memory and what the cache holds now (GET /api/state, read only).

Standard library only, and it imports nothing from the player, so it can be run with the system python3 while the player runs.
A file whose length is not in durations.json yet is measured here (WAV header, or ffprobe when it is on the PATH), else counted as unknown.
"""
import argparse, json, os, re, shutil, subprocess, sys, urllib.request, wave
from pathlib import Path

BPS = 48000 * 2 * 2                 # bytes per second of decoded audio in the player (cpl/devices.py: 48000 Hz, 16-bit, stereo)
MIB, GIB = 1048576, 1024 ** 3
SHARE, RESERVE, FLOOR = 0.25, GIB, 64 * MIB     # keep in step with cpl/cache.py (limit_parts)
AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac"}


def read_json(p):
    try:
        text = p.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    try:
        return json.loads(text)
    except ValueError:
        try:
            return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))
        except ValueError:
            return {}


def machine_ram(path="/proc/meminfo"):
    try:
        with open(path) as f:
            mi = {l.split(":")[0]: int(l.split()[1]) * 1024 for l in f if ":" in l and len(l.split()) >= 2}
        return mi.get("MemTotal"), mi.get("MemAvailable")
    except (OSError, ValueError):
        pass
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"), None
    except (ValueError, OSError, AttributeError):
        return None, None


def probe_len(path):
    """Length in seconds when durations.json has none: the WAV header, else ffprobe (if it is on the PATH), else None."""
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path)) as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            pass
    exe = shutil.which("ffprobe")
    if exe:
        try:
            out = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                                 capture_output=True, text=True, timeout=30).stdout.strip()
            return float(out)
        except Exception:
            pass
    return None


def mb(n):
    return "unknown" if n is None else f"{n / MIB:,.0f} MB"


def hms(s):
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", help="the install folder (holds player.py, config.json, media/library)")
    ap.add_argument("--url", help="a running player, e.g. http://127.0.0.1:8080 (read only: GET /api/state)")
    a = ap.parse_args()
    base = Path(a.folder).expanduser().resolve()
    lib = base / "media" / "library"
    if not lib.is_dir():
        sys.exit(f"no media/library in {base}")
    cfg = {"cache_mb": 768}
    cfg.update(read_json(base / "config.json"))
    cfg.update({k: v for k, v in read_json(base / "state.json").items() if k == "cache_mb"})
    durs = {k: v[2] for k, v in read_json(base / "durations.json").items() if isinstance(v, list) and len(v) == 3}
    pls = read_json(base / "playlists.json").get("playlists") or []
    in_pl = {fid for pl in pls if isinstance(pl, dict) for fid in pl.get("tracks") or []}

    rows, unknown = {}, []
    for root, dirs, files in os.walk(lib):
        dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
        for f in files:
            ext = Path(f).suffix.lower()
            if f.startswith(".") or ext not in AUDIO_EXT:
                continue
            full = Path(root) / f
            fid = full.relative_to(lib).as_posix()
            r = rows.setdefault(ext, {"n": 0, "disk": 0, "secs": 0.0, "pl_n": 0, "pl_secs": 0.0, "unknown": 0})
            r["n"] += 1
            r["disk"] += full.stat().st_size
            d = durs.get(fid)
            if d is None:
                d = probe_len(full)
            if d is None:
                r["unknown"] += 1
                unknown.append(fid)
                continue
            r["secs"] += d
            if fid in in_pl:
                r["pl_n"] += 1
                r["pl_secs"] += d

    print(f"Library: {base / 'media' / 'library'}")
    print(f"{'type':6} {'files':>5} {'on disk':>10} {'length':>9} {'decoded':>10} {'factor':>6}   {'in playlists':>12} {'decoded':>10}")
    tot = {"n": 0, "disk": 0, "secs": 0.0, "pl_n": 0, "pl_secs": 0.0}
    for ext in sorted(rows):
        r = rows[ext]
        for k in tot:
            tot[k] += r[k]
        dec = r["secs"] * BPS
        fac = f"{dec / r['disk']:.1f}x" if r["disk"] and r["secs"] else "-"
        print(f"{ext[1:]:6} {r['n']:5} {mb(r['disk']):>10} {hms(r['secs']):>9} {mb(dec):>10} {fac:>6}   {r['pl_n']:12} {mb(r['pl_secs'] * BPS):>10}"
              + (f"   ({r['unknown']} length unknown)" if r["unknown"] else ""))
    dec = tot["secs"] * BPS
    fac = f"{dec / tot['disk']:.1f}x" if tot["disk"] and tot["secs"] else "-"
    print(f"{'total':6} {tot['n']:5} {mb(tot['disk']):>10} {hms(tot['secs']):>9} {mb(dec):>10} {fac:>6}   {tot['pl_n']:12} {mb(tot['pl_secs'] * BPS):>10}")
    print(f"\nDecoded audio: 48 kHz, 16-bit, stereo = {BPS:,} bytes per second ({BPS * 60 / MIB:.1f} MB per minute), whatever the file type.")
    print("Only tracks used by a playlist (or a trigger point) are decoded ahead; other library files are decoded when they are played.")
    if unknown:
        print(f"{len(unknown)} file(s) have no known length; they are not in the decoded figures.")

    total, avail = machine_ram()
    setting = max(64.0, float(cfg.get("cache_mb") or 768)) * MIB
    parts = [("cache_mb setting", setting)]
    if total:
        parts += [("25 % of the RAM", int(total * SHARE)), ("RAM minus 1 GB", total - RESERVE)]
    name, lim = min(parts, key=lambda x: x[1])
    lim = max(FLOOR, lim)
    print(f"\nMachine RAM: {mb(total)}" + (f" (available now {mb(avail)})" if avail else ""))
    print(f"cache_mb: {cfg.get('cache_mb')}  ->  {mb(setting)}")
    for n, v in parts[1:]:
        print(f"{n}: {mb(v)}")
    print(f"Track cache limit (smallest of the above): {mb(lim)}  [set by: {name}]")
    print(f"Warm-up fills up to: {mb(max(0.8 * lim, lim - 512 * MIB))}; playlist audio to decode: {mb(tot['pl_secs'] * BPS)}"
          + ("  -> everything fits" if tot["pl_secs"] * BPS <= max(0.8 * lim, lim - 512 * MIB) else "  -> NOT everything fits: the rest is decoded when played"))

    if a.url:
        try:
            s = json.loads(urllib.request.urlopen(a.url.rstrip("/") + "/api/state", timeout=5).read())
            m = s.get("mem") or {}
            print(f"\nRunning player {s.get('version', '?')}: process {mb(m.get('proc'))}, track cache {mb(m.get('cache'))} of {mb(m.get('cache_budget'))}"
                  f" ({m.get('cache_tracks')} tracks); process minus cache {mb((m.get('proc') or 0) - (m.get('cache') or 0))}")
        except Exception as e:
            print(f"\nCould not read {a.url}/api/state: {e}")


if __name__ == "__main__":
    main()
