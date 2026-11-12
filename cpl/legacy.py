#!/usr/bin/env python3
"""
Cue Media Engine (CueME) - a small library + playlist audio player that Bitfocus Companion can control.
Runs on macOS and Linux (including Raspberry Pi).

Library    : every audio file lives once in media/library/; playlists only reference library tracks
Control in : OSC (UDP, default 9000) and HTTP (default 8080)
State out  : OSC to Companion's built-in OSC listener, as custom variables
Management : web UI at http://localhost:8080
"""
import asyncio, errno, filecmp, ipaddress, json, socket, math, os, random, re, shutil, signal, sys, threading, time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


from cpl.helpers.common import test_dev_dir as _test_dev_dir      # the test-only device hook; one definition, shared with the helper processes


from cpl import clock                                 # the time source (tests install a fake one)
from cpl.dsp import METER_WIN, compute_env, np      # moved to cpl/dsp.py in split step P2


import pygame
from aiohttp import web
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

from cpl.util import (atomic_write, _log_seen, _tasks, log_once, spawn, is_uint, route_int, finite_float, body, fmt, fmt_bytes, _UNITS, _warned, parse_size, _sc)      # moved to cpl/util.py in split step P3
from cpl.config import (APP_VERSION, BASE, LAUNCHER, MEDIA, LIB, DATA, CFG, cfg_file, read_config_file, RESUME, STATE, WARN_DEFAULT, _warn_item, warn_clean, PLAY_MODES, AUDIO_EXT, save_config_keys)      # moved to cpl/config.py in split step P3
from cpl.dsp import DUCK_STEP, duck_key, duck_curve, duck_smooth, lufs_from_pcm      # moved to cpl/dsp.py in split steps P2 / P3
from cpl.state import bump                          # rev += 1, then the on_change hooks (request_warm: lists changed, make sure the tracks around the focus are decoded)
from cpl import state as S                            # the shared state (split step P4); scalars are always S.name, containers may be imported by name
from cpl.state import playlists, FOLDER_COLORS, FOLDER_FLAGS, FOLDER_ICONS, LIBDIRS, library, focus, decks, ISSUES, DEV_MISSING, DURS      # stable containers: never rebound (tests/test_state_identity.py)
from cpl.persist import (save, save_state)      # moved to cpl/persist.py in split step P5/P6
from cpl import cache                                # cache.invalidate_all() / cache.rename_path(): the cache internals are private to the module
from cpl.cache import (_cache_lock, _env, _key, _loading, _tcache, cache_bytes, cache_drop, cache_put, cached, cut_sound, decode_in_child, ensure_loaded, mem_info, resolve_path, trimmed_cached, trimmed_put)      # moved to cpl/cache.py in split step P5/P6
from cpl.devices import (dev_notices, init_mixer, list_capture_devices, list_devices)      # moved to cpl/devices.py in split step P5/P6
from cpl.durations import (_dur_load, _dur_save, durations)      # moved to cpl/durations.py in split step P5/P6
from cpl import durations as durm      # reached as durm.<name> (patched by tests / registered in a hook list)
from cpl.infostore import (INFO, _info_load, info_entry, info_store)      # moved to cpl/infostore.py in split step P5/P6
from cpl.ffmpeg import (CONVERT_EXT, FF, ff_check, ff_convert, ff_loudness, ff_prefix, ff_probe, ff_run, ff_volume, get_wave, needs_normalising)      # moved to cpl/ffmpeg.py in split step P5/P6
from cpl.playlists import (END_ACTIONS, FADE_MAX_MS, FADE_MIN_MS, _bag, _file_len, add_to_playlist, clamp_focus, end_of, fade_default_ms, fade_in_default_ms, fade_in_ms_of, fade_in_start_ms, fade_ms_of, is_loop, move_focus, move_playlist, move_track, next_in_order, pl_mode, dur_eff, shuffle_left, remove_from_playlist, set_end, set_loop, set_play_mode, set_trim, set_xfade, track, trim_of, trim_range, valid, xfade_ms, xfade_of)      # moved to cpl/playlists.py in split step P5/P6
from cpl.library import (_safe_rel, delete_from_library, find_duplicate, invalidate_storage, lib_mkdir, lib_rename, lib_rmdir, missing_refs, mkdir_new, rescan_library, scan_library, storage_info, unique_in_lib)      # moved to cpl/library.py in split step P5/P6
from cpl.triggers_data import (TRIG, _truthy, set_triggers, trig_deck, trigger_json, trigger_target_ok, trigger_targets, triggers_of)      # moved to cpl/triggers_data.py in split step P5/P6
from cpl.loudness import (LOUD, _loud_load, _loud_save, _lufs_of, _scipy_ok, apply_gain_live, norm_cfg, norm_gain, norm_gain_db, set_norm)      # moved to cpl/loudness.py in split step P5/P6
from cpl import loudness      # reached as loudness.<name> (patched by tests / registered in a hook list)
from cpl.formats import (FMT, FMT_STATE, _fmt_load, fmt_kick)      # moved to cpl/formats.py in split step P5/P6
from cpl import warm      # reached as warm.<name> (patched by tests / registered in a hook list)
from cpl.fileinfo import (info_response)      # moved to cpl/fileinfo.py in split step P5/P6
from cpl.upload import (import_file, save_upload, space_error)      # moved to cpl/upload.py in split step P5/P6
from cpl import liveinput as lin      # the Live input (Duck only): lin.LI is the one instance
from cpl import watchdog as wdg      # the audio watchdog (2.8.0): Heartbeat (a silent looped sound) and Watchdog (pure logic)
from cpl import alerts      # push on state change (2.8.0): Notifier (state machine) and Poster (webhook, one worker thread)
from cpl import devwatch      # is the Live output still there, without enumerating devices while audio plays (2.8.0 follow-up)
from cpl import audiodrv      # which audio driver SDL selected, for the health report (2.8.0 follow-up 3)
from cpl import outalias      # labels, groups, hidden and live-only flags for output names (2.8.0 output-alias)
from cpl import health as healthm      # the health model (2.8.0): pure, fed by health_report()
from cpl.boot import (load)      # moved to cpl/boot.py in split step P5/P6

# ---------------------------------------------------------------- web files
STATIC = BASE / "static"             # the web pages (help, stage, variables ...) live here as files, next to player.py


def _static(name):
    """The text of static/<name> (UTF-8). CRLF line endings (a Windows checkout with autocrlf) are turned into LF, so the page and the
    include markers are the same whatever the checkout did; files that already use LF are returned byte for byte."""
    return (STATIC / name).read_bytes().decode("utf-8").replace("\r\n", "\n")


_STATIC_FILES = ("help.html", "stage.html", "variables.html", "index.html", "style.css", "app.js", "icons.js", "tour.js")
_missing = [n for n in _STATIC_FILES if not (STATIC / n).is_file()]
if _missing:
    sys.exit(f"Cue Media Engine: the folder {STATIC} is missing or incomplete (not found: {', '.join(_missing)}).\n"
             "Deploy the static/ folder together with player.py (copy both).")


# ---------------------------------------------------------------- state
# Shared state lives in cpl/state.py (S.<name>; containers imported by name). The ONLY module globals this file still rebinds with `global` are
# these 7 module-private names, each used by one future module only; localise them when that module is split out
# (tests/test_no_bare_state.py, MODULE_PRIVATE, lists them and fails on any other rebound global):
#   (_gen is now private to cpl/cache.py, _dur_busy / _dur_booted to cpl/durations.py: cache.invalidate_all(), durm.status())
#   osc_out     -> cpl/stateout.py     (P8: rebuild_osc())                  _list_keys             -> cpl/stateout.py (P8)
#   _ui_cache   -> cpl/ui_assets.py    (P8)                                 _dl_task               -> cpl/download.py (P8)


def _live_snapshot():
    """Everything needed to carry the live track over to another output without a jump."""
    d = S.live_deck
    if d is not None and d.top and not d.pt and d.under in decks:
        d = d.under                                    # a trigger point's voice-over belongs to no playlist entry: carry on with the track under it
    tr = track(*d.pt) if d and d.pt else None
    if not tr:
        return None
    snd = cached(tr["path"])
    pos = d.fpos()
    return {"pt": list(d.pt), "tr": tr, "pos": max(0.0, pos), "paused": d.paused_at is not None, "vol": d.vol, "trig": trig_carry_of(d),
            "raw": snd.get_raw() if snd is not None else None, "fmt": pygame.mixer.get_init()}


def _live_restore(s):
    """Carry on from the same point on the new output. The decoded audio is handed over from memory, so the only
    gap is the time the new device takes to open. Cue and focus are left where they were."""
    p, t = s["pt"]
    tr = track(p, t)
    if not tr:
        return
    keep = list(focus)
    if s["raw"] and pygame.mixer.get_init() == s["fmt"]:
        snd = pygame.mixer.Sound(buffer=s["raw"])
        cache_put(tr["path"], snd)
        if _start(p, t, tr, snd, 0, offset=s["pos"], paused=s["paused"]) and S.live_deck:
            S.live_deck.set_vol(s["vol"])
            S.live_deck.trig_carry = s.get("trig")
    else:                                                   # the new device runs at another rate: decode again
        S.pending_n += 1
        S.pending = {"token": S.pending_n, "pt": [p, t], "fid": tr["id"], "name": tr["name"], "xfade": 0,
                   "offset": s["pos"], "paused": s["paused"], "trig": s.get("trig")}
        spawn(_start_when_ready(S.pending_n, tr["path"]))
    focus[:] = keep


def set_device(name):
    """Switch the output device (None = system default). The live track carries on from where it was."""
    old = CFG["audio_device"]
    snap = _live_snapshot()
    stop_all()
    cache.invalidate_all()             # _gen += 1 (loads in flight were decoded for the old output: discarded), _loading.clear(), _cache.clear(), _tcache.clear()
    pygame.mixer.quit()
    try:
        init_mixer(name)
        CFG["audio_device"] = name
        DEV_MISSING.pop("output", None)
        ISSUES.pop("audio", None)
        ok = True
    except Exception as e:
        print("could not open output", name, "->", e)
        ok = False
        try:
            init_mixer(old)
        except Exception:
            init_mixer(None)
            CFG["audio_device"] = None
    if snap:
        try:
            _live_restore(snap)
        except Exception as e:
            print("could not carry the live track over to the new output:", e)
    HB.reset()                         # the old channel and sound belong to the closed mixer
    warm.request_warm()
    save_state()
    return ok


# ---------------------------------------------------------------- audio engine
class Deck:
    """One playing track with its own volume, fade and pause state."""

    def __init__(self, pt, name, sound, channel, loop=False, env=None):
        self.env, self._lidx = env, 0
        self.pt, self.name, self.sound, self.channel = pt, name, sound, channel
        self.loop = loop                 # started with loops=-1 (seamless "loop track")
        self.passes = 1                  # 2 when started with loops=1 ("loop once": the track plays twice)
        self.one_pass = False            # "loop once" was switched off in the first pass: end after it
        self.end_at = None               # when loop mode is switched off mid-play: finish the current pass
        self.natural = False             # True when it ended by itself (not stopped / faded out)
        self.duration = sound.get_length()
        self.base = 0.0                  # where in the file this sound begins (the In point, or a resume / seek position)
        self.lo, self.hi = 0.0, None     # the trimmed region of the file (hi None = to the end)
        self.end_fade_ms = 0             # fade out over this long before the Out point (0 = cut / no Out)
        self.fade_in_ms = 0              # fade-in applied when this deck started at its In point (0 = none; web page / tests only)
        self._outfaded = False
        self.started = clock.monotonic()
        self.paused_at = None
        self.vol = 1.0
        self.duck = 1.0                  # Play on Top ducking applied to this background track (1 = none)
        self.duck_in = 1.0               # Live input ducking (cpl.liveinput) applied to this track (1 = none); a separate factor, so the two never overwrite each other
        self.gain = 1.0                  # level match for this playlist (<= 1, only ever turns a track down)
        self.fade = None
        self.kill_on_fade_end = False
        self.path = None                 # file path, so the solo monitor can play the same audio on the preview output
        self.top = False                 # Play on Top: plays over a ducked background and hands back to it when it ends
        self.bg, self.under, self.under_ended, self.superseded = [], None, None, False
        self.trig = None                 # trigger-point bookkeeping (see triggers_tick); created when the deck is first seen live
        self.trig_carry = None           # state handed over from the deck this one replaced (output device change)
        self.seek_n = 0                  # bumped by seek_live, so the trigger logic re-arms
        self.fresh = False               # started from the In point (not resumed part-way in)
        self.fid = None                  # library id of the file, also for a trigger point's track that has no playlist entry

    def elapsed(self):
        return (self.paused_at or clock.monotonic()) - self.started

    def fpos(self):
        """Where the playhead is in the original file (the sound may begin part-way in)."""
        e = self.elapsed()
        if (self.loop or self.passes > 1) and self.duration > 0:
            e %= self.duration
        return self.base + max(0.0, min(e, self.duration))

    def remaining(self):
        """Seconds left of the pass that is playing."""
        e = self.elapsed()
        if (self.loop or self.passes > 1) and self.duration > 0:
            e %= self.duration
        return max(0.0, self.duration - e)

    def pass_idx(self):
        """Which pass is playing, counted from 0 (always 0 for a track that plays once)."""
        if not (self.loop or self.passes > 1) or self.duration <= 0:
            return 0
        i = int(self.elapsed() / self.duration)
        return i if self.loop else min(self.passes - 1, i)

    def pass_no(self):
        """Which pass is playing (1-based; 1 for a track that plays once)."""
        if self.passes < 2 or self.duration <= 0:
            return 1
        return min(self.passes, int(self.elapsed() / self.duration) + 1)

    def level(self):
        """(left, right) peak since the last call, 0..1, including this deck's current fade volume."""
        if self.env is None and self.path:
            self.env = _env.get(self.path)            # worked out after the track started
        if self.env is None or self.paused_at is not None or len(self.env) == 0:
            return 0.0, 0.0
        e = self.fpos()
        idx = min(len(self.env) - 1, max(0, int(e / METER_WIN)))
        seg = self.env[min(self._lidx, idx):idx + 1]
        self._lidx = idx
        g = self.vol * self.gain * self.duck * self.duck_in * CFG["live_volume"]
        return float(seg[:, 0].max()) * g, float(seg[:, 1].max()) * g

    def set_vol(self, v):
        self.vol = max(0.0, min(1.0, v))
        self.apply()

    def apply(self):
        self.channel.set_volume(self.vol * self.gain * self.duck * self.duck_in * CFG["live_volume"])

    def start_fade(self, target, ms, kill=False):
        self.kill_on_fade_end = kill
        if ms <= 0:
            self.fade = None
            self.set_vol(target)
        else:
            self.fade = {"a": self.vol, "b": target, "t0": clock.monotonic(), "len": ms / 1000.0}

    def pause(self):
        if self.paused_at is None:
            self.paused_at = clock.monotonic()
            self.channel.pause()

    def resume(self):
        if self.paused_at is not None:
            gap = clock.monotonic() - self.paused_at
            self.started += gap
            if self.fade:
                self.fade["t0"] += gap
            self.paused_at = None
            self.channel.unpause()

    def stop(self):
        if self.channel.get_sound() is self.sound:
            self.channel.stop()

    def update(self):
        """Advance fades. Returns False when the deck is finished and should be removed."""
        if self.paused_at is not None:
            return True
        if self.fade:
            x = (clock.monotonic() - self.fade["t0"]) / self.fade["len"]
            a, b = self.fade["a"], self.fade["b"]
            if x >= 1:
                self.set_vol(b)
                self.fade = None
                if self.kill_on_fade_end:
                    return False
            else:
                # equal-power curves keep perceived loudness steady through a crossfade
                if b >= a:
                    self.set_vol(a + (b - a) * math.sin(x * math.pi / 2))
                else:
                    self.set_vol(b + (a - b) * math.cos(x * math.pi / 2))
        e = self.elapsed()
        if self.passes > 1 and e < self.duration:         # switched away from "loop once" during the first pass: play that pass out, then end
            self.one_pass = not (self.pt and end_of(*self.pt) == "once")
        total = self.duration * (1 if self.one_pass else self.passes)
        over = e >= total
        if (self.end_fade_ms and not self.loop and not self._outfaded and not self.fade and not self.kill_on_fade_end
                and total - e <= min(self.end_fade_ms / 1000.0, self.duration) and not over):
            self._outfaded = True                         # fade out to the Out point (of the last pass); the track then ends by itself
            self.fade = {"a": self.vol, "b": 0.0, "t0": clock.monotonic(), "len": max(0.05, total - e)}
        if self.loop:
            if self.pt and is_loop(self.pt[0], self.pt[1]):
                over, self.end_at = False, None
            else:                         # mode changed while looping: play out the pass that is running
                if self.end_at is None:
                    self.end_at = (int(e / self.duration) + 1) * self.duration
                over = e >= self.end_at
        if over or self.channel.get_sound() is not self.sound:
            self.natural = not self.kill_on_fade_end
            return False
        return True


def is_paused():
    return bool(S.live_deck and S.live_deck.paused_at is not None)


def is_fading_out():
    return bool(S.live_deck and S.live_deck.fade and S.live_deck.kill_on_fade_end)


_vol_before_mute = [None]


def set_live_volume(v):
    """Master volume of the live output (0..1). Fades and crossfades keep working underneath it."""
    v = finite_float(v)
    if v is None:
        return False
    v = max(0.0, min(1.0, v))
    CFG["live_volume"] = v
    if v > 0:
        _vol_before_mute[0] = None
    for d in decks:
        d.channel.set_volume(d.vol * d.gain * d.duck * d.duck_in * v)
    save_state()
    return True


def seek_live(pos):
    """Jump the live track to `pos` seconds of the file (it keeps its volume, fades and pause state).
    A trimmed track cannot be moved outside its In/Out region."""
    d = S.live_deck
    tr = track(*d.pt) if d and d.pt else None
    snd = cached(tr["path"]) if tr else None
    if snd is None:
        return False
    full = snd.get_length()
    lo, hi, tm = trim_range(d.pt[0], d.pt[1], full)
    pos = finite_float(pos)
    if pos is None:
        return False
    pos = max(lo, min(pos, max(lo, hi - 0.3)))
    new = snd
    if pos > 0.05 or hi < full - 0.01:
        new = cut_sound(snd, pos, hi)
    ch = new.play(loops=0)
    if ch is None:
        return False
    was_paused = d.paused_at is not None
    d.channel.stop()
    d.sound, d.channel, d.loop, d.end_at, d._lidx, d.passes = new, ch, False, None, 0, 1
    d.seek_n += 1                                       # trigger points re-arm from the new position
    d.apply()
    now = clock.monotonic()
    d.base, d.lo, d.hi, d.duration = pos, lo, hi, new.get_length()
    was_out, d.started, d._outfaded = d._outfaded, now, False
    if was_out and d.fade and not d.kill_on_fade_end:
        d.fade = None                                   # the Out fade had begun: moving back means it is no longer ending
        d.set_vol(1.0)
    if was_paused:
        ch.pause()
        d.paused_at = now
    return True


def stop_all():
    S.pending = None                       # a track that was still loading must not start after a stop
    for d in decks:
        d.stop()
    decks.clear()
    S.live_deck = None
    # Nothing is left to duck: forget the depth too. Otherwise the loop keeps releasing it over the release time and a background
    # track started meanwhile would be turned down by the leftover when the next Play on Top arms it (the loop then ends on its next tick).
    DUCK["top"], DUCK["bg"], DUCK["curve"], DUCK["gr"] = None, [], None, 0.0


def pause_all():
    for d in decks:
        d.pause()


def resume_all():
    for d in decks:
        d.resume()


def play(p, t, xfade_ms=0):
    """Make a track live. xfade_ms > 0 fades the current output out while this one fades in.
    If the track isn't decoded yet it is prepared in the background and starts the moment it is ready;
    whatever is playing carries on untouched until then."""
    tr = track(p, t)
    if not tr:
        return False
    snd = cached(tr["path"])
    if snd is not None:
        S.pending = None
        return _start(p, t, tr, snd, xfade_ms)
    if not Path(tr["path"]).exists():
        print("file is missing:", tr["path"])
        return False
    S.pending_n += 1
    S.pending = {"token": S.pending_n, "pt": [p, t], "fid": tr["id"], "name": tr["name"], "xfade": xfade_ms}
    focus[:] = [p, t]
    spawn(_start_when_ready(S.pending_n, tr["path"]))
    return True


DUCK = {"top": None, "bg": [], "curve": None, "origin": 0.0, "gr": 0.0, "task": None}


def duck_arm(deck, snd, bg):
    """Start ducking `bg` for the track `deck` that was just played on top of it."""
    DUCK["top"], DUCK["bg"] = deck, list(bg)
    DUCK["origin"] = deck.base
    DUCK["curve"] = None                              # a fixed dip until the real curve is ready (normally it already is)
    level = float(CFG["top_track_pct"]) / 100.0 * deck.gain
    lo_i = int(deck.base / DUCK_STEP)
    hi_i = int(deck.hi / DUCK_STEP) if deck.hi else None

    def fit(key):                                     # the part of the track that actually plays
        return None if key is None else duck_curve(key[lo_i:hi_i], level, CFG["duck_ratio"], CFG["duck_threshold_db"], CFG["duck_hold"])

    key = _key.get(deck.path)
    if key is not None:
        DUCK["curve"] = fit(key)
    else:                                             # the analysis had not finished: do it off the event loop
        async def late():
            loop = asyncio.get_running_loop()
            try:
                k = await loop.run_in_executor(None, lambda: duck_key(snd.get_raw()))
                if k is None:
                    return
                # snd may be a cut of the file: its first sample is the file position deck.base, so no offset is needed
                if DUCK["top"] is deck:
                    DUCK["curve"] = duck_curve(k, level, CFG["duck_ratio"], CFG["duck_threshold_db"], CFG["duck_hold"])
            except Exception as e:
                log_once("duck", "ducking: could not analyse the top track (a fixed dip is used)", e)
        try:
            spawn(late())
        except RuntimeError:
            pass
    if DUCK["task"] is None or DUCK["task"].done():
        try:
            DUCK["task"] = asyncio.ensure_future(_duck_loop())
        except RuntimeError:
            pass


async def _duck_loop():
    last = clock.monotonic()
    while True:
        await asyncio.sleep(DUCK_STEP)
        now = clock.monotonic()
        dt = max(0.001, min(0.2, now - last))
        last = now
        top = DUCK["top"]
        tgt = 0.0
        if top is not None and top in decks:
            cur = DUCK["curve"]
            if cur is None:                          # no numpy: a fixed dip instead
                lv = max(0.01, min(1.0, float(CFG["top_level_pct"]) / 100.0))
                tgt = -20.0 * math.log10(lv)
            else:
                i = int((top.fpos() - DUCK["origin"]) / DUCK_STEP) + 2     # 20 ms look-ahead: the dip starts just before the word
                tgt = float(cur[i]) if 0 <= i < len(cur) else 0.0
        gr = DUCK["gr"]
        gr = duck_smooth(gr, tgt, dt, CFG["duck_attack_ms"], CFG["duck_release_ms"])
        DUCK["gr"] = gr
        mult = 10.0 ** (-gr / 20.0)
        for b in DUCK["bg"]:
            if b in decks and abs(b.duck - mult) > 0.0005:
                b.duck = mult
                b.apply()
        if gr == 0.0 and (top is None or top not in decks):
            for b in DUCK["bg"]:
                b.duck = 1.0
                if b in decks:
                    b.apply()
            DUCK["top"], DUCK["bg"], DUCK["curve"] = None, [], None
            return


DUCK_LIMITS = {"duck_threshold_db": (-60.0, 0.0), "duck_ratio": (1.0, 20.0), "duck_attack_ms": (1, 200),
               "duck_release_ms": (10, 3000), "top_track_pct": (0, 100)}


DUCK_STEPS = {"duck_threshold_db": 1.0, "duck_ratio": 0.5, "duck_attack_ms": 1, "duck_release_ms": 10, "top_track_pct": 1}


def set_duck(vals):
    """Change ducking settings (keys as in DUCK_LIMITS, plus duck_hold). Applied at once and saved. Returns an error text or None."""
    new = {}
    try:
        for k, v in vals.items():
            if k == "duck_hold":
                new[k] = bool(v) if not isinstance(v, str) else v.strip().lower() in ("1", "true", "on", "yes")
            elif k in DUCK_LIMITS:
                lo, hi = DUCK_LIMITS[k]
                x = float(v)
                if not lo <= x <= hi:
                    return f"{k.replace('duck_', '').replace('_', ' ')} must be between {lo:g} and {hi:g}"
                new[k] = int(round(x)) if isinstance(lo, int) else round(x, 1)
            elif k == "top_fade_ms":
                new[k] = int(max(0, min(30000, float(v))))
    except (TypeError, ValueError):
        return "not a number"
    try:
        save_config_keys(new)
    except Exception as e:
        return f"Could not write config.json: {e}"
    CFG.update(new)
    return None


def play_on_top(p, t):
    """Play this track over whatever is playing, which is turned down while it is loud (threshold / ratio / attack /
    release). When it ends the background comes back up and carries on. With nothing playing it simply plays."""
    tr = track(p, t)
    if not tr:
        return False
    if not decks:
        return play_default(p, t)
    return _play_on_top(p, t, tr)


def _play_on_top(p, t, tr):
    """The Play on Top itself, for the playlist entry (p, t) or, for a trigger point, a library file (p = t = None)."""
    ms = max(0, int(CFG["top_fade_ms"]))
    snd = cached(tr["path"])
    if snd is not None:
        S.pending = None
        return _start(p, t, tr, snd, ms, top=True)
    if not Path(tr["path"]).exists():
        print("file is missing:", tr["path"])
        return False
    S.pending_n += 1
    S.pending = {"token": S.pending_n, "pt": [p, t], "fid": tr["id"], "name": tr["name"], "xfade": ms, "top": True}
    spawn(_start_when_ready(S.pending_n, tr["path"]))
    return True


async def _start_when_ready(token, path):
    try:
        snd = await ensure_loaded(path)
    except Exception as e:
        print("load error:", e)
        S.LAST_LOAD_ERR = (clock.time(), f"could not load a track: {str(e)[:140]}")
        if S.pending and S.pending["token"] == token:
            S.pending = None
        S.notify()
        return
    if not S.pending or S.pending["token"] != token:       # stopped, or another track was triggered meanwhile
        return
    job, S.pending = S.pending, None
    S.LAST_LOAD_ERR = None
    p, t = job["pt"]
    tr = track(p, t)
    if not tr or tr["id"] != job["fid"]:                # the list was edited while loading: find the track again
        ids = playlists[p]["tracks"] if p < len(playlists) else []
        if job["fid"] not in ids:
            S.notify()
            return
        t = ids.index(job["fid"])
        tr = track(p, t)
    if _start(p, t, tr, snd, job["xfade"], job.get("offset", 0.0), job.get("paused", False), job.get("top", False)) and job.get("trig") and S.live_deck:
        S.live_deck.trig_carry = job["trig"]
    S.notify()


def _start(p, t, tr, snd, xfade_ms, offset=0.0, paused=False, top=False):
    play_snd = snd
    full = snd.get_length()
    lo, hi, tm = trim_range(p, t, full)
    start = lo if offset <= 0.05 else max(lo, offset)
    if offset > 0.05 and start >= hi - 0.5:
        return False                                 # it had practically finished
    if start > 0.05 or hi < full - 0.01:             # begin at the In point / resume part-way in / stop at the Out point
        play_snd = trimmed_cached(tr["path"], lo, hi) if offset <= 0.05 else None      # cut ahead of time by the warm-up
        if play_snd is None:
            play_snd = cut_sound(snd, start, hi)
    top = bool(top and decks)
    old_top = [d for d in decks if d.top] if top else []
    if top:                                         # Play on Top: duck what is playing instead of replacing it
        bg = [d for d in decks if not d.top]
        bg = [d for d in bg if not d.kill_on_fade_end]      # ducked by the ducking loop, not faded
        for d in old_top:                           # a second top track replaces the first and keeps the same background
            d.superseded = True
            d.start_fade(0.0, xfade_ms, kill=True)
        if old_top:
            bg, under_keep, ended_keep = old_top[0].bg, old_top[0].under, old_top[0].under_ended
        else:
            under_keep, ended_keep = (S.live_deck if S.live_deck in bg else (bg[-1] if bg else None)), None
    elif xfade_ms > 0 and decks:
        resume_all()
        for d in decks:
            d.start_fade(0.0, xfade_ms, kill=True)
    else:
        stop_all()
    fresh = abs(start - lo) < 0.06                    # a resumed pass ends, then the loop restarts from the In point
    loop = is_loop(p, t) and fresh
    once = end_of(p, t) == "once" and fresh and not top        # a track on top is measured for ducking once, so it never repeats
    ch = play_snd.play(loops=-1 if loop else (1 if once else 0))
    if ch is None:
        print("no free mixer channel")
        return False
    deck = Deck([p, t] if p is not None else None, tr["name"], play_snd, ch, loop, _env.get(tr["path"]))     # a trigger point plays a library file that belongs to no playlist entry: pt None
    deck.base, deck.lo, deck.hi = start, lo, hi
    deck.fresh = fresh
    deck.fid = tr["id"]
    deck.passes = 2 if once else 1
    if tm.get("out") is not None and tm.get("end", "fade") == "fade" and hi < full - 0.01:
        deck.end_fade_ms = fade_ms_of(p, t)
    deck.gain = norm_gain(p, t)
    deck.path = tr["path"]
    fin = 0                                         # fade-in at A: only on a start at the In point (never a seek or resume part-way in), never while paused;
    if offset <= 0.05 and not paused and not (xfade_ms > 0 and not top):      # a crossfade into the track already fades it in and wins
        fin = fade_in_start_ms(p, t)
        if fin:
            fin = int(min(fin, (hi - start) * 1000 - deck.end_fade_ms)) if (hi - start) * 1000 - deck.end_fade_ms >= FADE_MIN_MS else int(min(fin, (hi - start) * 1000))
    deck.fade_in_ms = max(0, fin)
    if top:
        deck.top, deck.bg, deck.under, deck.under_ended = True, bg, under_keep, ended_keep
    if top:                                         # a track played on top starts at its set level, no fade-in; only the background ducks
        level = max(0.0, min(1.0, float(CFG["top_track_pct"]) / 100.0))
        deck.set_vol(0.0 if deck.fade_in_ms else level)
        if deck.fade_in_ms:
            deck.start_fade(level, deck.fade_in_ms)     # the top deck fades up to its set level; the background ducks at full depth meanwhile (accepted in 2.7.4)
        duck_arm(deck, play_snd, bg)
    elif xfade_ms > 0:
        deck.set_vol(0.0)
        deck.start_fade(1.0, xfade_ms)
    elif deck.fade_in_ms:
        deck.set_vol(0.0)
        deck.start_fade(1.0, deck.fade_in_ms)
    else:
        deck.set_vol(1.0)
    decks.append(deck)
    S.live_deck = deck
    if not top:
        focus[:] = [p, t]                           # a track played on top leaves the cue where it was
    if paused:
        deck.pause()
    return True


def play_default(p, t, ms=None):
    if CFG["default_transition"] == "crossfade":
        return play(p, t, xfade_ms(p, t, ms))
    return play(p, t)


def fade_out(ms=None):
    S.pending = None
    ms = CFG["fadeout_ms"] if ms is None else ms
    if not decks:
        return
    if is_paused() or ms <= 0:
        stop_all()
        return
    for d in decks:
        d.start_fade(0.0, ms, kill=True)


def toggle(p, t, ms=None):
    if S.live_deck and S.live_deck.pt == [p, t] and not is_fading_out():
        fade_out(CFG["toggle_off_fade_ms"] if ms is None else ms)
    else:
        play_default(p, t, ms)


def play_playlist(p, ms=None):
    """/<p>/play: start playlist p from its first playable track (shuffle: a random one) as if Go were pressed on it."""
    n = len(playlists[p]["tracks"]) if 0 <= p < len(playlists) else 0
    if not n:
        return False
    order = next_in_order(p, n) if pl_mode(p) == "shuffle" else list(range(n))
    for i in order:
        tr = track(p, i)
        if tr and (cached(tr["path"]) is not None or Path(tr["path"]).exists()):
            play_default(p, i, ms)
            warm.request_warm()
            S.notify()
            return True
    return False


def auto_advance(deck):
    """The live track ended by itself: carry on according to the play mode."""
    if not deck.pt:
        return
    p, t = deck.pt
    if end_of(p, t) == "stop":                     # this track ends the run, whatever the playlist behavior is
        return
    if pl_mode(p) == "next_playlist":              # play on to the end of this playlist, then start the next one
        order = [(p, i) for i in range(t + 1, len(playlists[p]["tracks"]))]
        for q in range(p + 1, len(playlists)):
            order += [(q, i) for i in range(len(playlists[q]["tracks"]))]
        for q, i in order:
            if valid(q, i) and play(q, i):
                break
    else:
        for i in next_in_order(p, t):
            if valid(p, i) and play(p, i):
                break
    warm.request_warm()
    S.notify()


_rs = {"t": 0.0, "key": None}


def save_resume(force=False):
    """Remember what is live (and where) so a restart can carry on. Written every resume_save_s seconds while
    playing, and removed as soon as nothing is playing, so a deliberate stop is never undone by a restart."""
    if not CFG["resume_on_start"]:
        return
    d = S.live_deck
    if d is not None and d.top and d.under in decks:
        d = d.under                                  # resume the background track, not the announcement on top
    if d is None or not d.pt or is_fading_out():
        if S.pending and not force:
            return                                   # a track is loading: keep the previous record
        _rs["key"] = None
        if not force:
            try:
                RESUME.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
        return
    tr = track(*d.pt)
    if not tr:
        return
    key = (tr["id"], d.paused_at is not None)
    now = clock.monotonic()
    if not force and key == _rs["key"] and now - _rs["t"] < max(1.0, float(CFG["resume_save_s"])):
        return
    pos = d.fpos()
    try:
        atomic_write(RESUME, json.dumps({"pt": d.pt, "id": tr["id"], "pos": round(pos, 2), "paused": key[1], "saved": clock.time()}))
        _rs["key"], _rs["t"] = key, now
    except Exception as e:
        log_once("resume.json", "could not save resume.json (a restart will not carry on)", e)


def try_resume():
    """At start-up: carry on with the track that was playing when the player last stopped."""
    if not CFG["resume_on_start"] or not RESUME.exists():
        return
    try:
        d = json.loads(RESUME.read_text())
        age = clock.time() - float(d["saved"])
        fid, pos, paused = d["id"], float(d["pos"]), bool(d.get("paused"))
        if age > float(CFG["resume_max_age_s"]):
            print(f"Not resuming: it was last playing {int(age)} s ago (limit resume_max_age_s = {CFG['resume_max_age_s']})")
            RESUME.unlink()
            return
        p, t = d["pt"]
        if not (valid(p, t) and playlists[p]["tracks"][t] == fid):          # the lists were edited: find the track again
            hits = [(i, k) for i, pl in enumerate(playlists) for k, x in enumerate(pl["tracks"]) if x == fid]
            if not hits:
                RESUME.unlink()
                return
            p, t = next((h for h in hits if h[0] == p), hits[0])
        tr = track(p, t)
        if not tr or not Path(tr["path"]).exists():
            return
        S.pending_n += 1
        S.pending = {"token": S.pending_n, "pt": [p, t], "fid": fid, "name": tr["name"], "xfade": 0,
                   "offset": max(0.0, pos), "paused": paused}
        focus[:] = [p, t]
        spawn(_start_when_ready(S.pending_n, tr["path"]))
        print(f"Resuming \"{tr['name']}\" at {int(pos) // 60:02d}:{int(pos) % 60:02d}" + (" (paused)" if paused else ""))
    except Exception as e:
        print("could not resume:", e)


METER = {"live": [-90.0, -90.0], "preview": [-90.0, -90.0]}     # smoothed levels in dBFS
METER_PUB = {f"{k}_{n}_{x}": v for k in ("live", "preview") for x in ("l", "r")
             for n, v in (("level", "0"), ("meter", "░" * 8), ("fader", "0"), ("db", "-inf"))}   # what is sent to Companion (rate limited)
_meter_t = {"last": clock.monotonic(), "pub": 0.0}
METER_FLOOR, METER_DECAY = 60.0, 30.0                           # legacy 0-100 variables use -60..0 dBFS; the meters fall 30 dB per second
BAR = 8
# Console-fader taper of every level meter: dBFS -> % of the meter height from the bottom, linear between stops, 0 % at -90 dBFS ("-inf").
# 0 dBFS is the top and nothing is boosted. The JS table, the scale labels and the colour zones of the page are generated from this.
METER_STOPS = ((0, 100), (-5, 88), (-10, 76), (-20, 60), (-30, 46), (-40, 33), (-50, 21), (-60, 10), (-90, 0))
METER_TICKS = (0, 5, 10, 20, 30, 40, 50, 60, None)            # labelled stops in dB below full scale (None = -inf): the one list for the Live and the Preview meter
METER_AMBER_DB, METER_RED_DB = -17.0, -6.0                     # colour zones (the same dB thresholds as before)


def to_db(x):
    return 20 * math.log10(x) if x > 1e-5 else -90.0


def pct_of(db):
    """Meter position, 0-100, for a level in dBFS (the console taper above)."""
    if db >= 0:
        return 100.0
    for (d1, p1), (d2, p2) in zip(METER_STOPS, METER_STOPS[1:]):
        if db >= d2:
            return p2 + (p1 - p2) * (db - d2) / (d1 - d2)
    return 0.0


def pct_lin(db):
    """The old linear -60..0 dBFS scale (kept for the legacy *_level_* variables)."""
    return max(0.0, min(100.0, (db + METER_FLOOR) / METER_FLOOR * 100))


def db_text(db):
    return "-inf" if db <= -90.0 else f"{db:.1f}"


def update_meters():
    now = clock.monotonic()
    dt, _meter_t["last"] = now - _meter_t["last"], now
    ll = lr = 0.0
    for d in decks:
        l, r = d.level()
        ll, lr = ll + l * l, lr + r * r
    ps = preview.status
    pl, pr = (ps.get("l", 0.0), ps.get("r", 0.0)) if preview.enabled() and ps.get("state") == "playing" else (0.0, 0.0)
    if S.MONITOR and preview.enabled():                  # Solo live: the preview output carries the live audio at the preview volume
        pl, pr = math.sqrt(ll) * CFG["preview_volume"], math.sqrt(lr) * CFG["preview_volume"]
    for key, vals in (("live", (math.sqrt(ll), math.sqrt(lr))), ("preview", (pl, pr))):
        for i, x in enumerate(vals):
            db, cur = to_db(x), METER[key][i]
            METER[key][i] = db if db >= cur else max(db, cur - METER_DECAY * dt)
    rate = float(CFG["meter_rate_hz"] or 0)
    if rate > 0 and now >= _meter_t["pub"]:
        _meter_t["pub"] = now + 1.0 / rate
        for key in METER:
            for i, side in enumerate(("l", "r")):
                db = METER[key][i]
                fp = int(round(pct_of(db)))
                k = round(fp / 100 * BAR)
                METER_PUB[f"{key}_level_{side}"] = str(int(round(pct_lin(db))))      # legacy, linear -60..0
                METER_PUB[f"{key}_fader_{side}"] = str(fp)
                METER_PUB[f"{key}_db_{side}"] = db_text(db)
                METER_PUB[f"{key}_meter_{side}"] = "█" * k + "░" * (BAR - k)


def meters_json():
    out = {"enabled": np is not None, "gr": round(DUCK["gr"], 1), "in_gr": round(lin.LI.gr, 1) if lin.LI.alive else 0.0,
           "input": {"present": bool(lin.LI.alive), "signal": lin.LI.signal(), "level_db": round(lin.LI.level_db, 1) if lin.LI.alive else None,
                     "levels_db": [round(v, 1) for v in lin.LI.levels_db] if lin.LI.alive else None, "stereo": len(lin.LI.channels()) == 2}}
    for key in METER:
        l, r = METER[key]
        out[key] = {"l": round(pct_of(l), 1), "r": round(pct_of(r), 1), "l_db": round(l, 1), "r_db": round(r, 1)}
    return out


# ---------------------------------------------------------------- trigger points: engine
# Runs inside tick() (50 ms) for the live track and only compares numbers: crossing the trigger time is found from the
# file position (Deck.fpos, which includes trim and loop passes), nothing is decoded or copied here. Each Deck keeps
# `trig`: {seek_n, pass, pbase, last, fired, due, skipped, warm_t}.
#   fired   ids already handled in this pass (fired, skipped or not eligible), so they are armed again on a new pass or a seek back
#   due     ids whose time has come but whose target is still loading: {id: monotonic time it became due}
#   skipped ids the operator skipped ahead of time
TRIG_WAIT_S = 30.0                       # a target that is still not loaded this long after its time is given up on
_trig_load_err = {}                      # target path -> why loading it failed


def trig_notice(kind, text):
    """Remember what the trigger logic did, for the page (state.trigger_notice) and the log."""
    TRIG["seq"] += 1
    TRIG["notice"] = {"seq": TRIG["seq"], "kind": kind, "text": text, "t": clock.time()}
    print(f"trigger {kind}: {text}", flush=True)


# (stays in legacy until transport exists: split-plan F4; trig_deck and trigger_targets are in cpl/triggers_data.py)
def trig_carry_of(d):
    """What a new Deck needs to carry on the trigger bookkeeping of `d` (output device change)."""
    st = d.trig
    if st is None:
        return None
    return {"fired": set(st["fired"]), "due": list(st["due"]), "skipped": set(st["skipped"]), "pbase": st["pbase"] + st["pass"]}


def _trig_init(d):
    trs = triggers_of(*d.pt)
    pos = d.fpos()
    st = {"seek_n": d.seek_n, "pass": d.pass_idx(), "pbase": 0, "last": pos, "fired": set(), "due": {}, "skipped": set(), "warm_t": clock.monotonic()}
    carry = d.trig_carry
    if d.fresh and not carry and d.seek_n == 0:
        st["last"] = d.lo - 1e-3                          # a trigger at the very start (or the In point) still fires
    else:                                                 # resumed part-way in: everything before here is behind us
        st["fired"] = {x["id"] for x in trs if x["at"] <= pos}
    if carry:
        now = clock.monotonic()
        st["pbase"], st["skipped"] = carry["pbase"], set(carry["skipped"])
        st["fired"] = (st["fired"] - set(carry["due"])) | set(carry["fired"])
        st["due"] = {i: now for i in carry["due"]}
    d.trig_carry = None
    warm.request_warm()                                        # the targets are decoded before the trigger time comes
    return st


def _trig_eligible(d, tg):
    """Enabled, and inside the part of the file that this deck plays (a trigger before the In point or at/after the Out never fires)."""
    return bool(tg.get("enabled", True)) and tg["at"] >= d.lo - 1e-6 and (not d.hi or tg["at"] < d.hi - 1e-6)


def _trig_cross(d, st, a, b, trs, now):
    """Triggers whose time lies in (a, b] have been reached."""
    for tg in trs:
        i = tg["id"]
        if i in st["fired"] or i in st["due"] or not a < tg["at"] <= b:
            continue
        st["fired"].add(i)
        if not _trig_eligible(d, tg):
            continue
        if tg.get("once") and st["pbase"] + st["pass"] > 0:
            continue                                      # "first pass only"
        st["due"][i] = now


def _trig_load(path):
    """Start decoding a trigger target that is not in the cache (once)."""
    if path in _loading:
        return
    async def go():
        try:
            await ensure_loaded(path)
            _trig_load_err.pop(path, None)
        except Exception as e:
            _trig_load_err[path] = str(e)[:100]
    try:
        spawn(go())
    except RuntimeError:
        _trig_load_err[path] = "no event loop"


def _trig_fire_due(d, st, trs, now):
    """Fire (or give up on) the triggers that are due. A target that is not decoded yet is waited for, a few ticks at most."""
    by_id = {x["id"]: x for x in trs}
    for i in sorted(st["due"], key=lambda k: by_id[k]["at"] if k in by_id else 0):
        tg = by_id.get(i)
        since = st["due"][i]
        if tg is None or not tg.get("enabled", True):
            del st["due"][i]                              # deleted or switched off while waiting
            continue
        name = Path(tg["file"]).stem
        path = str(LIB / tg["file"])
        top_busy = any(x.top for x in decks)
        if i in st["skipped"]:
            st["skipped"].discard(i)
            trig_notice("skipped", f"{name} (skipped by the operator)")
        elif not CFG["triggers_armed"]:
            trig_notice("skipped", f"{name} (Auto triggers are off)")
        elif not top_busy and d is not S.live_deck:
            print(f"trigger {name}: not fired, the track it belongs to is no longer live", flush=True)   # a crossfade moved on
        elif not trigger_target_ok(tg["file"]):
            trig_notice("failed", f"{name} is missing from the library")
        elif top_busy:
            trig_notice("skipped", f"{name} (a Play on Top is already running)")
        elif cached(path) is None:
            if path in _trig_load_err or now - since > TRIG_WAIT_S:
                trig_notice("failed", f"{name} could not be loaded ({_trig_load_err.pop(path, 'timed out')})")
            else:
                _trig_load(path)
                continue                                  # try again next tick
        else:
            late = now - since
            if _play_on_top(None, None, {"id": tg["file"], "name": name, "path": path}):
                trig_notice("fired", name)
                if late > 0.1:
                    print(f"trigger {name}: fired {late:.2f} s late (the track was still loading)", flush=True)
            else:
                trig_notice("failed", f"{name} could not be started")
        del st["due"][i]


def triggers_tick():
    """Called every tick: find the trigger points the live track has reached and fire them."""
    d = trig_deck()
    if d is None or d.kill_on_fade_end:
        return
    trs = triggers_of(*d.pt)
    if d.trig is None:
        d.trig = _trig_init(d)
    st = d.trig
    now = clock.monotonic()
    if d.paused_at is not None:
        return                                            # pause holds: nothing crosses, nothing fires
    pos = d.fpos()
    if st["seek_n"] != d.seek_n:                          # jumped: what is ahead is armed, what is behind is done
        st["pbase"] += st["pass"]
        st["pass"], st["seek_n"], st["last"], st["due"] = d.pass_idx(), d.seek_n, pos, {}
        st["fired"] = {x["id"] for x in trs if x["at"] <= pos}
        warm.request_warm()
    elif d.pass_idx() != st["pass"]:                      # a loop wrapped: finish the old pass, start the new one from the In point
        _trig_cross(d, st, st["last"], d.base + d.duration, trs, now)
        st["pass"], st["last"], st["fired"] = d.pass_idx(), d.lo - 1e-3, set()
    _trig_cross(d, st, st["last"], pos, trs, now)
    st["last"] = pos
    if st["due"]:
        _trig_fire_due(d, st, trs, now)
    elif now - st["warm_t"] >= 1.0:                       # keep the next target decoded even if the cache was trimmed meanwhile
        st["warm_t"] = now
        nxt = next_trigger(d)
        if nxt and nxt["in_seconds"] < 30 and not nxt["missing"] and cached(str(LIB / nxt["file"])) is None:
            warm.request_warm()


def next_trigger(d=None):
    """The trigger that will fire next on the watched track: {id, file, target, in_seconds, at, missing, pass}, or None."""
    d = d or trig_deck()
    if d is None or d.trig is None or d.pt is None:
        return None
    st, pos = d.trig, d.fpos()
    trs = [x for x in triggers_of(*d.pt) if _trig_eligible(d, x) and x["id"] not in st["skipped"]]
    for tg in trs:
        if tg["id"] in st["due"]:
            return _nt_json(tg, 0.0, 0)
    for tg in trs:
        if tg["id"] not in st["fired"] and tg["at"] > pos - 1e-6 and not (tg.get("once") and st["pbase"] + st["pass"] > 0):
            return _nt_json(tg, tg["at"] - pos, 0)
    more = d.loop or (d.passes > 1 and not d.one_pass and st["pass"] + 1 < d.passes)
    if more:                                              # nothing left in this pass: the first one of the next pass
        for tg in trs:
            if not tg.get("once"):
                return _nt_json(tg, (d.base + d.duration - pos) + (tg["at"] - d.lo), 1)
    return None


def _nt_json(tg, secs, nxt_pass):
    return {"id": tg["id"], "file": tg["file"], "target": Path(tg["file"]).stem, "at": tg["at"], "in_seconds": round(max(0.0, secs), 2),
            "missing": not trigger_target_ok(tg["file"]), "next_pass": bool(nxt_pass)}


def skip_next_trigger():
    """Skip the trigger that is coming next on the live track (once). Returns it, or None when nothing is coming."""
    d = trig_deck()
    nt = next_trigger(d)
    if nt is None:
        return None
    d.trig["skipped"].add(nt["id"])
    return nt


def set_triggers_armed(on):
    save_config_keys({"triggers_armed": bool(on)})
    CFG["triggers_armed"] = bool(on)
    return bool(on)


def live_triggers_json():
    """The watched track's trigger points that can still matter, for the live waveform: {fid, items: [{n, at, fired}]}.
    `fired` = already dealt with in this pass (fired, skipped or passed), so the page greys it."""
    d = trig_deck()
    if d is None or d.trig is None:
        return None
    st = d.trig
    items = [{"n": n + 1, "at": tg["at"], "fired": tg["id"] in st["fired"] or tg["id"] in st["due"], "skipped": tg["id"] in st["skipped"]}
             for n, tg in enumerate(triggers_of(*d.pt)) if _trig_eligible(d, tg)]
    return {"fid": d.fid, "items": items}


def triggers_json():
    """State of the trigger feature for the page: the switch, what is coming and the last notice (shown for a few seconds)."""
    nt = next_trigger()
    n = TRIG["notice"]
    return {"triggers_armed": bool(CFG["triggers_armed"]), "next_trigger": nt, "live_triggers": live_triggers_json(),
            "trigger_notice": n if n and clock.time() - n["t"] < 10 else None}


def tick():
    ended = None
    tops_done = []
    for d in list(decks):
        if not d.update():
            if d.top:
                tops_done.append(d)
            elif d is S.live_deck and d.natural:
                ended = d
            elif d.natural:                      # a background track that finished underneath a Play on Top
                over = next((x for x in decks if x.top), None)
                if over and d is over.under:
                    over.under_ended = d
            d.stop()
            decks.remove(d)
    for d in tops_done:                          # the track played on top finished: bring the background back
        if d.superseded:
            continue
        alive = [b for b in d.bg if b in decks and not b.kill_on_fade_end]      # they come back up through the ducking loop
        if d is S.live_deck and d.natural:
            if d.under in alive:
                S.live_deck = d.under
            elif alive:
                S.live_deck = alive[-1]
            elif d.under_ended and not S.pending:
                ended = d.under_ended             # the background ended while it was covered: carry on from there
    if S.live_deck not in decks:
        S.live_deck = None
    if ended and not S.pending:
        auto_advance(ended)
    try:
        triggers_tick()
    except Exception as e:                       # a trigger problem must never stop fades and auto-advance
        log_once("triggers", "trigger points: error in the tick", e)
    monitor_sync()
    try:
        if CFG["watchdog"] and _wd_playing():
            HB.poll()                            # a few microseconds: one get_busy() call, and a silent play() every half second
        WD.poll()
    except Exception as e:                       # the watchdog must never stop fades and auto-advance
        log_once("watchdog", "watchdog: error in the tick", e)
    lin.LI.watchdog()                            # a Live input detector that has not run for 250 ms must not leave the music ducked
    update_meters()
    save_resume()


# ---------------------------------------------------------------- preview output
class Preview:
    """Talks to the preview worker process (a separate mixer on a second output device)."""
    KEY = "preview_device"                       # the config key that holds this output's device name
    MIRROR = False                               # a mirror always plays the live audio, like Solo live that is never switched off

    def __init__(self):
        self.proc, self.queue, self.spawning = None, [], False
        self.status = {"state": "stopped", "pos": 0.0, "dur": 0.0, "error": ""}
        self.name, self.fid = "-", None
        self.muted = False                       # Mute of this output (the preview output only: never the live decks, ducking or the Live meters); kept while the player runs

    def enabled(self):
        return bool(CFG[self.KEY])

    def info(self):
        st = dict(self.status)
        if self.proc is None and not self.spawning and st["state"] != "error":
            st["state"] = "stopped"
        return {"device": CFG["preview_device"], "name": self.name if st["state"] != "stopped" else self.name,
                "fid": self.fid, "volume": CFG["preview_volume"], **st, "solo": S.MONITOR, "muted": self.muted}

    def send(self, obj):
        if not self.enabled():
            return False
        if self.proc is None or self.proc.returncode is not None:
            self.queue.append(obj)
            if not self.spawning:
                self.spawning = True
                spawn(self._spawn())
            return True
        self._write(obj)
        return True

    def _write(self, obj):
        try:
            self.proc.stdin.write((json.dumps(obj) + "\n").encode())
        except Exception as e:
            print("preview:", e)

    async def _spawn(self):
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(LAUNCHER), "--preview", CFG[self.KEY],
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
        except Exception as e:
            self.spawning, self.queue = False, []
            self.status = {"state": "error", "pos": 0.0, "dur": 0.0, "error": f"could not start the output: {e}"}
            return
        self.proc, self.spawning = proc, False
        self.status = {"state": "stopped", "pos": 0.0, "dur": 0.0, "error": ""}
        spawn(self._read(proc))
        self._write({"cmd": "vol", "v": CFG["preview_volume"]})
        if self.muted:
            self._write({"cmd": "mute", "on": True})
        if S.MONITOR or self.MIRROR:
            self._write({"cmd": "solo", "on": True})
        if not self.MIRROR and lin.LI.solo:
            self._write(input_solo_msg())
        for o in self.queue:
            self._write(o)
        self.queue = []

    async def _read(self, proc):
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            try:
                st = json.loads(line)
            except Exception as e:
                log_once("pvread", "preview/mirror worker sent an unreadable line", e)
                continue
            if proc is self.proc:
                self.status = st
        if proc is self.proc:                                  # the worker exited
            self.proc = None
            if self.status.get("state") != "error":
                self.status = {"state": "error", "pos": 0.0, "dur": 0.0, "error": ("mirror" if self.MIRROR else "preview") + " output stopped"}

    def play_file(self, path, name, start=0.0, fid=None):
        self.name, self.fid = name, fid
        if not Path(path).exists():
            self.status = {"state": "error", "pos": 0.0, "dur": 0.0, "error": "file is missing"}
            return False
        self.status = {"state": "loading", "pos": 0.0, "dur": 0.0, "error": ""}     # until the worker reports
        return self.send({"cmd": "play", "path": path, "start": start})

    def play_pt(self, p, t):
        tr = track(p, t)
        return bool(tr) and self.play_file(tr["path"], tr["name"], fid=tr["id"])

    def play_id(self, fid):
        if fid not in library:
            return False
        return self.play_file(str(LIB / fid), Path(fid).stem, fid=fid)

    def toggle_pt(self, p, t):
        """Start previewing that track, or stop if it is the one already previewing (playing, paused or loading)."""
        tr = track(p, t)
        if not tr:
            return False
        if self.fid == tr["id"] and self.status["state"] in ("playing", "paused", "loading"):
            return self.send({"cmd": "stop"})
        return self.play_pt(p, t)

    def set_volume(self, v):
        CFG["preview_volume"] = max(0.0, min(1.0, float(v)))
        save_state()
        self.send({"cmd": "vol", "v": CFG["preview_volume"]})

    def set_mute(self, on):
        """Mute or unmute this output only (the worker keeps its volume, so unmuting brings the same level back)."""
        self.muted = bool(on)
        self.send({"cmd": "mute", "on": self.muted})

    def set_device(self, name):
        """Choose the preview output (None = off). The worker restarts on the new device."""
        old = self.proc
        self.proc, self.queue = None, []
        if old and old.returncode is None:
            try:
                old.stdin.write(b'{"cmd":"quit"}\n')
                old.stdin.close()
            except Exception:
                pass
        CFG[self.KEY] = name
        self.name = "-"
        self.status = {"state": "stopped", "pos": 0.0, "dur": 0.0, "error": ""}
        save_state()
        if name:
            self.send({"cmd": "stop"})                         # starts the worker now, so a bad device shows up at once


class Mirror(Preview):
    """A second output that plays a copy of whatever is live (same worker as the preview, with the live monitor always on)."""
    KEY = "mirror_device"
    MIRROR = True

    def enabled(self):
        return bool(CFG["mirror_enabled"] and CFG["mirror_device"])

    def apply(self):
        """Start, restart or stop the worker to match the current switch and device."""
        old = self.proc
        self.proc, self.queue = None, []
        if old and old.returncode is None:
            try:
                old.stdin.write(b'{"cmd":"quit"}\n')
                old.stdin.close()
            except Exception:
                pass
        self.status = {"state": "stopped", "pos": 0.0, "dur": 0.0, "error": ""}
        _mon["sig"] = None
        if self.enabled():
            self.send({"cmd": "stop"})


preview = Preview()
mirror = Mirror()


def input_solo_msg():
    """What the preview worker needs to tap the Live input (its own read pointer on the shared ring; the preview bus only)."""
    return {"cmd": "inmon", "on": bool(lin.LI.solo and lin.LI.ring_path), "ring": lin.LI.ring_path, "gain_db": float(CFG["input_gain_db"])}


def input_solo_sync():
    if preview.enabled() and (lin.LI.solo or preview.proc is not None):
        preview.send(input_solo_msg())


lin.LI.on_solo = input_solo_sync

_mon = {"t": 0.0, "sig": None, "full": 0.0}


def monitor_set(on):
    S.MONITOR = bool(on)
    _mon["sig"] = None
    preview.send({"cmd": "solo", "on": S.MONITOR})


def monitor_decks():
    """The live decks that are audible: id, file, position and the level they are heard at (fades, ducking, level match and live volume included)."""
    ds = []
    for d in decks:
        if d.paused_at is not None or not d.path:
            continue
        v = d.vol * d.gain * d.duck * d.duck_in * CFG["live_volume"]
        if v < 0.001:
            continue
        ds.append({"id": id(d), "path": d.path, "pos": round(d.fpos(), 3), "vol": round(v, 4)})
    ds.sort(key=lambda x: -x["vol"])
    return ds


def monitor_sync():
    """Tell the outputs that play a copy of the live audio (Solo live on the preview output, and the mirror output)
    which live decks are audible, where they are and how loud."""
    targets = [t for t in ((preview if S.MONITOR else None), mirror) if t and t.enabled() and t.proc is not None]
    if not targets:
        return
    now = clock.monotonic()
    if now - _mon["t"] < 0.1:
        return
    _mon["t"] = now
    ds = monitor_decks()
    sig = tuple((x["id"], x["vol"]) for x in ds[:3])
    if sig == _mon["sig"] and now - _mon["full"] < 0.5:
        return
    _mon["sig"], _mon["full"] = sig, now
    for t in targets:
        t.send({"cmd": "mon", "decks": ds[:3]})


# ---------------------------------------------------------------- state out
class OscOut:
    """The one sender of variables (and of the Settings test message) to Companion. It never looks a host name up on the event loop and not when it is
    made, so an address that does not resolve (offline, an mDNS name, Companion not up yet) can be saved and the player still starts and ticks.
    A host name is resolved in a background thread; the answer is kept REFRESH_S (a changed IP is noticed) and a failed lookup is never kept: it is
    tried again after RETRY_S. While there is no address, send_message raises socket.gaierror (Host not found) at once. An IP address needs no lookup."""
    RETRY_S = 2.0
    REFRESH_S = 60.0

    def __init__(self, host, port):
        self.host, self.port = host, port
        self._ip, self._client, self._busy, self._thread = None, None, False, None
        self._at = self._tried = -1e9
        self.found = None                     # None = no lookup finished yet, False = the last lookup failed, True = it resolved
        try:
            ipaddress.ip_address(host)
            self._literal, self._ip, self.found = True, host, True
        except ValueError:
            self._literal = False

    def _look(self):
        try:
            return socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_DGRAM)[0][4][0]
        except (OSError, IndexError):
            return None

    def _apply(self, ip):
        self._tried = clock.monotonic()
        if ip != self._ip:
            self._ip, self._client = ip, None
        self.found = ip is not None

    def _bg(self):
        try:
            self._apply(self._look())
        finally:
            self._busy = False

    async def refresh(self):
        """Look the name up now (off the loop, at most 3 s); True when it was found. Used by Save and Send test."""
        if self._literal:
            return True
        try:
            ip = await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(None, self._look), 3.0)
        except asyncio.TimeoutError:
            ip = None
        self._apply(ip)
        self._at = clock.monotonic()
        return ip is not None

    def send_message(self, address, value):
        now = clock.monotonic()
        if not self._literal and not self._busy and (now - self._tried >= self.RETRY_S if self._ip is None else now - self._at > self.REFRESH_S):
            self._busy, self._at = True, now
            self._thread = threading.Thread(target=self._bg, daemon=True)
            self._thread.start()
            if self.found is None:
                self._thread.join(0.3)        # the very first lookup: usually done within a few ms
        ip, c = self._ip, self._client            # local copies: push() can run on the loop thread and on worker threads (S.notify), and the
        if ip is None:                            # lookup thread may reset self._ip / self._client at any moment
            raise socket.gaierror(socket.EAI_NONAME, "Host not found")
        if c is None:
            c = self._client = SimpleUDPClient(ip, self.port)
        try:
            c.send_message(address, value)
        except OSError:
            if self._client is c:
                self._client = None
            raise


osc_out = OscOut(CFG["companion_host"], CFG["companion_osc_port"])
_osc = {"down": False}                       # push() could not send. A dict item, not a `global` (the state gate allows no rebinding of a module name): an item
                                               # assignment is atomic under the GIL and the flag only decides two log lines, so threads racing on it can at worst repeat or skip one line; it says so once, and once when it works again


last_sent = {}


def health():
    """('starting' | 'ready' | 'error', text) for the status light in the page header."""
    iss = dict(ISSUES)
    if pygame.mixer.get_init() is None:
        iss["audio"] = "the audio output is not open"
    if not LIB.is_dir():
        iss["library"] = "the library folder is missing"
    if S.LAST_LOAD_ERR and clock.time() - S.LAST_LOAD_ERR[0] < 120:
        iss["load"] = S.LAST_LOAD_ERR[1]
    if iss:
        return "error", "; ".join(iss.values())
    dur_busy, dur_booted = durm.status()       # the two flags written by the duration worker thread (cpl/durations.py)
    if not S.boot_done or dur_busy or not dur_booted:
        return "starting", "Starting: checking the library..."
    return "ready", "Ready"


# ---------------------------------------------------------------- health panel (2.8.0)
def _wd_playing():
    """Something should be producing sound: a deck that is not paused (a fade or a crossfade is a deck too)."""
    return any(d.paused_at is None for d in decks)


def _wd_restart():
    """Close and reopen the output exactly as a device change does (the live track carries on from where it was). Never the service or the process."""
    set_device(CFG["audio_device"])


def _wd_can_restart():
    """No restart while the configured Live output is missing (the player is on the system default or SDL's dummy output): that is the Live output check's problem, not a stall."""
    if DEV_MISSING.get("output"):
        return False
    rep = _hrep["v"]
    return not (rep and any(c["id"] == "live_output" and c["status"] == "bad" for c in rep["checks"]))


HB = wdg.Heartbeat(pygame.mixer)
WD = wdg.Watchdog(lambda: HB.beats, _wd_playing, _wd_restart, enabled=lambda: bool(CFG["watchdog"]), log=lambda m: print(m, flush=True),
                  on_restart=lambda: ALERT.watchdog_restarted(wdg.STALL_S), can_restart=_wd_can_restart)


PLAYER_NAME_MAX = 40                          # characters of the name used in push messages and the report (Settings > System > Health and alerts)


def _push_sanitize():
    """A saved state.json or config.json with a wrong push value must not stop the player: repair it."""
    CFG["player_name"] = " ".join(str(CFG.get("player_name") or "").split())[:PLAYER_NAME_MAX]
    CFG["push_enabled"] = CFG.get("push_enabled") is True
    CFG["push_hold"] = CFG.get("push_hold") is True
    try:
        CFG["push_url"] = alerts.clean_url(CFG.get("push_url"))
    except ValueError:
        CFG["push_url"] = ""
    try:
        CFG["push_events"] = alerts.clean_events(CFG.get("push_events"))
    except ValueError:
        CFG["push_events"] = alerts.clean_events(None)


_push_sanitize()
POSTER = alerts.Poster(lambda: CFG["push_url"], log=lambda m: print(m, flush=True))
ALERT = alerts.Notifier(CFG, lambda: player_name(), lambda: any(d.paused_at is None for d in decks), POSTER, log=lambda m: print(m, flush=True))
_STARTED = clock.monotonic()                  # uptime of the player
COMP = {"last": None, "hdr": False}                         # when the Companion module last asked for /api/state (clock.monotonic()); None = never since the player started
_hdisk = {"v": None, "t": -1e9, "busy": False}   # the media drive's free space, read in a thread and kept 30 s
DW = devwatch.DevWatch(list_devices, devwatch.CardWatch(log=lambda m: print(m, flush=True)))      # the output device names (idle only, in a thread) and the /proc/asound/cards probe (while playing)
AUDRV = audiodrv.Driver()                     # SDL's selected audio driver, read once a device is open (the report's "Audio driver:" line)
_hrep = {"t": -1e9, "v": None}                # the finished report, kept 1 s (the page polls once a second, the module four times)


def is_companion_poll(req):
    """True when /api/state was asked for by the Companion module: the 2.8 module sends the header X-CompanionPlayer-Client, older ones are
    Node's fetch (user agent "node"). A browser (Mozilla ...), curl and the test client are not counted."""
    if req.headers.get("X-CompanionPlayer-Client"):
        COMP["hdr"] = True                                   # a 2.8 module exists: from now on only the header counts (another Node client, like n8n, must not look like Companion)
        return True
    if COMP["hdr"]:
        return False
    ua = req.headers.get("User-Agent", "")
    return ua == "node" or ua.startswith("undici")


def _disk_read():
    try:
        env = os.environ.get("CP_TEST_DISK_FREE_GB")                    # test hook, inert unless set: "<free GB>[,<total GB>]"
        if env:
            parts = [float(x) for x in env.split(",")]
            tot = os.environ.get("CP_TEST_DISK_TOTAL_GB")               # optional; without it (and without a second number) the drive's real total is kept
            if tot:
                total = int(float(tot) * 1024 ** 3)
            elif len(parts) > 1:
                total = int(parts[1] * 1024 ** 3)
            else:
                total = shutil.disk_usage(MEDIA).total
            v = {"free": int(parts[0] * 1024 ** 3), "total": total}
        else:
            du = shutil.disk_usage(MEDIA)
            v = {"free": du.free, "total": du.total}
    except Exception:
        v = None
    _hdisk["v"], _hdisk["t"], _hdisk["busy"] = v, clock.monotonic(), False


def disk_reading():
    """The cached free-space reading; a stale one starts a thread that refreshes it (never a disk call on the event loop)."""
    if clock.monotonic() - _hdisk["t"] > 30 and not _hdisk["busy"]:
        _hdisk["busy"] = True
        if _hdisk["v"] is None:
            _disk_read()                                               # the first reading: one statvfs call, the page waits for no thread
        else:
            threading.Thread(target=_disk_read, daemon=True).start()
    return _hdisk["v"]


def player_name():
    return (str(CFG.get("player_name") or "").strip() or socket.gethostname().split(".")[0] or "Cue Media Engine")[:60]


def health_report(force=False):
    """The health model (cpl/health.py) fed with the current facts. Cheap: nothing here touches the audio device or the disk."""
    now = clock.monotonic()
    if not force and _hrep["v"] is not None and now - _hrep["t"] < 1.0:
        return _hrep["v"]
    hs, ht = health()
    playing = bool(decks)                                       # a track, a fade or a crossfade (paused or not): the stream is running, so no device enumeration at all
    DW.refresh(playing)                                         # idle only, in a thread, never waited for
    want = CFG["audio_device"] or DEV_MISSING.get("output")
    live = {"name": want or "system default", "shown": outalias.shown(want) if want else "system default", "present": (not DEV_MISSING.get("output")) and DW.live_present(want, playing), "open": pygame.mixer.get_init() is not None}
    pv = CFG["preview_device"]
    ri = warm.ram_info()
    last = COMP["last"]
    inp = {"starting": hs == "starting",
           "live": live,
           "preview": {"configured": bool(pv), "name": pv, "shown": outalias.shown(pv) if pv else pv, "present": (not pv) or DW.device_present(pv), "amber": bool(CFG["health_preview_amber"])},
           "engine": {"stalled": WD.stalled, "gave_up": WD.gave_up, "restarts": WD.total},
           "companion": {"polled": last is not None, "silent_s": 0 if last is None else now - last, "host_found": getattr(osc_out, "found", None)},
           "disk": disk_reading(),
           "cache": {"measured": bool(ri and ri.get("tracks_total")), "full": bool(ri and ri.get("full")), "failing": bool(S.LAST_LOAD_ERR and clock.time() - S.LAST_LOAD_ERR[0] < 120)},
           "uptime_s": max(0.0, now - _STARTED),
           "issues": ht if hs == "error" else ""}
    rep = healthm.compact(healthm.evaluate(inp))
    _hrep["t"], _hrep["v"] = now, rep
    return rep


def snapshot():
    ft = None if S.cue_cleared else track(*focus)
    if not S.live_deck:
        state = "loading" if S.pending else "stopped"
    elif is_paused():
        state = "paused"
    elif is_fading_out():
        state = "fading"
    else:
        state = "playing"
    si = storage_info()
    return {
        "focus_id": "-" if S.cue_cleared else f"{focus[0]}/{focus[1]}",
        "focus_name": ft["name"] if ft else "-",
        "focus_playlist": playlists[focus[0]]["name"] if focus[0] < len(playlists) else "-",
        "focus_playlist_num": str(focus[0]) if focus[0] < len(playlists) else "-",
        "focus_is_live": "1" if S.live_deck and not S.cue_cleared and S.live_deck.pt == focus else "0",
        "live_id": f"{S.live_deck.pt[0]}/{S.live_deck.pt[1]}" if S.live_deck and S.live_deck.pt else "-",
        "live_name": S.live_deck.name if S.live_deck else "-",
        "remaining": fmt(S.live_deck.remaining()) if S.live_deck else "--:--",
        "state": state,
        "play_mode": pl_mode(focus[0]),          # mode of the focused playlist
        "go_transition": CFG["go_transition"],
        "preview_volume": str(round(CFG["preview_volume"] * 100)),
        "status": health()[0],
        "player_version": APP_VERSION,
        "on_top": "1" if S.live_deck and S.live_deck.top else "0",
        "duck_gr": str(round(DUCK["gr"])),
        "duck_threshold": f"{float(CFG['duck_threshold_db']):.1f}",
        "duck_ratio": f"{float(CFG['duck_ratio']):g}",
        "duck_attack": str(int(CFG["duck_attack_ms"])),
        "duck_release": str(int(CFG["duck_release_ms"])),
        "duck_hold": "1" if CFG["duck_hold"] else "0",
        "top_level": str(int(CFG["top_track_pct"])),
        "input_armed": "1" if CFG["input_armed"] else "0",
        "input_duck_now": "1" if lin.LI.duck_now else "0",
        "input_signal": "1" if lin.LI.signal() else "0",
        "input_ducking": "1" if lin.LI.ducking() else "0",
        "live_gain_db": f"{20 * math.log10(S.live_deck.gain):.1f}" if S.live_deck and S.live_deck.gain < 1 else "0",
        "loading": S.pending["name"] if S.pending else "-",
        "live_volume": str(round(CFG["live_volume"] * 100)),
        "preview_state": preview.status["state"] if preview.enabled() else "off",
        "preview_solo": "1" if S.MONITOR and preview.enabled() else "0",
        "preview_playing": "1" if preview.enabled() and preview.status["state"] in ("playing", "loading") else "0",
        "preview_remaining": fmt(preview.status["dur"] - preview.status["pos"])
        if preview.enabled() and preview.status["state"] in ("playing", "paused") else "--:--",
        **METER_PUB,
        "preview_name": preview.name if preview.enabled() and preview.status["state"] in ("playing", "paused", "loading") else "-",
        "output": CFG["audio_device"] or "System default",
        "storage_free": fmt_bytes(si["disk_free"]),
        "storage_library": fmt_bytes(si["used"]) + (f" / {fmt_bytes(si['cap'])}" if si["cap"] else ""),
    }


_list_keys = set()


def list_vars():
    """Playlist and track names as variables: pl<N>_name, pl<N>_count, pl<N>_t<K>. With the focused playlist number
    (focus_playlist_num) Companion can build the variable name it wants, e.g. $(custom:<prefix>pl$(custom:<prefix>focus_playlist_num)_t0)."""
    out = {}
    for i, pl in enumerate(playlists):
        out[f"pl{i}_name"] = pl["name"]
        out[f"pl{i}_count"] = str(len(pl["tracks"]))
        for k in range(len(pl["tracks"])):
            tr = track(i, k)
            out[f"pl{i}_t{k}"] = tr["name"] if tr else "-"
    n = len(playlists[focus[0]]["tracks"]) if focus[0] < len(playlists) else 0
    out["focus_count"] = str(n)                              # a fixed window onto the focused playlist: 32 slots, "-" when unused
    for k in range(32):
        tr = track(focus[0], k) if k < n else None
        out[f"focus_t{k}"] = tr["name"] if tr else "-"
    return out


def push(force=False):
    global _list_keys
    lv = list_vars()
    allv = {**snapshot(), **lv}
    for k in _list_keys - set(lv):                          # a playlist or track was removed: blank its variable once
        allv[k] = "-"
    _list_keys = set(lv)
    try:
        for k, v in allv.items():
            if force or last_sent.get(k) != v:
                osc_out.send_message(f"/custom-variable/{CFG['var_prefix']}{k}/value", v)
                last_sent[k] = v                # only after it was sent: what failed is sent again when the address works
    except OSError as e:                         # host not found, network unreachable ...: never stop the player for it
        _osc["down"] = True
        log_once("osc-out", f"Can't send variables to Companion at {CFG['companion_host']}:{CFG['companion_osc_port']} ({osc_error_text(e)}); trying again")
        return
    if _osc["down"]:
        _osc["down"] = False
        print(f"Sending variables to Companion at {CFG['companion_host']}:{CFG['companion_osc_port']} again", flush=True)


S.notify = push                            # callers below stateout (transport, loudness) call S.notify() (split step P4, F6)


# ---------------------------------------------------------------- command handling
def command(parts, ms=None):
    """parts like ['0','1'] | ['0','1','xfade'] | ['next'] | ['pause'] ...
    ms optionally overrides the fade/crossfade time for this one command."""
    if len(parts) >= 2 and is_uint(parts[0]) and is_uint(parts[1]):
        p, t = int(parts[0]), int(parts[1])
        if not valid(p, t):
            return "invalid"
        action = parts[2] if len(parts) > 2 else "play"
        if action == "play":
            play_default(p, t, ms)
        elif action == "loop":                      # /<p>/<t>/loop  toggles, /<p>/<t>/loop/1 on, /<p>/<t>/loop/0 off
            arg = parts[3].lower() if len(parts) > 3 else None
            if not set_loop(p, t, None if arg is None else arg in ("1", "on", "true")):
                return "invalid"
        elif action == "end" and (len(parts) < 4 or parts[3].lower() in END_ACTIONS + ("next",)):
            if not set_end(p, t, parts[3].lower() if len(parts) > 3 else None):      # /<p>/<t>/end[/default|once|loop|stop] (no value: next in the cycle)
                return "invalid"
        elif action in ("in", "out", "end", "trim"):   # /<p>/<t>/in/<sec> /out/<sec> /end/fade|cut /trim/clear (/in/clear removes one point)
            arg = parts[3].lower() if len(parts) > 3 else ""
            if action == "trim":
                ok = arg in ("clear", "reset", "off") and set_trim(p, t, {"in": None, "out": None, "end": None})
            elif action == "end":
                ok = set_trim(p, t, {"end": arg}) if arg in ("fade", "cut") else False
            elif arg in ("clear", "reset", "off"):
                ok = set_trim(p, t, {action: None})
            else:
                try:
                    ok = set_trim(p, t, {action: float(arg)})
                except ValueError:
                    ok = False
            if not ok:
                return "invalid"
        elif action in ("xftime", "xfadetime"):          # /<p>/<t>/xftime/<seconds> sets this track's own crossfade time, /xftime/clear returns it to the master time
            arg = parts[3].lower() if len(parts) > 3 else ""
            if not set_xfade(p, t, None if arg in ("clear", "reset", "off", "master") else arg):
                return "invalid"
        elif action in ("xfade", "crossfade"):
            play(p, t, xfade_ms(p, t, ms))
        elif action in ("top", "ontop"):
            play_on_top(p, t)
        elif action == "cut":
            play(p, t)
        elif action == "toggle":
            toggle(p, t, ms)
        elif action in ("focus", "cue"):
            S.cue_cleared = False
            focus[:] = [p, t]
        else:
            return "unknown"
    else:
        a = parts[0] if parts else ""
        if len(parts) == 2 and is_uint(parts[0]) and parts[1] == "play":      # /<playlist>/play: first track (random when shuffling)
            if not play_playlist(int(parts[0]), ms):
                return "invalid"
        elif len(parts) >= 3 and is_uint(parts[0]) and parts[1] == "mode":      # /<playlist>/mode/<x>
            if not set_play_mode(int(parts[0]), parts[2]):
                return "invalid"
        elif len(parts) >= 3 and is_uint(parts[0]) and parts[1] == "norm":    # /<p>/norm/off | track[/<k>] | lufs[/<value>]
            pi, sub = int(parts[0]), parts[2].lower()
            arg = parts[3] if len(parts) > 3 else None
            if sub in ("off", "none"):
                ok = set_norm(pi, mode="off")
            elif sub in ("track", "match"):
                ok = set_norm(pi, mode="track", ref=int(arg) if arg and is_uint(arg) else None)
            elif sub in ("lufs", "fixed"):
                ok = set_norm(pi, mode="lufs", lufs=arg)
            elif sub == "ref" and arg and is_uint(arg):
                ok = set_norm(pi, ref=int(arg))
            else:
                ok = False
            if not ok:
                return "invalid"
        elif a == "loop":                     # /loop toggles looping of the focused track, /loop/1 on, /loop/0 off
            arg = parts[1].lower() if len(parts) > 1 else None
            if not set_loop(focus[0], focus[1], None if arg is None else arg in ("1", "on", "true")):
                return "invalid"
        elif a in ("clear", "clearcue"):      # nothing is cued; take / xfade / cut / toggle do nothing until a cue is picked
            S.cue_cleared = True
        elif a == "next":
            S.cue_cleared = False
            move_focus(1)
        elif a in ("prev", "previous"):
            S.cue_cleared = False
            move_focus(-1)
        elif a == "nextlist":
            S.cue_cleared = False
            move_playlist(1)
        elif a == "prevlist":
            S.cue_cleared = False
            move_playlist(-1)
        elif a in ("take", "xfade", "crossfade", "cut", "toggle", "top", "ontop") and S.cue_cleared:
            return "no cue"
        elif a in ("top", "ontop"):               # /top: duck the live audio and play the cue over it
            play_on_top(*focus)
        elif a == "take":
            play_default(*focus, ms)
        elif a in ("xfade", "crossfade"):
            play(*focus, xfade_ms(*focus, ms))
        elif a == "cut":
            play(*focus)
        elif a == "toggle":
            toggle(*focus, ms)
        elif a == "duck":              # /duck/threshold/-30  /duck/ratio/6  /duck/attack/10  /duck/release/500  /duck/hold/1  /duck/level/100
            #                                 /duck/<what>/inc  /duck/<what>/dec  (optionally /inc/<step>): for rotary knobs;  /duck/hold toggles
            what = parts[1].lower() if len(parts) > 1 else ""
            key = {"threshold": "duck_threshold_db", "ratio": "duck_ratio", "attack": "duck_attack_ms", "release": "duck_release_ms",
                   "hold": "duck_hold", "level": "top_track_pct"}.get(what)
            if not key:
                return "invalid"
            arg = parts[2].lower() if len(parts) > 2 else ""
            if key == "duck_hold":
                val = (not CFG["duck_hold"]) if arg == "" else arg
            elif arg in ("inc", "dec", "up", "down"):
                step = finite_float(parts[3]) if len(parts) > 3 else DUCK_STEPS[key]
                if step is None:
                    return "invalid"
                lo, hi = DUCK_LIMITS[key]
                val = max(lo, min(hi, float(CFG[key]) + (step if arg in ("inc", "up") else -step)))
            else:
                val = arg
            if val == "" or set_duck({key: val}):
                return "invalid"
            push()
        elif a == "input":             # /input/armed/<on|off|toggle>  /input/ducknow/<on|off|toggle>: the Live input (Duck only)
            err = input_command(parts)
            if err:
                return err
        elif a == "go_transition":     # /go_transition/cut | crossfade | toggle: what the web page's Go button does (Take and Crossfade commands are unchanged)
            v = parts[1].lower() if len(parts) > 1 else "toggle"
            if v == "toggle":
                v = "crossfade" if CFG["go_transition"] == "cut" else "cut"
            if v not in ("cut", "crossfade"):
                return "invalid"
            CFG["go_transition"] = v
            save_state()
            push()
        elif a == "mode":              # /mode/stop | track | playlist | shuffle | next (cycles): focused playlist
            if not set_play_mode(focus[0], parts[1] if len(parts) > 1 else ""):
                return "invalid"
        elif a == "preview":           # /preview/<p>/<t> | /preview/focus | /preview/stop | pause | resume | playpause
            sub = parts[1:]
            if not preview.enabled():
                return "no preview output"
            if len(sub) >= 2 and is_uint(sub[0]) and is_uint(sub[1]):
                if not valid(int(sub[0]), int(sub[1])) or not preview.play_pt(int(sub[0]), int(sub[1])):
                    return "invalid"
            elif sub in (["focus"], ["cue"]):                     # toggle: previews the focused track, or stops if it is already on
                if not S.cue_cleared:
                    preview.toggle_pt(*focus)
            elif sub == ["stop"]:
                preview.send({"cmd": "stop"})
            elif sub and sub[0] == "volume":                       # /preview/volume/<0-100> | up[/n] | down[/n]: the preview output's level (with Solo live, what you hear)
                arg, cur = (sub[1].lower() if len(sub) > 1 else ""), round(CFG["preview_volume"] * 100)
                step = finite_float(sub[2]) if len(sub) > 2 else 5.0
                v = cur + step if step is not None and arg == "up" else cur - step if step is not None and arg == "down" else finite_float(arg)
                if v is None or step is None:
                    return "invalid"
                preview.set_volume(max(0.0, min(100.0, v)) / 100.0)
            elif sub == ["pause"]:
                preview.send({"cmd": "pause"})
            elif sub == ["resume"]:
                preview.send({"cmd": "resume"})
            elif sub == ["playpause"]:
                preview.send({"cmd": "resume" if preview.status["state"] == "paused" else "pause"})
            else:
                return "unknown"
        elif a in ("solo", "monitor"):  # /solo (toggle) | /solo/1 | /solo/0: hear the live audio on the preview output
            if not preview.enabled():
                return "no preview output"
            arg = parts[1] if len(parts) > 1 else ""
            monitor_set(not S.MONITOR if arg == "" else arg in ("1", "on"))
        elif a in ("volume", "vol"):   # /volume/80 | /volume/up[/5] | /volume/down[/5] | /volume/mute (toggle)
            arg = parts[1] if len(parts) > 1 else ""
            step = int(parts[2]) if len(parts) > 2 and is_uint(parts[2]) else 5
            cur = round(CFG["live_volume"] * 100)
            if is_uint(arg):
                ok = set_live_volume(min(100, int(arg)) / 100)
            elif arg == "up":
                ok = set_live_volume(min(100, cur + step) / 100)
            elif arg == "down":
                ok = set_live_volume(max(0, cur - step) / 100)
            elif arg == "mute":
                if CFG["live_volume"] > 0:
                    keep = CFG["live_volume"]
                    ok = set_live_volume(0)
                    _vol_before_mute[0] = keep
                else:
                    ok = set_live_volume(_vol_before_mute[0] or 1.0)
            else:
                ok = False
            if not ok:
                return "invalid"
        elif a == "seek":              # /seek/<seconds>: jump the live track
            ok = seek_live(parts[1]) if len(parts) > 1 else False       # seek_live refuses anything that is not a finite number
            if not ok:
                return "invalid"
        elif a == "pause":
            pause_all()
        elif a == "resume":
            resume_all()
        elif a == "playpause":
            resume_all() if is_paused() else pause_all()
        elif a == "fadeout":
            fade_out(ms)
        elif a == "stop":
            stop_all()
        elif a == "stopall":           # stop the live audio and the preview, and clear the cue
            stop_all()
            preview.send({"cmd": "stop"})
            S.cue_cleared = True
        elif a == "resend":            # push every variable to Companion again
            push(True)
        elif a == "rescan":            # re-read media/library (files added/removed offline)
            rescan_library()
            push(True)
        elif a == "device":            # /device/0 (index in device list) | /device/next | /device/default
            names = list_devices()
            arg = parts[1] if len(parts) > 1 else ""
            if arg == "default":
                target = None
            elif arg == "next":
                opts = [None] + [n for n in names if not outalias.lookup(n) or not outalias.lookup(n)["hidden"]]     # a hidden output (the far end of a loopback) is never reached by cycling
                cur = CFG["audio_device"]
                target = opts[(opts.index(cur) + 1) % len(opts)] if cur in opts else None
            elif is_uint(arg) and int(arg) < len(names):
                target = names[int(arg)]
            else:
                return "invalid"
            if not set_device(target):
                return "failed"
        else:
            return "unknown"
    warm.request_warm()
    push()
    return "ok"


def osc_default(address, *args):
    parts = [x for x in address.split("/") if x]
    ms = int(args[0]) if args and isinstance(args[0], (int, float)) and not isinstance(args[0], bool) and math.isfinite(args[0]) else None
    print("OSC", address, args, "->", command(parts, ms))


# ---------------------------------------------------------------- web page


# ---------------------------------------------------------------- variables page
VAR_INFO = {
    "focus_id": "Cued track as playlist/track, e.g. 0/1 (- when the cue is cleared)",
    "focus_name": "Name of the focused track (what Next / Prev moved to)",
    "focus_playlist": "Name of the focused playlist",
    "focus_playlist_num": "Number of the focused playlist (0, 1, 2 ...), the same number used in /<playlist>/<track> commands",
    "focus_is_live": "1 if the focused track is the live one, else 0",
    "live_id": "Live track as playlist/track, or - when nothing plays",
    "live_name": "Name of the live track",
    "remaining": "Time left on the live track (mm:ss)",
    "state": "playing / paused / fading / loading / stopped",
    "live_gain_db": "Level match applied to the live track in dB (0 = none, negative = turned down)",
    "on_top": "1 while a track is playing on top of a ducked background (Play on Top), else 0",
    "duck_gr": "How far the background is turned down by Play on Top right now, in dB (0 when not ducking)",
    "duck_threshold": "Play on Top ducking threshold in dB (the background is turned down while the top track is louder)",
    "duck_ratio": "Play on Top ducking ratio (the number before :1)",
    "duck_attack": "Play on Top ducking attack in ms",
    "duck_release": "Play on Top ducking release in ms",
    "duck_hold": "1 when the background stays ducked until the top track ends, else 0",
    "top_level": "Level of the track played on top, in percent",
    "input_armed": "1 when the Live input is armed (speech on the input ducks the playlist audio), else 0 (/input/armed/on, off, toggle)",
    "input_duck_now": "1 while Duck now is on (a manual override that holds the playlist audio down, with or without an input), else 0 (/input/ducknow/on, off, toggle)",
    "input_signal": "1 while the Live input has signal (above -60 dBFS within the last half second), else 0 (also 0 with no input)",
    "input_ducking": "1 while the Live input is ducking the playlist audio (from speech or Duck now), else 0",
    "player_version": "Version of the player program (e.g. 2.7.0). The Companion module warns when its major.minor differs",
    "status": "Player health: starting (still checking the library) / ready / error",
    "play_mode": "End-of-track mode of the focused playlist: stop / loop_playlist / next_playlist / shuffle (what a single track does at its end is /<p>/<t>/end/<default|once|loop|stop>)",
    "loading": "Name of the live track being prepared (decoded) before it starts, or -. Preview has its own: preview_state = loading",
    "preview_volume": "Volume of the preview output, 0-100 (/preview/volume/<0-100>, /preview/volume/up, /preview/volume/down). While Solo live is on this is the level you hear",
    "go_transition": "What the web page's Go button does: cut or crossfade (/go_transition/cut, /crossfade, /toggle). Companion's Take and Crossfade are not affected",
    "live_volume": "Master volume of the live output, 0-100 (/volume/<0-100>, /volume/up, /volume/down, /volume/mute)",
    "preview_state": "Preview output: off / stopped / loading / playing / paused / error",
    "preview_solo": "1 while the live audio is soloed on the preview output (/solo), else 0",
    "preview_playing": "1 while a preview is playing (or starting), else 0",
    "preview_remaining": "Time left on the previewed track (mm:ss), or --:--",
    "preview_name": "Track being previewed, or -",
    "live_level_l": "LEGACY: live output level, left, 0-100 on a linear -60..0 dBFS scale; sent at meter_rate_hz (use live_fader_l)",
    "live_level_r": "LEGACY: live output level, right, 0-100 on a linear -60..0 dBFS scale",
    "live_fader_l": "Live output level, left, 0-100 on the console-fader taper (0 dBFS = 100, -10 = 76, -20 = 60, -40 = 33, -60 = 10, -inf = 0); sent at meter_rate_hz",
    "live_fader_r": "Live output level, right, 0-100 on the console-fader taper",
    "live_db_l": "Live output level, left, in dBFS as text with one decimal (-inf when silent)",
    "live_db_r": "Live output level, right, in dBFS as text with one decimal (-inf when silent)",
    "live_meter_l": "Live level, left, as a text bar (follows the console-fader taper)",
    "live_meter_r": "Live level, right, as a text bar",
    "preview_level_l": "LEGACY: preview output level, left, 0-100 on a linear -60..0 dBFS scale (use preview_fader_l)",
    "preview_level_r": "LEGACY: preview output level, right, 0-100 on a linear -60..0 dBFS scale",
    "preview_fader_l": "Preview output level, left, 0-100 on the console-fader taper",
    "preview_fader_r": "Preview output level, right, 0-100 on the console-fader taper",
    "preview_db_l": "Preview output level, left, in dBFS as text with one decimal (-inf when silent)",
    "preview_db_r": "Preview output level, right, in dBFS as text with one decimal (-inf when silent)",
    "preview_meter_l": "Preview level, left, as a text bar (follows the console-fader taper)",
    "preview_meter_r": "Preview level, right, as a text bar",
    "output": "Name of the main output device",
    "storage_free": "Free disk space",
    "storage_library": "Library size (and the cap, when one is set)",
}

VARS_PAGE = _static("variables.html")


# the meter taper, scale labels and colour zones are written into the page from the one table above
def meter_label(d):
    """The text of one scale label: 0 unsigned, a true minus sign (U+2212, the width of a plus sign) before every other number, and the minus and the infinity sign for the bottom."""
    return "\u2212\u221e" if d is None else "0" if d == 0 else f"\u2212{d}"


def _scale(ticks):
    return "".join(f'<b style="bottom:{pct_of(-(d if d is not None else 90)):.1f}%">{meter_label(d).replace(chr(0x221e), '<span class=inf>' + chr(0x221e) + '</span>')}</b>' for d in ticks)


def _include(text, marker, piece):
    """Put `piece` where `marker` stands in `text` (the marker must occur exactly once)."""
    assert text.count(marker) == 1, f"static: marker {marker!r} must occur exactly once"
    return text.replace(marker, piece)


def build_ui():
    """The main page, assembled from static/index.html + style.css + app.js (with icons.js and tour.js included at their markers)
    as ONE document, with the four generated pieces (meter table, the scale, two colour stops) written in."""
    app = _include(_static("app.js"), "//@include icons.js\n", _static("icons.js"))
    app = _include(app, "//@include tour.js\n", _static("tour.js"))
    page = _include(_static("index.html"), "<!--@include style.css-->", _static("style.css"))
    page = _include(page, "<!--@include app.js-->", app)
    page = (page.replace("/*MST*/[]", json.dumps([list(x) for x in METER_STOPS])).replace("@@SCL@@", _scale(METER_TICKS))
            .replace("@@AMB@@", f"{pct_of(METER_AMBER_DB):.1f}").replace("@@RED@@", f"{pct_of(METER_RED_DB):.1f}"))
    assert "@@" not in page, "a @@ placeholder is left in the page"
    assert "@include" not in page, "an include marker is left in the page"
    return page


UI_DEV = bool(os.environ.get("CP_DEV_UI"))      # development: read static/ again on every request of /
_ui_cache = None


def ui_page():
    """The main page: assembled once and kept in memory; with CP_DEV_UI=1 it is rebuilt from the files on every request."""
    global _ui_cache
    if UI_DEV:
        return build_ui()
    if _ui_cache is None:
        _ui_cache = build_ui()
    return _ui_cache


ui_page()           # fail at start-up, not on the first visit, if a file or placeholder is wrong


# ---------------------------------------------------------------- web handlers
STAGE_PAGE = _static("stage.html")


HELP_PAGE = _static("help.html")


async def h_stage(req):
    """The stage page: big time remaining for embedding (FreeShow stage layouts, an iframe, any browser). No frame or
    CSP headers are sent on purpose, so it can be embedded from another machine."""
    v = req.match_info.get("v")
    if v not in (None, "a", "b", "c"):
        raise web.HTTPNotFound()
    return web.Response(text=STAGE_PAGE, content_type="text/html", charset="utf-8", headers={"Cache-Control": "no-cache"})


async def h_help_page(_):
    return web.Response(text=HELP_PAGE, content_type="text/html")


async def h_restart(_):
    """Restart the player in place: remember the position, then re-run this same program (same PID, so systemd
    keeps supervising it and no sudo is needed). The page waits for it to come back."""
    async def go():
        await asyncio.sleep(0.4)             # let this HTTP reply reach the browser first
        try:
            save_resume(True)
            save()
            _dur_save()
            if preview.proc:
                preview.proc.kill()
            pygame.mixer.quit()
        except Exception as e:
            print("restart: cleanup problem:", e)
        print("Restarting on request from the web page...", flush=True)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    spawn(go())
    return web.json_response({"ok": True})


async def h_vars_page(_):
    return web.Response(text=VARS_PAGE, content_type="text/html")


async def h_vars(_):
    snap = snapshot()
    return web.json_response({"prefix": CFG["var_prefix"],
                              "target": f"{CFG['companion_host']}:{CFG['companion_osc_port']}",
                              "vars": [{"name": k, "value": str(v), "info": VAR_INFO.get(k, "")} for k, v in snap.items()]
                              + [{"name": k, "value": str(v), "info": ("Name of track %s in the focused playlist (- when unused)" % k[7:] if k.startswith("focus_t") else "Number of tracks in the focused playlist" if k == "focus_count" else "Playlist name" if k.endswith("_name") else "Number of tracks in the playlist" if k.endswith("_count") else "Name of the track")}
                                 for k, v in list_vars().items()]})


async def h_ui(_):
    return web.Response(text=ui_page(), content_type="text/html")


async def h_state(req):
    if is_companion_poll(req):
        if COMP["last"] is None:
            _hrep["t"] = -1e9                                      # the first poll since the start: the Companion check changes from unknown, show it at once
        COMP["last"] = clock.monotonic()
    d = S.live_deck
    tr = track(*d.pt) if d and d.pt else None
    fid = tr["id"] if tr else (d.fid if d else None)         # a trigger point's voice-over has no playlist entry but is still a file
    full = _file_len(fid) if fid else 0.0
    if d and full < d.base + d.duration:
        full = d.base + d.duration
    live = {"live_pos": round(d.fpos(), 2) if d else 0, "live_dur": round(full, 2) if d else 0,
            "trim_fade_ms": int(CFG["trim_fade_ms"]), "trim_fadein_ms": fade_in_default_ms(), "live_fade_ms": int(d.end_fade_ms) if d else 0, "live_fade_in_ms": int(d.fade_in_ms) if d else 0, "live_in": round(d.lo, 2) if d else 0, "live_out": round(d.hi if d and d.hi else full, 2) if d else 0,
            "live_fid": fid,
            "live_rem": round(d.remaining(), 3) if d else None,
            "live_pass": d.pass_no() if d else 1, "live_passes": d.passes if d and not d.one_pass and d.pt and end_of(*d.pt) == "once" else 1,
            "live_end": end_of(*d.pt) if d and d.pt else "default"}        # exact seconds left (the stage page counts down from it)
    hs, ht = health()
    return web.json_response({**snapshot(), "version": APP_VERSION, **live, **triggers_json(), "health": {"status": hs, "detail": ht, **health_report(), **({"push_error": POSTER.last_error} if POSTER.last_error else {})}, "mem": mem_info(), "ram": warm.ram_info(), "input": lin.LI.info(), "rev": S.rev, "preview": preview.info(), "warning": warn_json(), **test_state(), "variable_prefix": CFG["var_prefix"],     # the prefix of every variable sent to Companion (the module declares its variables with it); not in snapshot()
                              
                              "feedback": f"{CFG['companion_host']}:{CFG['companion_osc_port']}"})


async def h_lists(_):
    rs = warm.ram_states()
    return web.json_response([
        {"name": pl["name"], "mode": pl_mode(i), "norm": norm_cfg(i),
         "ram_in": sum(1 for fid in pl["tracks"] if rs.get(fid) == "in"), "ram_total": sum(1 for fid in pl["tracks"] if fid in library), "shuffle_left": shuffle_left(i) if pl_mode(i) == "shuffle" else None,
         "tracks": [{"id": fid, "name": Path(fid).stem, "missing": fid not in library, "ram": rs.get(fid, "out"), "dur_eff": dur_eff(i, k), "loop": is_loop(i, k), "end": end_of(i, k), "xfade": xfade_of(i, k),
                     "lufs": (None if _lufs_of(fid) is None else round(_lufs_of(fid), 1)),
                     "trim": playlists[i].get("trims", {}).get(fid), "fade_ms_eff": fade_ms_of(i, k), "fade_in_ms_eff": fade_in_ms_of(i, k), "triggers": trigger_json(i, k), "measured": fid in LOUD, "gain_db": (None if norm_gain_db(i, k) is None else round(norm_gain_db(i, k), 1))}
                    for k, fid in enumerate(pl["tracks"])]}
        for i, pl in enumerate(playlists)])


async def h_formats(req):
    """GET /api/formats -> check status and the files with problems; ?deep=1 also decodes every file to find damage."""
    if req.query.get("deep") == "1":
        if not ff_check():
            return web.json_response({"ok": False, "error": FF["err"] or "ffmpeg was not found"}, status=415)
        for f in list(FMT.values()):
            f.pop("deep", None)
        fmt_kick(True)
    bad = [{"id": f, "lv": v["lv"], "msg": v["msg"]} for f, v in FMT.items() if f in library and v["lv"] in ("warn", "error")]
    return web.json_response({"ok": True, "available": bool(ff_check()), "running": FMT_STATE["running"], "deep": FMT_STATE["deep"],
                              "done": FMT_STATE["done"], "total": FMT_STATE["total"], "problems": bad})


async def h_lib_info(req):
    """GET /api/library/info?id=<library id>: the properties shown by the "i" button. Whatever is not measured yet is null with the
    state "measuring" (a background job fills it in; ask again a second later)."""
    fid = req.query.get("id", "")
    if fid not in library:
        return web.json_response({"error": "that file is not in the library"}, status=404)
    try:
        st = os.stat(LIB / fid)
    except OSError:
        return web.json_response({"error": "the file is missing from the disk (try Settings > Rescan library)"}, status=404)
    loop = asyncio.get_running_loop()
    ff = await loop.run_in_executor(None, ff_check)
    bi = bool(not ff and np is not None and await loop.run_in_executor(None, _scipy_ok))        # (importing scipy takes a moment: not on the event loop)
    r = info_response(fid, st, ff, bi)
    r["done"] = "measuring" not in r["status"].values()
    return web.json_response(r)


async def h_library(_):
    used = {}
    for p, pl in enumerate(playlists):
        for fid in pl["tracks"]:
            used.setdefault(fid, set()).add(p)
    dd = durations()
    fmt_kick()
    files = [{"id": fid, "name": Path(fid).stem, "size": size, "used": sorted(used.get(fid, ())),
              "dur": (dd[fid][2] if fid in dd and dd[fid][0] == size else None),
              "fmt": ({"lv": FMT[fid]["lv"], "msg": FMT[fid]["msg"], "tip": FMT[fid]["tip"]} if fid in FMT and FMT[fid]["s"] == size else None)}
             for fid, size in sorted(library.items(), key=lambda kv: kv[0].lower())]
    return web.json_response({"files": files, "folders": sorted(LIBDIRS, key=str.lower), "colors": FOLDER_COLORS, "icons": FOLDER_ICONS, "flags": _flags_out(), "storage": storage_info(True)})


async def h_lib_rename(req):
    b = await body(req)
    msg, status = lib_rename(b.get("from", ""), b.get("to", ""))
    push(True)
    return web.json_response({"ok": status == 200, **({"id": msg} if status == 200 else {"error": msg})}, status=status)


async def h_lib_mkdir(req):
    b = await body(req)
    msg, status = lib_mkdir(b.get("path", ""))
    return web.json_response({"ok": status == 200, **({"path": msg} if status == 200 else {"error": msg})}, status=status)


async def h_lib_color(req):
    """Set the colour and / or the icon of a library folder: {path, color: "#rrggbb"|null, icon: "name"|null}."""
    b = await body(req)
    rel = _safe_rel(b.get("path", ""), True)
    if not rel or rel not in LIBDIRS:
        return web.json_response({"ok": False, "error": "no such folder"}, status=404)
    if "color" in b:
        col = b.get("color")
        if col in (None, ""):
            FOLDER_COLORS.pop(rel, None)
        elif re.fullmatch(r"#[0-9a-fA-F]{6}", str(col)):
            FOLDER_COLORS[rel] = str(col).lower()
        else:
            return web.json_response({"ok": False, "error": "colour must look like #3b82f6"}, status=400)
    if "icon" in b:
        ic = b.get("icon")
        if ic in (None, ""):
            FOLDER_ICONS.pop(rel, None)
        elif re.fullmatch(r"[a-z0-9-]{1,32}", str(ic)):
            FOLDER_ICONS[rel] = str(ic)
        else:
            return web.json_response({"ok": False, "error": "unknown icon"}, status=400)
    save()
    return web.json_response({"ok": True})


def _flags_out():
    """Favorite / hidden flags of the folders that exist (a stale path left in the file is ignored)."""
    return {k: dict(v) for k, v in FOLDER_FLAGS.items() if k in LIBDIRS}


async def h_lib_flags_get(_):
    return web.json_response({"flags": _flags_out()})


async def h_lib_flags(req):
    """Set the favorite and / or hidden flag of a library folder: {path, fav: bool, hidden: bool}. Shared by every browser.
    Web page only: never in snapshot() or command()."""
    b = await body(req)
    rel = _safe_rel(b.get("path", ""), True)
    if not rel or rel not in LIBDIRS:
        return web.json_response({"ok": False, "error": "no such folder"}, status=404)
    cur = dict(FOLDER_FLAGS.get(rel, {}))
    for f in ("fav", "hidden"):
        if f in b:
            if not isinstance(b[f], bool):
                return web.json_response({"ok": False, "error": f"{f} must be true or false"}, status=400)
            if b[f]:
                cur[f] = True
            else:
                cur.pop(f, None)
    if cur:
        FOLDER_FLAGS[rel] = cur
    else:
        FOLDER_FLAGS.pop(rel, None)
    save()
    return web.json_response({"ok": True, "flags": _flags_out()})


async def h_lib_rmdir(req):
    msg, status = lib_rmdir(req.query.get("path", ""), req.query.get("force") == "1")
    push(True)
    return web.json_response({"ok": status == 200, **({} if status == 200 else {"error": msg})}, status=status)


async def h_storage(_):
    return web.json_response(storage_info(True))


async def h_get_settings(_):
    return web.json_response({"companion_host": CFG["companion_host"],
                              "companion_osc_port": CFG["companion_osc_port"],
                              "target": f"{CFG['companion_host']}:{CFG['companion_osc_port']}",
                              "var_prefix": CFG["var_prefix"], "variable_prefix": CFG["var_prefix"],
                              "host_found": getattr(osc_out, "found", None),
                              "config_file": str(cfg_file)})


def warn_json():
    """The Time warning settings; "set" is false until someone has saved them (a page may then upload its old browser copy)."""
    w = CFG["time_warning"]
    ws = (w or WARN_DEFAULT)["warnings"]
    # t1/c1 (longest) and t2/c2 (shortest) are the older two-warning shape, so a page that is still open from before keeps working
    return {"set": w is not None, "on": True, "warnings": ws, "t1": ws[0]["t"], "c1": ws[0]["c"], "t2": ws[-1]["t"], "c2": ws[-1]["c"]}


async def h_warn_get(_):
    return web.json_response(warn_json())


async def h_warn_set(req):
    """POST {"warnings": [{"t": seconds, "c": "#rrggbb"}, ...]}: replace the Time warning list for every page, and keep it in state.json."""
    try:
        b = await req.json()
    except Exception:
        b = None
    try:
        new = warn_clean(b, CFG["time_warning"])
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)
    if new is None:
        return web.json_response({"ok": False, "error": "send a JSON object"}, status=400)
    CFG["time_warning"] = new
    save_state()
    return web.json_response({"ok": True, **warn_json()})


def health_report_text():
    """The plain text of "Copy report", for pasting into a chat. Deliberately without Companion addresses, the webhook address, and file paths."""
    rep = health_report(force=True)
    names = DW.names or []                                      # the last good list: this report never enumerates devices itself
    known = DW.names is not None
    labels = {"ok": "OK", "warn": "WARNING", "bad": "PROBLEM", "unknown": "unknown"}
    lines = [f"Cue Media Engine health report ({player_name()})", f"Version: {APP_VERSION}", f"Date: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %z')}",
             f"State: {rep['state'].capitalize()}" + (f" ({rep['summary']})" if rep["summary"] else ""), "", "Checks:"]
    for c in rep["checks"]:
        line = f"- {c['title']}: {labels.get(c['status'], c['status'])}"
        if c["text"]:
            line += f" \u2014 {c['text']}"
        lines.append(line)
    live = CFG["audio_device"] or DEV_MISSING.get("output")
    pv = CFG["preview_device"]
    lines += ["", f"Audio driver: {AUDRV.text(pygame.mixer.get_init() is not None)}",
              f"Live output: {outalias.shown(live) if live else 'system default'}" + ("" if live is None else (" (found in the device list)" if live in names and not DEV_MISSING.get("output") else " (NOT in the device list)" if known and not decks else " (not checked while audio plays)" if decks else " (not checked yet)")),
              f"Preview output: {outalias.shown(pv) if pv else 'none'}" + ("" if not pv else (" (found in the device list)" if pv in names else " (NOT in the device list)" if known and not decks else " (not checked while audio plays)" if decks else " (not checked yet)")),
              f"Audio engine: {healthm.restarts_note(WD.total)}" + ("" if CFG["watchdog"] else " (watchdog is off)"),
              f"Push messages: {'on' if CFG['push_enabled'] and CFG['push_url'] else 'off'}" + (f"; last failure: {POSTER.last_error}" if POSTER.last_error else ""),
              healthm.process_memory_text(), healthm.open_files_text()]
    return "\n".join(lines) + "\n"


async def h_health_report(_):
    return web.json_response({"ok": True, "text": await asyncio.get_running_loop().run_in_executor(None, health_report_text)})


def health_settings_json():
    return {"watchdog": bool(CFG["watchdog"]), "preview_amber": bool(CFG["health_preview_amber"]),
            "restarts": WD.total, "beats": HB.beats, "stalled": WD.stalled, "gave_up": WD.gave_up,
            "player_name": CFG["player_name"], "player_in_use": player_name(), "push": {"enabled": bool(CFG["push_enabled"]), "has_url": bool(CFG["push_url"]), "host": alerts.mask_url(CFG["push_url"]), "events": dict(CFG["push_events"]),
                     "hold": bool(CFG["push_hold"]), "queued": len(ALERT.held), "last_error": POSTER.last_error, "last_ok_at": POSTER.last_ok_at, "player": player_name()}}


async def h_health_get(_):
    return web.json_response({"ok": True, **health_settings_json()})


async def h_health_set(req):
    """POST {"watchdog": bool, "preview_amber": bool} (either): Settings > System > Health and alerts. Saved at once, like the other settings."""
    b = await body(req)
    for key, cfg in (("watchdog", "watchdog"), ("preview_amber", "health_preview_amber")):
        if key in b:
            if not isinstance(b[key], bool):
                return web.json_response({"ok": False, "error": f"{key} must be true or false"}, status=400)
            CFG[cfg] = b[key]
    if "player_name" in b:
        n = b["player_name"]
        if not isinstance(n, str):
            return web.json_response({"ok": False, "error": "the player name must be text"}, status=400)
        n = " ".join(n.split())                              # trimmed, inner runs of spaces collapsed
        if len(n) > PLAYER_NAME_MAX:
            return web.json_response({"ok": False, "error": f"the player name can be at most {PLAYER_NAME_MAX} characters"}, status=400)
        CFG["player_name"] = n
    if "push" in b:
        p = b["push"]
        if not isinstance(p, dict):
            return web.json_response({"ok": False, "error": "push must be an object"}, status=400)
        try:
            new = {}
            for key, cfg in (("enabled", "push_enabled"), ("hold", "push_hold")):
                if key in p:
                    if not isinstance(p[key], bool):
                        raise ValueError(f"{key} must be true or false")
                    new[cfg] = p[key]
            if "url" in p:
                new["push_url"] = alerts.clean_url(p["url"])
            if "events" in p:
                new["push_events"] = alerts.clean_events(p["events"], CFG["push_events"])
        except ValueError as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)
        CFG.update(new)
        if new.get("push_hold") is False:
            ALERT.flush()                                    # hold was switched off: what waited goes out now
    save_state()
    _hrep["t"] = -1e9
    return web.json_response({"ok": True, **health_settings_json()})


async def h_push_test(_):
    """Send a test message now (whatever the hold setting says; no state changes). The send runs in a thread; the answer is the result for the chip."""
    if not CFG["push_url"]:
        return web.json_response({"ok": False, "error": "Enter a webhook address first", "at": clock.time()})
    ok, reason = await asyncio.get_running_loop().run_in_executor(None, ALERT.send_test)
    return web.json_response({"ok": ok, "error": reason, "at": clock.time()})


async def h_test_stall(_):
    """Test hook, only registered when CP_TEST_WATCHDOG is set: the heartbeat stops counting, as if the audio callback had stalled (a restart clears it)."""
    HB.frozen = True
    return web.json_response({"ok": True})


async def h_tr_get(_):
    return web.json_response({"default": CFG["default_transition"], "crossfade_ms": CFG["crossfade_ms"], "trim_fade_ms": fade_default_ms(), "trim_fadein_ms": fade_in_default_ms()})


async def h_tr_set(req):
    b = await body(req)
    try:
        mode = str(b.get("default", CFG["default_transition"]))
        ms = int(round(float(b.get("crossfade_s", float(CFG["crossfade_ms"]) / 1000.0)) * 1000))
        fms = int(round(float(b["trim_fade_s"]) * 1000)) if "trim_fade_s" in b else fade_default_ms()
        if mode not in ("cut", "crossfade") or not (0 <= ms <= 30000):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        return web.json_response({"ok": False, "error": "Default: cut or crossfade. Crossfade time: 0 to 30 seconds."}, status=400)
    if not (FADE_MIN_MS <= fms <= FADE_MAX_MS):
        return web.json_response({"ok": False, "error": "Default fade-out at B: 0.1 to 10 seconds."}, status=400)
    try:
        fin = int(round(float(b["trim_fadein_s"]) * 1000)) if "trim_fadein_s" in b else fade_in_default_ms()
    except (TypeError, ValueError, OverflowError):
        return web.json_response({"ok": False, "error": "Default fade-in at A: 0 (none) or 0.1 to 10 seconds."}, status=400)
    if fin != 0 and not (FADE_MIN_MS <= fin <= FADE_MAX_MS):
        return web.json_response({"ok": False, "error": "Default fade-in at A: 0 (none) or 0.1 to 10 seconds."}, status=400)
    try:
        save_config_keys({"default_transition": mode, "crossfade_ms": ms, "trim_fade_ms": fms, "trim_fadein_ms": fin})
    except Exception as e:
        return web.json_response({"ok": False, "error": f"Could not write config.json: {e}"}, status=500)
    CFG["default_transition"], CFG["crossfade_ms"], CFG["trim_fade_ms"], CFG["trim_fadein_ms"] = mode, ms, fms, fin
    return web.json_response({"ok": True})


def duck_json():
    return {"fade_ms": CFG["top_fade_ms"], "track_pct": CFG["top_track_pct"], "threshold_db": CFG["duck_threshold_db"],
            "ratio": CFG["duck_ratio"], "attack_ms": CFG["duck_attack_ms"], "release_ms": CFG["duck_release_ms"],
            "hold": bool(CFG["duck_hold"])}


async def h_folders_get(_):
    return web.json_response({"default_icon": CFG.get("default_folder_icon") or ""})


async def h_folders_set(req):
    b = await body(req)
    ic = str(b.get("default_icon") or "")
    if ic and not re.fullmatch(r"[a-z0-9-]{1,32}", ic):
        return web.json_response({"ok": False, "error": "unknown icon"}, status=400)
    try:
        save_config_keys({"default_folder_icon": ic})
    except Exception as e:
        return web.json_response({"ok": False, "error": f"Could not write config.json: {e}"}, status=500)
    CFG["default_folder_icon"] = ic
    return web.json_response({"ok": True})


async def h_top_get(_):
    return web.json_response(duck_json())


async def h_top_set(req):
    b = await body(req)
    m = {"track_pct": "top_track_pct", "threshold_db": "duck_threshold_db", "ratio": "duck_ratio",
         "attack_ms": "duck_attack_ms", "release_ms": "duck_release_ms", "hold": "duck_hold", "fade_ms": "top_fade_ms"}
    err = set_duck({m[k]: v for k, v in b.items() if k in m})
    if err:
        return web.json_response({"ok": False, "error": err}, status=400)
    return web.json_response({"ok": True, **duck_json()})


# ---------------------------------------------------------------- Live input (Duck only)
def _on_off(arg, cur):
    """on / off / toggle (or 1 / 0, true / false) -> bool, or None for anything else."""
    if isinstance(arg, bool):
        return arg
    a = str(arg or "toggle").lower()
    if a == "toggle":
        return not cur
    if a in ("on", "1", "true", "yes"):
        return True
    if a in ("off", "0", "false", "no"):
        return False
    return None


def input_command(parts):
    """/input/armed/<on|off|toggle>   /input/ducknow/<on|off|toggle>. Returns None, or an error word for command()."""
    what = parts[1].lower() if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""
    if what == "armed":
        v = _on_off(arg, CFG["input_armed"])
        if v is None or lin.LI.set_config({"armed": v}):
            return "invalid"
    elif what in ("ducknow", "duck_now", "duck"):
        v = _on_off(arg, lin.LI.duck_now)
        if v is None:
            return "invalid"
        lin.LI.set_duck_now(v)
    else:
        return "invalid"
    push()
    return None


async def h_input_get(_):
    return web.json_response({**lin.LI.info(), "devices": list_capture_devices(), "notice": dev_notices(list_devices()).get("input", "")})


async def h_input_set(req):
    b = await body(req)
    keys = {"device", "channel", "channels", "gain_db", "threshold_db", "armed"}
    err = lin.LI.set_config({k: v for k, v in b.items() if k in keys})
    if err:
        return web.json_response({"ok": False, "error": err}, status=400)
    push()
    return web.json_response({"ok": True, **lin.LI.info()})


async def h_input_solo(req):
    on = lin.as_bool((await body(req)).get("on"))
    if on and not preview.enabled():
        return web.json_response({"ok": False, "error": "Choose a Preview output first (Settings > Audio)."}, status=400)
    lin.LI.set_solo(on)
    return web.json_response({"ok": True, **lin.LI.info()})


async def h_input_ducknow(req):
    v = _on_off((await body(req)).get("on", "toggle"), lin.LI.duck_now)
    if v is None:
        return web.json_response({"ok": False, "error": "send on: true or false"}, status=400)
    lin.LI.set_duck_now(v)
    push()
    return web.json_response({"ok": True, **lin.LI.info()})


def host_error(host):
    """None when `host` is a complete IP address or host name; else a short reason. A half-typed address such as 192.168.1. is refused,
    so the address in use only ever changes to a complete one."""
    if not host:
        return "Enter an IP address or a host name, e.g. 192.168.1.50"
    if ":" in host:                                          # IPv6
        try:
            ipaddress.IPv6Address(host)
            return None
        except ValueError:
            return "Incomplete address: that is not a complete IPv6 address"
    if not re.fullmatch(r"[A-Za-z0-9._\-]+", host):
        return "Enter an IP address or a host name, e.g. 192.168.1.50"
    if re.fullmatch(r"[0-9.]+", host):                       # looks like an IPv4 address: it must be a whole one
        try:
            ipaddress.IPv4Address(host)
            return None
        except ValueError:
            return "Incomplete address: an IP address has four numbers from 0 to 255, e.g. 192.168.1.50"
    if host.startswith((".", "-")) or host.endswith((".", "-")) or ".." in host or len(host) > 253:
        return "Incomplete address: check the host name"
    return None


PREFIX_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,15}")      # the variable prefix: a letter first, then letters, digits and underscores, 1 to 16 in all


def prefix_error(p):
    """None when `p` can be the variable prefix, else a short reason. A trailing underscore is the user's choice (mp_ and mp are both fine)."""
    if not isinstance(p, str) or not PREFIX_RE.fullmatch(p):
        return "Use 1 to 16 letters, digits or underscores, starting with a letter."
    return None


async def h_prefix_set(req):
    """POST {"prefix": "mp_", "confirm": true}: change the prefix of every variable sent to Companion (CFG["var_prefix"], config.json). Changing it breaks
    Companion buttons that use the old names, so without "confirm": true the answer is 409 {needs_confirm, old, new, message} and nothing changes. With it the
    new prefix is saved and every variable is sent again under the new names (the old ones stay in Companion until it is told otherwise)."""
    b = await body(req)
    new = b.get("prefix")
    err = prefix_error(new)
    if err:
        return web.json_response({"ok": False, "error": err, "prefix": CFG["var_prefix"]}, status=400)
    old = CFG["var_prefix"]
    if new == old:
        return web.json_response({"ok": True, "changed": False, "prefix": old, "example": old + "remaining"})
    if b.get("confirm") is not True:
        return web.json_response({"ok": False, "needs_confirm": True, "old": old, "new": new,
                                  "message": "Buttons and triggers in Companion that use the old variable names must be updated, and the old variables stay in Companion until the module is reloaded."}, status=409)
    try:
        save_config_keys({"var_prefix": new})
    except Exception as e:
        return web.json_response({"ok": False, "error": f"Could not write config.json: {e}"}, status=500)
    CFG["var_prefix"] = new
    last_sent.clear()
    push(True)                                   # everything again, under the new names
    print(f"Variable prefix changed from {old} to {new} (saved to config.json)")
    return web.json_response({"ok": True, "changed": True, "prefix": new, "old": old, "example": new + "remaining", "sending": not _osc["down"]})


TEST_VAR = "test"                       # the Companion custom variable <var_prefix>test (mp_test with the default prefix)
TEST_LAST = {"value": "", "at": "", "t": 0.0}      # the last test message sent (reported in /api/state for the Companion module, never in snapshot())


def osc_error_text(e):
    if isinstance(e, socket.gaierror):
        return "Host not found"
    n = getattr(e, "errno", None)
    if n in (errno.ENETUNREACH, errno.EHOSTUNREACH, getattr(errno, "ENETDOWN", -1)):
        return "Network unreachable"
    if n == errno.ECONNREFUSED:
        return "Connection refused"
    return "Socket error: " + (e.strerror if isinstance(e, OSError) and e.strerror else str(e) or type(e).__name__)


TEST_FRESH_S = 120


def test_state():
    """`test_message` / `test_sent_at` of /api/state. The Companion module cannot receive OSC (it polls HTTP), so it fills its variable <prefix>test from
    this. The value is only reported for TEST_FRESH_S seconds after the test was sent, then it is "" again, so Companion cannot go on showing an old
    time as if it were a new test; `test_sent_at` (epoch seconds) is there so a client can tell tests apart even when the HH:MM:SS repeats."""
    t = TEST_LAST["t"]
    if t and clock.time() - t <= TEST_FRESH_S:
        return {"test_message": TEST_LAST["value"], "test_sent_at": round(t, 3)}
    return {"test_message": "", "test_sent_at": None}


async def h_companion_test(_):
    """Send <var_prefix>test = HH:MM:SS to Companion with the same sender, address and port as the live variables (osc_out, never a
    value being edited in the page). UDP gives no reply, so ok only means the player sent it."""
    target = f"{CFG['companion_host']}:{CFG['companion_osc_port']}"
    at = time.strftime("%H:%M:%S", time.localtime(clock.time()))
    try:
        refresh = getattr(osc_out, "refresh", None)
        if refresh:
            await refresh()                                  # a fresh lookup, whatever happened before (off the event loop)
        osc_out.send_message(f"/custom-variable/{CFG['var_prefix']}{TEST_VAR}/value", at)
    except Exception as e:
        return web.json_response({"ok": False, "error": osc_error_text(e), "sent_to": target, "host_found": getattr(osc_out, "found", None)})
    TEST_LAST["value"], TEST_LAST["at"], TEST_LAST["t"] = at, at, clock.time()
    return web.json_response({"ok": True, "sent_to": target, "at": at, "host_found": True})


async def h_set_settings(req):
    """Change where variables are sent to Companion: applied immediately and saved to config.json."""
    global osc_out
    b = await body(req)
    host = str(b.get("companion_host", "")).strip()
    err = host_error(host)
    if err:
        return web.json_response({"ok": False, "error": err}, status=400)
    try:
        port = int(str(b.get("companion_osc_port", "")).strip())
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        return web.json_response({"ok": False, "error": "The port must be a number from 1 to 65535"}, status=400)
    client = OscOut(host, port)                  # no lookup here: a well-formed name that does not resolve (yet) is still saved
    try:
        save_config_keys({"companion_host": host, "companion_osc_port": port})
    except Exception as e:
        return web.json_response({"ok": False, "error": f"Could not write config.json: {e}"}, status=500)
    osc_out = client
    CFG["companion_host"], CFG["companion_osc_port"] = host, port
    last_sent.clear()
    push(True)                                   # the new Companion gets every variable straight away
    print(f"Companion address changed to {host}:{port} (saved to config.json)")
    found = await client.refresh()
    return web.json_response({"ok": True, "target": f"{host}:{port}", "host_found": found})


async def h_waveform(req):
    fid = req.query.get("id", "")
    if fid not in library:
        return web.json_response({"error": "not in the library"}, status=404)
    try:
        return web.json_response(await get_wave(fid))
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def h_meters(_):
    return web.json_response(meters_json())


_live_subs = [0]


async def h_live(req):
    """Server-sent events for the web page: level meters about 14 times a second and the preview output's state about
    4 times a second, over one connection instead of two polling loops."""
    if _live_subs[0] >= 16:
        return web.json_response({"error": "too many live streams open"}, status=429)
    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-store", "X-Accel-Buffering": "no"})
    await resp.prepare(req)
    _live_subs[0] += 1
    n = 0
    try:
        while req.transport is not None and not req.transport.is_closing():
            msg = {"m": meters_json()}
            if n % 4 == 0:
                msg["pv"] = preview.info()
            await resp.write(b"data: " + json.dumps(msg).encode() + b"\n\n")
            n += 1
            await asyncio.sleep(0.07)
    except (ConnectionError, asyncio.CancelledError):
        pass                                           # the page was closed or reloaded
    finally:
        _live_subs[0] -= 1
    return resp


async def h_lib_file(req):
    """Stream a library file to the browser (preview in the web page). Only ids in the library are served;
    aiohttp answers Range requests, so seeking works."""
    fid = req.query.get("id", "")
    if fid not in library:
        return web.json_response({"error": "not in the library"}, status=404)
    return web.FileResponse(LIB / fid)


async def h_pv_state(_):
    return web.json_response(preview.info())


async def h_pv_play(req):
    d = await body(req)
    if not preview.enabled():
        return web.json_response({"ok": False, "error": "no preview output set"}, status=400)
    if "id" in d:
        ok = preview.play_id(str(d["id"]))
    else:
        try:
            p, t = int(d.get("p", -1)), int(d.get("t", -1))
        except (TypeError, ValueError, OverflowError):
            p, t = -1, -1
        ok = valid(p, t) and preview.play_pt(p, t)
    return web.json_response({"ok": bool(ok)}, status=200 if ok else 404)


async def h_pv_ctl(req):
    d = await body(req)
    op = d.get("cmd")
    if not preview.enabled():
        return web.json_response({"ok": False, "error": "no preview output set"}, status=400)
    if op in ("stop", "pause", "resume"):
        preview.send({"cmd": op})
    elif op == "loop":                                  # Loop A-B in the trim dialog: preview output only, never the live decks
        a, b, fin, fout = (finite_float(d.get(k, 0)) for k in ("a", "b", "fin", "fout"))
        if None in (a, b, fin, fout) or a < 0 or b < a + 0.1 or not (0 <= fin <= 10000) or not (0 <= fout <= 10000):
            return web.json_response({"ok": False, "error": "a loop needs A, B (at least 0.1 s apart) and fade times of 0 to 10000 ms"}, status=400)
        preview.send({"cmd": "loop", "a": a, "b": b, "fin": fin, "fout": fout})
    elif op == "mute":                                  # the Mute button under the Preview meters: the preview output only
        if not isinstance(d.get("on"), bool):
            return web.json_response({"ok": False, "error": "on must be true or false"}, status=400)
        preview.set_mute(d["on"])
    elif op in ("seek", "vol"):
        v = finite_float(d.get("pos", 0) if op == "seek" else d.get("v", 1))
        if v is None:
            return web.json_response({"ok": False, "error": "a finite number is needed"}, status=400)
        if op == "seek":
            preview.send({"cmd": "seek", "pos": v})
        else:
            preview.set_volume(v)
    else:
        return web.json_response({"ok": False, "error": "unknown command"}, status=400)
    return web.json_response({"ok": True})


async def h_pv_device(req):
    name = (await body(req)).get("name") or None
    if name is not None and name not in list_devices():
        return web.json_response({"ok": False, "error": "unknown device"}, status=400)
    if name is not None and outalias.live_only(name):
        return web.json_response({"ok": False, "error": outalias.LIVE_ONLY_MSG}, status=400)
    preview.set_device(name)
    push(True)
    return web.json_response({"ok": True, "device": name})


async def h_mirror_device(req):
    name = (await body(req)).get("name") or None
    if name is not None and name not in list_devices():
        return web.json_response({"ok": False, "error": "unknown device"}, status=400)
    if name is not None and outalias.live_only(name):
        return web.json_response({"ok": False, "error": outalias.LIVE_ONLY_MSG}, status=400)
    CFG["mirror_device"] = name
    save_state()
    mirror.apply()
    return web.json_response({"ok": True, "device": name})


async def h_mirror_enable(req):
    CFG["mirror_enabled"] = bool((await body(req)).get("on"))
    save_state()
    mirror.apply()
    return web.json_response({"ok": True, "enabled": CFG["mirror_enabled"]})


async def h_devices(_):
    names = list_devices()
    return web.json_response({"devices": names, "current": CFG["audio_device"], "saved_output": DEV_MISSING.get("output"), "notices": dev_notices(names),
                              "preview": CFG["preview_device"], "mirror": CFG["mirror_device"], "mirror_enabled": CFG["mirror_enabled"],
                              "output_info": outalias.info(names), "output_aliases": outalias.table(), "output_aliases_default": outalias.is_default(),
                              "inputs": list_capture_devices(), "input": CFG["input_device"],
                              "mirror_error": (mirror.status.get("error") or "") if mirror.enabled() else "",
                              "mirror_playing": int(mirror.status.get("mon") or 0) if mirror.enabled() else 0})


def outputs_json():
    return {"aliases": outalias.table(), "using_default": outalias.is_default(), "default": outalias.DEFAULT_ALIASES, "max_entries": outalias.MAX_ENTRIES}


async def h_outputs_get(_):
    return web.json_response({"ok": True, **outputs_json()})


async def h_outputs_set(req):
    """POST {"aliases": [ {match, label?, hidden?, group?, live_only?}, ... ]} replaces the whole table; {"aliases": null} goes back to the built-in
    default (as if never saved). A bad table is refused whole and the old one stays. The saved Live / Preview / Mirror names are never touched."""
    b = await body(req)
    if "aliases" not in b:
        return web.json_response({"ok": False, "error": "send \"aliases\": a list, or null for the default"}, status=400)
    try:
        new = None if b["aliases"] is None else outalias.clean_aliases(b["aliases"])
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)
    CFG["output_aliases"] = new
    save_state()
    push(True)
    return web.json_response({"ok": True, **outputs_json()})


async def h_set_device(req):
    name = (await body(req)).get("name")
    if name is not None and name not in list_devices():
        return web.json_response({"ok": False, "error": "unknown device"}, status=400)
    ok = set_device(name)
    push(True)
    return web.json_response({"ok": ok}, status=200 if ok else 500)


PL_NAME_MAX = 80            # longest playlist name (create and rename)


async def h_add_list(req):
    b = await body(req)
    name = str(b.get("name") or "Playlist").strip()[:PL_NAME_MAX].strip() or "Playlist"
    playlists.append({"name": name, "tracks": []})
    save(); push(True)
    return web.json_response({"ok": True})


def move_playlist_to(i, j):
    """Move playlist i so that it ends up at position j. Everything that remembers a playlist number follows it."""
    n = len(playlists)
    if not (0 <= i < n and 0 <= j < n):
        return False
    if i == j:
        return True

    def f(x):
        if x == i:
            return j
        if i < j and i < x <= j:
            return x - 1
        if i > j and j <= x < i:
            return x + 1
        return x

    playlists.insert(j, playlists.pop(i))
    for d in decks:
        if d.pt:
            d.pt = [f(d.pt[0]), d.pt[1]]
    if S.pending:
        S.pending["pt"] = [f(S.pending["pt"][0]), S.pending["pt"][1]]
    focus[0] = f(focus[0])
    moved = {f(k): v for k, v in _bag.items()}
    _bag.clear()
    _bag.update(moved)
    save()
    return True


async def h_pl_reorder(req):
    b = await body(req)
    try:
        ok = move_playlist_to(int(b["from"]), int(b["to"]))
    except (KeyError, TypeError, ValueError):
        ok = False
    push(True)
    return web.json_response({"ok": ok}, status=200 if ok else 400)


async def h_pl_rename(req):
    i = route_int(req, "p")
    b = await body(req)
    name = " ".join(str(b.get("name", "")).split())[:PL_NAME_MAX]
    if not (0 <= i < len(playlists)) or not name:
        return web.json_response({"ok": False}, status=400)
    playlists[i]["name"] = name
    save()
    push(True)
    return web.json_response({"ok": True})


async def h_pl_trim(req):
    """POST {track, in, out, end}: set the In/Out of one track (a null or missing point is cleared; {"clear":true} removes both)."""
    i = route_int(req, "p")
    b = await body(req)
    try:
        t = int(b.get("track"))
    except (TypeError, ValueError, OverflowError):
        return web.json_response({"ok": False}, status=400)
    if b.get("clear"):
        fields = {"in": None, "out": None, "end": None, "fade_ms": None, "start": None, "fade_in_ms": None}
    else:
        fields = {k: b.get(k) for k in ("in", "out", "fade_ms", "fade_in_ms") if k in b}
        for k in ("end", "start"):
            if k in b:
                fields[k] = b[k]
    if not set_trim(i, t, fields):
        return web.json_response({"ok": False, "error": "invalid trim (Out must be at least 0.5 s after In; fade 0.1 to 10 s)"}, status=400)
    push(True)
    return web.json_response({"ok": True, "trim": playlists[i].get("trims", {}).get(playlists[i]["tracks"][t]), "fade_ms": fade_ms_of(i, t), "fade_in_ms": fade_in_ms_of(i, t)})


async def h_pl_triggers_get(req):
    """GET ?track=<n>: the trigger points of one track (all tracks of the playlist when track is left out)."""
    i = route_int(req, "p")
    if not 0 <= i < len(playlists):
        return web.json_response({"ok": False, "error": "no such playlist"}, status=404)
    q = req.query.get("track")
    if q is not None:
        if not is_uint(q) or not valid(i, int(q)):
            return web.json_response({"ok": False, "error": "no such track"}, status=400)
        return web.json_response({"ok": True, "triggers": trigger_json(i, int(q))})
    return web.json_response({"ok": True, "tracks": {str(k): trigger_json(i, k) for k in range(len(playlists[i]["tracks"])) if triggers_of(i, k)}})


async def h_pl_triggers(req):
    """POST {track, action: add|update|delete|set, id, at, file, once, enabled, triggers}: edit the trigger points of one track."""
    i = route_int(req, "p")
    b = await body(req)
    try:
        t = int(b.get("track"))
    except (TypeError, ValueError, OverflowError):
        return web.json_response({"ok": False, "error": "track is missing"}, status=400)
    _lst, err = set_triggers(i, t, str(b.get("action", "")).lower(), b)
    if err:
        return web.json_response({"ok": False, "error": err}, status=400)
    push(True)
    return web.json_response({"ok": True, "triggers": trigger_json(i, t)})


async def h_triggers_get(_):
    return web.json_response({"ok": True, **triggers_json()})


async def h_triggers_arm(req):
    """POST {armed: true|false}: the Auto triggers switch. Without a body it toggles."""
    b = await body(req)
    try:
        on = _truthy(b["armed"]) if "armed" in b else not CFG["triggers_armed"]
        set_triggers_armed(on)
    except Exception as e:
        return web.json_response({"ok": False, "error": f"Could not write config.json: {e}"}, status=500)
    return web.json_response({"ok": True, **triggers_json()})


async def h_triggers_skip(_):
    nt = skip_next_trigger()
    return web.json_response({"ok": nt is not None, "skipped": nt, **triggers_json()}, status=200 if nt else 409)


async def h_pl_norm(req):
    i = route_int(req, "p")
    b = await body(req)
    ok = set_norm(i, mode=b.get("mode"), ref=b.get("ref"), lufs=b.get("lufs"))
    return web.json_response({"ok": ok}, status=200 if ok else 400)


async def h_del_list(req):
    i = route_int(req, "p")
    if 0 <= i < len(playlists):
        if S.live_deck and S.live_deck.pt and S.live_deck.pt[0] == i:
            S.live_deck.pt = None                       # keeps playing; its playlist is gone
        playlists.pop(i)

        def fn(pt):
            return None if pt[0] == i else ([pt[0] - 1, pt[1]] if pt[0] > i else pt)

        for d in decks:
            if d.pt:
                d.pt = fn(d.pt)
        focus[:] = [0, 0]
        save(); push(True)
    return web.json_response({"ok": True})


async def h_pl_add(req):
    p = route_int(req, "p")
    b = await body(req)
    files, index = b.get("files", []), b.get("index")
    try:
        if not isinstance(files, (list, str)):
            raise TypeError
        if index is not None:
            index = int(index)
    except (TypeError, ValueError, OverflowError):
        return web.json_response({"ok": False, "result": "invalid", "error": "files must be a list of library ids and index a number"}, status=400)
    res = add_to_playlist(p, list(files), index)
    push(True)
    return web.json_response({"ok": res == "ok", "result": res}, status=200 if res == "ok" else 400)


async def h_pl_remove(req):
    res = remove_from_playlist(route_int(req, "p"), route_int(req, "t"))
    push(True)
    return web.json_response({"ok": res == "ok"}, status=200 if res == "ok" else 400)


async def h_ffmpeg(_):
    ok = ff_check(True)
    return web.json_response({"ok": ok, "version": FF["ver"], "error": FF["err"], "ffprobe": bool(FF["probe"]),
                              "cores": CFG["ffmpeg_cores"], "convert": bool(CFG["import_convert"]), "normalise": bool(CFG["import_normalise"]),
                              "formats": sorted(e[1:] for e in CONVERT_EXT)})


async def h_lib_delete(req):
    res = delete_from_library(req.query.get("id", ""))
    push(True)
    return web.json_response({"ok": res == "ok"}, status=200 if res == "ok" else 404)


async def h_move(req):
    b = await body(req)
    try:
        (fp, ft), (tp, ti) = b["from"], b["to"]
        result = move_track(int(fp), int(ft), int(tp), int(ti))
    except (KeyError, TypeError, ValueError):
        result = "invalid"
    push(True)
    return web.json_response({"ok": result == "ok", "result": result}, status=200 if result == "ok" else 400)


async def h_monitor(_):
    """For Solo live in the browser: what is on air right now, so the page can play a copy of it. Changes nothing on the player."""
    out = []
    for d in monitor_decks()[:3]:
        try:
            out.append({"id": d["id"], "fid": Path(d["path"]).relative_to(LIB).as_posix(), "pos": d["pos"], "vol": d["vol"]})
        except ValueError:
            pass                                   # not a library file
    return web.json_response({"decks": out})


async def h_scan(_):
    return web.json_response({**S.last_scan, "missing": missing_refs()})


# ---------------------------------------------------------------- download from a link (yt-dlp, or youtube-dl)
DL_FORMATS = {"mp3": ("mp3", "0"), "flac": ("flac", None), "wav": ("wav", None)}     # name -> (ffmpeg codec, quality)
DL = {"state": "idle", "url": "", "title": "", "pct": 0.0, "msg": "", "files": [], "ids": [], "folder": "", "note": ""}
_dl_task = None


def ytdl_module():
    """The downloader library: yt-dlp (kept up to date; YouTube changes often) or, failing that, youtube-dl. None if neither is installed."""
    for name in ("yt_dlp", "youtube_dl"):
        try:
            return __import__(name)
        except ImportError:
            continue
    return None


def _dl_clean(name):
    name = re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(name))).strip(" .")
    return name[:120] or "download"


async def _dl_child(url, codec, quality, whole, tmp):
    """Run the download in a helper process under the same CPU limits as ffmpeg (nice, the last few cores, low priority
    on Windows), and follow its progress. Returns ({"_type": "playlist"} or {}, error text or None)."""
    args = {"url": url, "codec": codec, "quality": quality, "whole": whole, "tmp": str(tmp),
            "normalise": bool(CFG["import_normalise"]), "ffmpeg": FF["exe"] or ""}
    env = {**os.environ, "PYGAME_HIDE_SUPPORT_PROMPT": "1"}
    vb = str(Path(sys.executable).parent)             # a deno installed with pip lives next to python in the venv
    if vb not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = vb + os.pathsep + env.get("PATH", "")
    proc = await asyncio.create_subprocess_exec(
        *ff_prefix(), sys.executable, str(LAUNCHER), "--dl", json.dumps(args),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env=env,
        **({"creationflags": 0x4000} if os.name == "nt" else {}))
    result = ({}, "The downloader stopped without an answer.")
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if m.get("t") == "p":
                if m.get("title"):
                    DL["title"] = m["title"]
                if m.get("pct") is not None:
                    DL["pct"] = m["pct"]
                DL["msg"] = m.get("msg") or DL["msg"]
            elif m.get("t") == "done":
                result = ({"_type": "playlist"} if m.get("playlist") else {}, m.get("err"))
        await proc.wait()
    finally:
        if proc.returncode is None:                   # cancelled, or the player is stopping: do not leave it running
            proc.kill()
            await proc.wait()
    return result


async def _dl_run(url, fmt, whole, folder):
    loop = asyncio.get_running_loop()
    codec, quality = DL_FORMATS.get(fmt, DL_FORMATS["flac"])
    tmp = LIB / "_downloading" / str(int(clock.time()))      # folders that start with _ are ignored by the library scan
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        info, err = await _dl_child(url, codec, quality, whole, tmp)
        got = sorted(f for f in tmp.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXT)
        if err or not got:
            DL.update(state="error", msg=err or "Nothing was downloaded from that link.", pct=0.0)
            return
        names, ids, free = [], [], storage_info(True)["allowance"]
        for f in got:
            sub = f.parent.relative_to(tmp).as_posix()
            sub = "/".join(_dl_clean(x) for x in sub.split("/")) if sub != "." else ""
            if sub == "NA":                          # a single video has no playlist title
                sub = ""
            rel_dir = f"{folder}/{sub}" if sub else folder
            if f.stat().st_size > free:
                DL.update(state="error", msg="Not enough space in the library for the rest of the download.")
                break
            mkdir_new(LIB / rel_dir)
            dest = unique_in_lib(f"{rel_dir}/{_dl_clean(f.stem)}{f.suffix.lower()}")
            size = f.stat().st_size
            dup = await loop.run_in_executor(None, find_duplicate, f, size)
            if dup:                                  # identical audio is already in the library
                names.append(Path(dup).stem)
                ids.append(dup)
                continue
            await loop.run_in_executor(None, shutil.move, str(f), str(dest))
            fid = dest.relative_to(LIB).as_posix()
            library[fid] = size
            parts = Path(fid).parent.parts
            for i in range(1, len(parts) + 1):
                LIBDIRS.add("/".join(parts[:i]))
            free -= size
            names.append(dest.stem)
            ids.append(fid)
        invalidate_storage()
        save()
        push(True)
        if DL["state"] != "error":
            note = ""
            if not whole and isinstance(info, dict) and info.get("_type") == "playlist":
                note = "That link is a playlist, so only its first track was saved. Tick Whole playlist to get them all."
            DL.update(state="done", pct=100.0, msg=f"Saved {len(names)} track{'s' if len(names) != 1 else ''} in the {folder} folder.",
                      files=names, ids=ids, note=note)
    except Exception as e:
        print("download:", e)
        DL.update(state="error", msg=str(e) or e.__class__.__name__, pct=0.0)
    finally:
        shutil.rmtree(LIB / "_downloading", ignore_errors=True)


async def h_dl_start(req):
    global _dl_task
    b = await body(req)
    url = str(b.get("url") or "").strip()
    if not re.match(r"^https?://\S+$", url, re.I):
        return web.json_response({"ok": False, "error": "Paste a full link that starts with http:// or https://"}, status=400)
    if ytdl_module() is None:
        return web.json_response({"ok": False, "error": "The downloader is not installed. On the player run: pip install -r requirements.txt, then restart it."}, status=501)
    if not ff_check():
        return web.json_response({"ok": False, "error": f"ffmpeg is needed to turn downloads into audio files, and {FF['err']}. Install it (sudo apt install ffmpeg) or set ffmpeg_path, then try again."}, status=501)
    if _dl_task and not _dl_task.done():
        return web.json_response({"ok": False, "error": "A download is already running. Wait for it to finish."}, status=409)
    info = storage_info(True)
    if info["allowance"] < 50 * 1048576:
        return web.json_response({"ok": False, "error": space_error(50 * 1048576, info)}, status=507)
    fmt = str(b.get("format") or CFG["download_format"]).lower()
    folder = _safe_rel(CFG["download_folder"], True) or "Downloads"
    DL.update(state="running", url=url, title="", pct=0.0, msg="Starting...", files=[], ids=[], folder=folder, note="")
    _dl_task = asyncio.create_task(_dl_run(url, fmt if fmt in DL_FORMATS else "flac", bool(b.get("playlist")), folder))
    return web.json_response({"ok": True})


async def h_dl_state(_):
    return web.json_response(DL)


async def h_dl_clear(_):
    if not (_dl_task and not _dl_task.done()):
        DL.update(state="idle", url="", title="", pct=0.0, msg="", files=[], ids=[], note="")
    return web.json_response({"ok": True})


async def h_upload(req):
    q = req.query.get("playlist")
    pidx = int(q) if q and is_uint(q) else None
    if pidx is not None and pidx >= len(playlists):
        return web.json_response({"ok": False, "error": "no such playlist"}, status=404)
    folder = ""
    if req.query.get("folder"):
        folder = _safe_rel(req.query["folder"], True)
        if not folder:
            return web.json_response({"ok": False, "error": "that folder name is not allowed"}, status=400)
    if not req.content_type.startswith("multipart/"):
        return web.json_response({"ok": False, "error": "send the file as multipart/form-data"}, status=400)
    reader = await req.multipart()
    results = []
    while True:
        try:
            part = await reader.next()
        except ValueError:                      # no multipart boundary in the body: not a file upload
            if results:
                save()
            return web.json_response({"ok": False, "error": "the body is not a valid multipart/form-data upload"}, status=400)
        if part is None:
            break
        if not part.filename:
            continue
        res = await save_upload(part, req.content_length, folder)
        if "error" in res:
            if results:
                save()
            return web.json_response({"ok": False, "error": res["error"]}, status=res["status"])
        results.append(res)
    if pidx is not None and results:
        add_to_playlist(pidx, [r["id"] for r in results])      # also saves
    else:
        save()
    push(True)
    return web.json_response({"ok": True, "files": results})


async def h_cmd(req):
    parts = [x for x in req.match_info["tail"].split("/") if x]
    q = req.query.get("ms")
    ms = int(q) if q and is_uint(q) else None
    return web.json_response({"result": command(parts, ms), **snapshot()})


# ---------------------------------------------------------------- main loop
async def ticker():
    last_full = clock.monotonic()
    last_err = 0.0
    last_health = 0.0
    while True:
        try:
            tick()
            if clock.monotonic() - last_health >= 1.0:
                last_health = clock.monotonic()
                ALERT.observe(health_report())      # the push messages need the state even when no browser is open
            if clock.monotonic() - last_full >= 5:
                last_full = clock.monotonic()
                push(True)           # resend everything every 5 s so Companion catches up if it
            else:                    # restarted, or a variable was created after the player started
                push()               # otherwise only values that changed
        except Exception:            # one bad tick (or an unreachable Companion) must not stop fades and auto-advance
            if clock.monotonic() - last_err > 10:
                last_err = clock.monotonic()
                import traceback
                traceback.print_exc()
        await asyncio.sleep(0.05)    # 50 ms keeps fades smooth


async def main():
    try:
        init_mixer(CFG["audio_device"])
    except Exception as e:                 # e.g. the Dante device isn't connected yet
        want = CFG["audio_device"]
        found = want in list_devices()
        print(f"Could not open output {want!r} ({e}); using system default. "
              + ("The device is listed but would not open." if found else "No current device has exactly that name (is the device running?)."))
        ISSUES["audio"] = f"could not open the saved output ({str(e)[:100]}); using the system default"
        DEV_MISSING["output"] = want       # kept in state.json, so the choice survives until another is made
        CFG["audio_device"] = None
        init_mixer(None)
    print("Audio devices:", list_devices(), "| using:", CFG["audio_device"] or "system default")
    load()
    _dur_load()
    _fmt_load()
    _info_load()
    durations(True)
    _loud_load()
    loudness.request_loudness()

    @web.middleware
    async def same_site_only(req, handler):
        """Refuse /api requests another website makes from the operator's browser (an <img>, link or form pointing at /api/stopall).
        Companion and the player's own page send no cross-site marker, so they are unaffected."""
        if req.headers.get("Sec-Fetch-Site") == "cross-site" and req.path.startswith("/api"):   # opening the page from a link elsewhere is fine
            return web.json_response({"ok": False, "error": "cross-site request refused"}, status=403)
        org = req.headers.get("Origin")
        if org and req.method != "GET" and org.split("://", 1)[-1] != req.host:
            return web.json_response({"ok": False, "error": "cross-site request refused"}, status=403)
        return await handler(req)

    app = web.Application(client_max_size=1024 ** 4, middlewares=[same_site_only])
    app.add_routes([
        web.get("/", h_ui),
        web.get("/variables", h_vars_page),
        web.get("/help", h_help_page),
        web.get("/stage", h_stage),
        web.get("/stage/", h_stage),
        web.get("/stage/{v}", h_stage),
        web.post("/api/restart", h_restart),
        web.get("/api/variables", h_vars),
        web.get("/api/state", h_state),
        web.get("/api/playlists", h_lists),
        web.post("/api/playlists", h_add_list),
        web.post("/api/playlists/reorder", h_pl_reorder),
        web.post("/api/playlists/{p}/rename", h_pl_rename),
        web.post("/api/playlists/{p}/trim", h_pl_trim),
        web.get("/api/playlists/{p}/triggers", h_pl_triggers_get),
        web.post("/api/playlists/{p}/triggers", h_pl_triggers),
        web.get("/api/triggers", h_triggers_get),
        web.post("/api/triggers/arm", h_triggers_arm),
        web.post("/api/triggers/skip", h_triggers_skip),
        web.get("/api/settings/folders", h_folders_get),
        web.post("/api/settings/folders", h_folders_set),
        web.post("/api/playlists/{p}/norm", h_pl_norm),
        web.delete("/api/playlists/{p}", h_del_list),
        web.post("/api/playlists/{p}/add", h_pl_add),
        web.delete("/api/playlists/{p}/{t}", h_pl_remove),
        web.get("/api/library", h_library),
        web.get("/api/library/file", h_lib_file),
        web.get("/api/library/info", h_lib_info),
        web.delete("/api/library", h_lib_delete),
        web.get("/api/ffmpeg", h_ffmpeg),
        web.get("/api/formats", h_formats),
        web.post("/api/library/rename", h_lib_rename),
        web.post("/api/library/folder", h_lib_mkdir),
        web.delete("/api/library/folder", h_lib_rmdir),
        web.post("/api/library/folder/color", h_lib_color),
        web.get("/api/library/folder/flags", h_lib_flags_get),
        web.post("/api/library/folder/flags", h_lib_flags),
        web.get("/api/waveform", h_waveform),
        web.post("/api/library/upload", h_upload),
        web.get("/api/storage", h_storage),
        web.get("/api/settings", h_get_settings),
        web.post("/api/settings", h_set_settings),
        web.post("/api/settings/prefix", h_prefix_set),
        web.post("/api/settings/companion/test", h_companion_test),
        web.get("/api/settings/warning", h_warn_get),
        web.post("/api/settings/warning", h_warn_set),
        web.get("/api/settings/health", h_health_get),
        web.get("/api/health/report", h_health_report),
        web.post("/api/settings/health", h_health_set),
        web.post("/api/settings/health/push-test", h_push_test),
        web.get("/api/settings/transition", h_tr_get),
        web.post("/api/settings/transition", h_tr_set),
        web.get("/api/input", h_input_get),
        web.post("/api/input", h_input_set),
        web.post("/api/input/solo", h_input_solo),
        web.post("/api/input/ducknow", h_input_ducknow),
        web.get("/api/settings/top", h_top_get),
        web.post("/api/settings/top", h_top_set),
        web.get("/api/devices", h_devices),
        web.get("/api/settings/outputs", h_outputs_get),
        web.post("/api/settings/outputs", h_outputs_set),
        web.get("/api/meters", h_meters),
        web.get("/api/live", h_live),
        web.get("/api/preview", h_pv_state),
        web.post("/api/preview/play", h_pv_play),
        web.post("/api/preview/ctl", h_pv_ctl),
        web.post("/api/preview/device", h_pv_device),
        web.post("/api/mirror/device", h_mirror_device),
        web.post("/api/mirror/enable", h_mirror_enable),
        web.post("/api/device", h_set_device),
        web.get("/api/scan", h_scan),
        web.get("/api/monitor", h_monitor),
        web.post("/api/download", h_dl_start),
        web.get("/api/download", h_dl_state),
        web.post("/api/download/clear", h_dl_clear),
        web.post("/api/move", h_move),
        web.get("/api/{tail:.*}", h_cmd),    # Companion HTTP: GET /api/0/1, /api/next ...
    ])
    if os.environ.get("CP_TEST_WATCHDOG"):                  # test hook, inert unless set
        app.add_routes([web.post("/api/test/stall", h_test_stall)])
    app.add_routes([web.post("/api/test/{tail:.*}", lambda req: web.Response(status=404, text="not found"))])      # hooks off (or unknown): a plain 404, not the catch-all GET's 405
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", CFG["http_port"]).start()

    disp = Dispatcher()
    disp.set_default_handler(osc_default)
    server = AsyncIOOSCUDPServer(("0.0.0.0", CFG["osc_in_port"]), disp, asyncio.get_running_loop())
    await server.create_serve_endpoint()

    print(f"UI  http://localhost:{CFG['http_port']}   OSC in :{CFG['osc_in_port']}   "
          f"variables out -> {CFG['companion_host']}:{CFG['companion_osc_port']} "
          f"(/custom-variable/{CFG['var_prefix']}<name>/value)")
    if preview.enabled():
        if CFG["preview_device"] in list_devices():
            preview.send({"cmd": "stop"})
        else:
            print(f"Preview output {CFG['preview_device']!r} not found; preview is off until you pick one in Settings")
    if mirror.enabled():
        if CFG["mirror_device"] in list_devices():
            mirror.send({"cmd": "stop"})
        else:
            print(f"Mirror output {CFG['mirror_device']!r} not found; the mirror is off until you pick one on the web page")
    lin.start()                            # the Live input: its ring, the detector loop and the capture helper (only when an input device is chosen)
    try_resume()
    push(True)
    S.boot_done = True
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):      # systemd stop / Ctrl-C: record the exact position first
        try:
            loop.add_signal_handler(sig, lambda: (save_resume(True), os._exit(0)))
        except (NotImplementedError, ValueError):
            pass
    await ticker()


def run():                  # called by the launcher (player.py)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
