#!/usr/bin/env python3
"""Golden audio fixtures: what the Python player does with sound, written as JSON for any other engine to match (docs/AUDIO-SPEC.md).

    PYTHONHASHSEED=0 python tests/golden-audio/generate.py            # check: regenerate in memory, compare with tests/golden-audio/fixtures/
    PYTHONHASHSEED=0 python tests/golden-audio/generate.py --write    # regenerate and overwrite the committed fixtures

Everything is measured from the real code (a copy of the app imported in-process, fake clock from cpl/clock.py, SDL dummy mixer): nothing here
changes the player. A fixture file is {"spec_version", "name", "about", "tolerance", "cases": {...}}; numbers are rounded to 6 decimals.
Keys that start with "_info" are explanatory and never compared. Every case carries a "scenario" object with the inputs it was built from
(written from the same variables that run the scenario); a case-level "tolerance" overrides the file-level one, and a case-level "tolerance_by_key" {key: tol} overrides both for the numbers under that key only.
"""
import asyncio
import json
import math
import os
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rig import Rig                                   # noqa: E402

SPEC_VERSION = 1                                      # docs/AUDIO-SPEC.md: bump it (and regenerate) whenever audio behaviour changes
FIXTURES = HERE / "fixtures"
END_TOL = 0.05                                        # one tick (the measured end is also on the 0.25 s sampling grid, which these ideal values sit on)
TRIG_TOL = 0.05                                       # one tick of the Python player: measured times are ideal + 0 .. 1 tick
SAMPLE_TOL = 2.5e-5                                   # s: just over one sample at 48 kHz (1/48000 = 2.083e-5), see tolerance_by_key


def SAMPLE_TOL_KEYS(keys):
    return {k: SAMPLE_TOL for k in keys}


TOL = 2e-6                                            # what the comparison allows (the files hold 6 decimals)
FRACS = [0.0, 0.125, 0.25, 0.5, 0.75, 0.875, 1.0]


def r6(x):
    return None if x is None else round(float(x), 6)


def doc(name, about, cases, **extra):
    d = {"spec_version": SPEC_VERSION, "name": name, "about": about, "tolerance": TOL}
    d.update(extra)
    d["cases"] = cases
    return d


# ------------------------------------------------------------------------------------------------ fades.json
async def fades():
    cases = {}
    cases["equal_power_formula"] = {"_info": "x = elapsed / fade length (0..1). A fade UP goes a + (b - a) * sin(x*pi/2); a fade DOWN goes b + (a - b) * cos(x*pi/2); new^2 + old^2 = 1 in a crossfade.",
                                    "scenario": {"x_values": [i / 16 for i in range(17)]},
                                    "rows": [{"x": f, "up": r6(math.sin(f * math.pi / 2)), "down": r6(math.cos(f * math.pi / 2))} for f in [i / 16 for i in range(17)]]}
    lib = {"a.wav": 12, "b.wav": 12}
    pls = [{"name": "A", "tracks": ["a.wav", "b.wav"]}]
    base = {"library_s": dict(lib), "playlist": pls[0]["tracks"], "sampled_at_fractions": FRACS}
    async with Rig(lib, pls) as r:
        await r.load("a.wav", "b.wav")
        for ms in (1000, 3000):
            r.reset()
            r.P.play(0, 0)
            old = r.live()
            r.rebase()
            r.P.play(0, 1, ms)
            new = r.live()
            rows = []
            for f in FRACS:
                r.at(f * ms / 1000.0)
                rows.append({"x": f, "t_s": r6(f * ms / 1000.0), "new": r6(new.vol), "old": r6(old.vol), "old_still_playing": old in r.P.decks})
            cases[f"crossfade_{ms}ms"] = {"scenario": dict(base, steps=["play track 0 (a.wav)", f"play track 1 (b.wav) with a {ms} ms crossfade at the same instant"], fade_ms=ms), "fade_ms": ms, "start": {"new": 0.0, "old": 1.0}, "rows": rows}
        r.reset()                                           # a zero-length crossfade is a cut
        r.P.play(0, 0)
        old = r.live()
        r.P.play(0, 1, 0)
        cases["crossfade_0ms_is_a_cut"] = {"scenario": dict(base, steps=["play track 0", "play track 1 with a 0 ms crossfade"], fade_ms=0), "new_vol": r6(r.live().vol), "old_removed": old not in r.P.decks, "decks": len(r.P.decks)}
        r.reset()                                           # fade out
        r.P.play(0, 0)
        d = r.live()
        r.rebase()
        out_ms = 2000
        r.P.fade_out(out_ms)
        rows = []
        for f in FRACS:
            r.at(f * out_ms / 1000.0)
            rows.append({"x": f, "vol": r6(d.vol), "playing": d in r.P.decks})
        cases["fade_out_2000ms"] = {"scenario": dict(base, steps=["play track 0", "fade_out at the same instant"], fade_ms=out_ms),
                                    "_info_live_after": "live_after true = nothing is live any more at the end of the fade", "rows": rows, "live_after": r.live() is None}
        r.reset()                                           # pause freezes a fade; the pause time is not counted
        r.P.play(0, 0)
        old = r.live()
        r.rebase()
        pause_fade_ms = 1000
        r.P.play(0, 1, pause_fade_ms)
        new = r.live()
        r.at(0.25)
        a = (r6(new.vol), r6(old.vol))
        r.P.pause_all()
        r.at(5.25)
        b = (r6(new.vol), r6(old.vol))
        r.P.resume_all()
        r.at(5.5)
        cases["pause_freezes_a_fade"] = {"scenario": dict(base, steps=["play track 0", "play track 1 with the crossfade", "t = 0.25 s: sample", "pause all", "t = 5.25 s: sample (5 s of pause)", "resume all", "t = 5.5 s: sample (0.25 s after resume)"],
                                                          fade_ms=pause_fade_ms, sample_1_at_s=0.25, sample_2_at_s=5.25, sample_3_at_s=5.5), "at_0_25": {"new": a[0], "old": a[1]}, "after_5s_pause": {"new": b[0], "old": b[1]},
                                         "0_25s_after_resume": {"new": r6(new.vol), "old": r6(old.vol)}}
    return doc("fades", "Gain of the decks during equal-power fades, read from Deck.vol at fixed fake-clock times (the mixer channel quantises to 128 steps; Deck.vol is the contract).", cases)


# ------------------------------------------------------------------------------------------------ xfade.json
async def xfade():
    cases = {}
    lib = {"a.wav": 12, "b.wav": 12}
    pls = [{"name": "A", "tracks": ["a.wav", "b.wav"]}]
    master_ms = 3000
    base = {"library_s": dict(lib), "playlist": pls[0]["tracks"], "target_track": 1, "master_crossfade_ms": master_ms}
    async with Rig(lib, pls, cfg={"crossfade_ms": master_ms, "default_transition": "crossfade"}) as r:
        P = r.P
        await r.load("a.wav", "b.wav")
        rows = []

        def row(label, ms=None):
            rows.append({"case": label, "explicit_ms": ms, "own_ms": P.xfade_of(0, 1), "master_ms": P.CFG["crossfade_ms"], "result_ms": P.xfade_ms(0, 1, ms)})
        row("master only")
        P.set_xfade(0, 1, 1.5)
        row("own time beats master")
        row("explicit beats own", 500)
        row("explicit 0 beats own", 0)
        P.set_xfade(0, 1, 0)
        row("own 0 is a cut, beats master")
        P.set_xfade(0, 1, None)
        row("cleared: master again")
        row("explicit beats master", 250)
        cases["precedence"] = {"scenario": dict(base, input="each row: the track's own time own_ms (null = not set), explicit_ms (the ?ms= value, null = none) and the master time, all in the row"), "_info": "result = explicit (?ms=) if given, else the track's own time if set (0 allowed), else the master crossfade_ms", "rows": rows}
        rows = []
        for secs in (0, 0.5, 30, 30.0004, 31, -1, "abc"):
            ok = P.set_xfade(0, 1, secs)
            rows.append({"seconds": secs, "accepted": bool(ok), "stored_ms": P.xfade_of(0, 1)})
            P.set_xfade(0, 1, None)
        cases["own_time_limits"] = {"scenario": dict(base, input="set_xfade(playlist 0, track 1, seconds) with each row's `seconds`, cleared again after every row"), "_info": "accepted 0..30 s, stored in whole ms", "rows": rows}
        out = []                                            # the length really used by Go / play_default with the crossfade transition
        pd_inputs = (("master", None), ("own 1.5 s", 1.5))
        for label, own in pd_inputs:
            r.reset(cfg={"crossfade_ms": master_ms})
            P.set_xfade(0, 1, own)
            P.play(0, 0)
            P.play_default(0, 1)
            out.append({"case": label, "fade_len_s": r6(r.live().fade["len"])})
        cases["play_default_uses_it"] = {"scenario": dict(base, default_transition="crossfade", steps=["play track 0", "play_default(playlist 0, track 1)"], row_inputs={lbl: {"own_time_s": own} for lbl, own in pd_inputs}), "rows": out}
    return doc("xfade", "Crossfade time precedence (explicit ?ms= > per-track > master crossfade_ms) and the fade length that play_default really starts.", cases)


# ------------------------------------------------------------------------------------------------ trim.json
async def trim():
    cases = {}
    lib = {"a.wav": 10, "b.wav": 12}
    tcfg = {"trim_fade_ms": 1500, "trim_fadein_ms": 0}
    base = {"library_s": dict(lib), "playlist": ["a.wav", "b.wav"], "track_under_test": 0, "file_length_s": 10.0, "config": tcfg}
    async with Rig(lib, [{"name": "A", "tracks": ["a.wav", "b.wav"]}], cfg=tcfg) as r:
        P = r.P
        await r.load("a.wav", "b.wav")
        rows = []
        for fields in ({}, {"in": 2, "out": 8}, {"in": 9.8}, {"in": 2.0, "out": 2.3}, {"out": 99}, {"in": 3.456, "out": 7.891}, {"in": 5, "out": 5.2, "end": "cut"},
                       {"out": 6, "fade_ms": 2500}, {"out": 6, "fade_ms": 50}, {"out": 6, "fade_ms": 20000}, {"in": 1, "start": "fade", "fade_in_ms": 800}, {"start": "fade"}, {"fade_in_ms": 900}):
            P.playlists[0].pop("trims", None)
            ok = P.set_trim(0, 0, fields)
            lo, hi, tm = P.trim_range(0, 0, 10.0)
            rows.append({"set": fields, "accepted": bool(ok), "stored": dict(P.trim_of(0, 0)), "range_s": [r6(lo), r6(hi)], "dur_eff_s": r6(P.dur_eff(0, 0)),
                         "fade_out_ms": P.fade_ms_of(0, 0), "fade_in_ms_eff": P.fade_in_ms_of(0, 0), "fade_in_applied_ms": P.fade_in_start_ms(0, 0)})
        P.playlists[0]["trims"] = {"a.wav": {"in": 2.0, "out": 2.3}}               # data that is already stored (an old file): trim_range ignores a window under 0.5 s
        raw_rows = [{"stored": {"in": 2.0, "out": 2.3}, "range_s": [r6(x) for x in P.trim_range(0, 0, 10.0)[:2]]}]
        P.playlists[0]["trims"] = {"a.wav": {"in": 12.0}}
        raw_rows.append({"stored": {"in": 12.0}, "range_s": [r6(x) for x in P.trim_range(0, 0, 10.0)[:2]]})
        P.playlists[0].pop("trims", None)
        cases["trim_range_of_stored_data"] = {"scenario": dict(base, input="the `stored` trim dict is written straight into playlists[0]['trims'] (an old file), then trim_range is read"), "_info": "file is 10 s; trim_range clamps stored values: A at most 0.5 s before the end; a window under 0.5 s falls back to the end of the file", "rows": raw_rows}
        cases["windows"] = {"scenario": dict(base, input="set_trim(playlist 0, track 0, row.set) from an empty trim for each row"), "_info": "file is 10 s. range_s = (A, B) in file seconds; set_trim REFUSES a window shorter than 0.5 s (accepted false, nothing stored); A is held 0.5 s before the end; fade_out_ms = own fade_ms else config trim_fade_ms (1500); the fade-in is applied only while start == 'fade'", "rows": rows}
        rows = []
        for label, trim_, offset in (("no trim", {}, 0.0), ("A and B, fade at B", {"in": 2, "out": 8, "end": "fade", "fade_ms": 1000}, 0.0), ("A and B, cut at B", {"in": 2, "out": 8, "end": "cut"}, 0.0),
                                     ("B only, default fade", {"out": 6}, 0.0), ("fade-in 1.5 s at A", {"in": 1, "out": 9, "start": "fade", "fade_in_ms": 1500}, 0.0),
                                     ("fade-in longer than the window", {"in": 1, "out": 3, "start": "fade", "fade_in_ms": 9000}, 0.0),
                                     ("resume part-way in (no fade-in)", {"in": 1, "out": 9, "start": "fade", "fade_in_ms": 1500}, 4.0)):
            r.reset()
            P.playlists[0].pop("trims", None)
            P.set_trim(0, 0, trim_)
            tr = P.track(0, 0)
            snd = await P.ensure_loaded(tr["path"])
            P._start(0, 0, tr, snd, 0, offset=offset)
            d = r.live()
            rows.append({"case": label, "trim": trim_, "offset": offset, "deck": {"base_s": r6(d.base), "lo_s": r6(d.lo), "hi_s": r6(d.hi), "duration_s": r6(d.duration), "end_fade_ms": d.end_fade_ms,
                                                                                   "fade_in_ms": d.fade_in_ms, "start_vol": r6(d.vol), "fresh": d.fresh}})
        cases["deck_start"] = {"scenario": dict(base, input="set_trim(row.trim), then _start(playlist 0, track 0, offset = row.offset seconds into the file); the deck is read right away"), "_info": "what _start sets on the Deck. base = where in the file the sound begins, duration = length of one pass of the window", "rows": rows}
        r.reset()                                           # the fade-out ahead of B
        P.playlists[0].pop("trims", None)
        ob_trim = {"out": 6, "end": "fade", "fade_ms": 2000}
        P.set_trim(0, 0, ob_trim)
        P.play(0, 0)
        d = r.live()
        r.rebase()
        rows = []
        ob_times, ob_end_check = (0, 3.5, 3.9375, 4.0, 4.25, 4.5, 5.0, 5.5, 5.75, 5.9375), 6.25
        for t in ob_times:
            r.at(t)
            rows.append({"t_s": t, "vol": r6(d.vol), "fading": d.fade is not None})
        r.at(ob_end_check)
        cases["fade_out_ahead_of_B"] = {"scenario": dict(base, trim=ob_trim, steps=["play track 0 from the start"], sampled_at_s=list(ob_times), ended_check_at_s=ob_end_check),
                                    "_info_live_after": "live_after true = nothing is live at ended_check_at_s (6.25 s)", "_info": "window 0..6 s, fade_ms 2000: the fade (cos) starts when 2 s are left and ends at B; then the track ends by itself", "rows": rows, "ended": d not in P.decks, "live_after": r.live() is None}
        r.reset()                                           # fade-in at A
        P.playlists[0].pop("trims", None)
        fi_trim = {"in": 2, "start": "fade", "fade_in_ms": 1500}
        P.set_trim(0, 0, fi_trim)
        P.play(0, 0)
        d = r.live()
        r.rebase()
        rows = []
        for f in FRACS:
            r.at(f * fi_trim["fade_in_ms"] / 1000.0)
            rows.append({"x": f, "vol": r6(d.vol)})
        cases["fade_in_at_A"] = {"scenario": dict(base, trim=fi_trim, steps=["play track 0 from the start"], sampled_at_fractions=FRACS), "_info": "fade_in_ms 1500: sin(x*pi/2) up to full level", "rows": rows}
    cases.update(await trim_boundaries())
    return doc("trim", "Trim windows (A/B), fade-in at A, fade or cut at B: what set_trim stores, what _start sets on the deck, and the gain curve near B.", cases)


# Boundary cases (added to Audio spec 1, no change of behaviour): both sides of every threshold of the trim rules.
async def _deck_for(r, t, trim_, end="default", offset=0.0, xfade_ms=0, paused=False, raw=False):
    """Start track t of playlist 0 with a trim (through set_trim, or written straight into `trims` when raw) and return its deck (clock rebased)."""
    P = r.P
    r.reset()
    fid = P.playlists[0]["tracks"][t]
    ok = True
    if raw:
        P.playlists[0]["trims"] = {fid: dict(trim_)}
    else:
        ok = P.set_trim(0, t, trim_)
    if end != "default":
        P.set_end(0, t, end)
    tr = P.track(0, t)
    snd = await P.ensure_loaded(tr["path"])
    P._start(0, t, tr, snd, xfade_ms, offset=offset, paused=paused)
    d = r.live()
    r.rebase()
    return ok, d


def _deck_row(d):
    return {"base_s": r6(d.base), "lo_s": r6(d.lo), "hi_s": r6(d.hi), "duration_s": r6(d.duration), "end_fade_ms": d.end_fade_ms, "fade_in_ms": d.fade_in_ms,
            "fade_in_ramp_s": r6(d.fade["len"]) if d.fade and d.fade["b"] >= d.fade["a"] and d.fade_in_ms else None,
            "start_vol": r6(d.vol), "fresh": d.fresh, "loop": d.loop, "passes": d.passes}


def _set_row(P, t, fields, full=None):
    ok = P.set_trim(0, t, fields)
    lo, hi, _tm = P.trim_range(0, t, full or P.DURS[P.playlists[0]["tracks"][t]][2])
    return {"set": fields, "accepted": bool(ok), "stored": dict(P.trim_of(0, t)), "range_s": [r6(lo), r6(hi)]}


async def trim_boundaries():
    cases = {}
    lib = {"a.wav": 10, "c.wav": 30, "e.wav": 10.004}
    tcfg = {"trim_fade_ms": 1500, "trim_fadein_ms": 0}
    names = ["a.wav", "c.wav", "e.wav"]
    base = {"library_s": dict(lib), "playlist": names, "config": tcfg}
    async with Rig(lib, [{"name": "A", "tracks": names}], cfg=tcfg) as r:
        P = r.P
        for n in names:
            await r.load(n)

        # ---- 1. a stored window that is too short
        rows = []
        for fields in ({"in": 2.0, "out": 2.49}, {"in": 2.0, "out": 2.5}, {"in": 2.0, "out": 2.51}, {"in": 5.0, "out": 5.49}, {"in": 5.0, "out": 5.5}, {"in": 5.0, "out": 3.0},
                       {"in": 9.4, "out": 9.8}, {"in": 9.5, "out": 9.9}, {"in": 9.49}, {"in": 9.5}, {"in": 9.51}, {"in": 9.8, "out": 9.95}, {"out": 0.49}, {"out": 0.5}, {"out": 0.0}):
            ok, d = await _deck_for(r, 0, fields, raw=True)
            lo, hi, _ = P.trim_range(0, 0, 10.0)
            rows.append({"stored": fields, "range_s": [r6(lo), r6(hi)], "dur_eff_s": r6(P.dur_eff(0, 0)), "deck": {k: v for k, v in _deck_row(d).items() if k in ("base_s", "lo_s", "hi_s", "duration_s", "end_fade_ms")}})
        cases["short_window_stored"] = {"scenario": dict(base, track_under_test=0, file_length_s=10.0, input="each `stored` trim dict is written straight into playlists[0]['trims'] (old data; set_trim would refuse some of them), then trim_range, dur_eff and _start (from the start) are read"),
                                        "_info": "file is 10 s. trim_range: A is first held to at most file - 0.5 s; then, when B < A + 0.5 (B missing counts as the end), B BECOMES THE END OF THE FILE and A is KEPT (so [2.0, 10.0], not the whole file). Exactly 0.5 s is long enough. A fallen-back window has no out-fade (hi = end of file)",
                                        "tolerance_by_key": SAMPLE_TOL_KEYS(["base_s", "lo_s", "hi_s", "duration_s", "dur_eff_s", "range_s"]),
                                        "_info_tolerance_by_key": "positions and durations in file seconds are compared within one sample (2.5e-5 s): Deck.duration is sound.get_length() of the cut Sound, whose frame range is [int(lo * 48000), int(hi * 48000)), so In 2.0 / Out 2.51 gives 24479 samples = 0.509979 s (int(2.51 * 48000) = 120479 in floating point), while hi_s, range_s and dur_eff_s are the exact float seconds (2.51, 0.51); a whole-frame engine gets 0.51 for the duration", "rows": rows}

        # ---- 2. rounding, what is not stored, the 0.5 s rule of set_trim
        rows = []
        for fields in ({"in": 0.0}, {"in": 0.004}, {"in": 0.01}, {"in": 0.014}, {"in": 0.016}, {"in": 0.02}, {"in": 3.454}, {"in": 3.456},
                       {"out": 9.98}, {"out": 9.99}, {"out": 10.0}, {"out": 10.5}):
            P.playlists[0].pop("trims", None)
            rows.append(_set_row(P, 0, fields, 10.0))
        cases["set_trim_rounding_a_b"] = {"scenario": dict(base, track_under_test=0, file_length_s=10.0, input="set_trim(playlist 0, track 0, row.set) from an empty trim for each row"),
                                          "_info": "values are rounded to 0.01 s (round(v, 2)). An In that is <= 0.01 s after rounding is not stored (so 0.01 is dropped and 0.02 is the smallest stored In); an Out that is >= file length - 0.01 s after rounding is not stored; an Out past the end is first clipped to the file length (and then dropped)", "rows": rows}
        rows = []
        for fields in ({"in": 2.0, "out": 2.49}, {"in": 2.0, "out": 2.5}, {"in": 2.0, "out": 2.51}, {"in": 2.0, "out": 2.3}, {"in": 4.0, "out": 4.5}, {"in": 2.004, "out": 2.496}, {"in": 2.004, "out": 2.494}):
            P.playlists[0].pop("trims", None)
            rows.append(_set_row(P, 0, fields, 10.0))
        P.playlists[0].pop("trims", None)
        P.set_trim(0, 0, {"in": 1.0, "out": 5.0})                                           # a refused change leaves what was stored
        keep = _set_row(P, 0, {"out": 1.2}, 10.0)
        keep["previous"] = {"in": 1.0, "out": 5.0}
        rows.append(keep)
        for fields in ({"out": 0.3}, {"out": 0.5}):                                       # B alone is never compared with A
            P.playlists[0].pop("trims", None)
            rows.append(_set_row(P, 0, fields, 10.0))
        cases["set_trim_minimum_window"] = {"scenario": dict(base, track_under_test=0, file_length_s=10.0, input="set_trim(row.set) from an empty trim (the row with `previous` starts from {in 1.0, out 5.0})"),
                                            "_info": "the window is checked AFTER rounding and only when both A and B are stored: B < A + 0.5 is refused (accepted false, nothing changes), exactly 0.5 s is accepted. B alone (no A) is accepted whatever it is, but a stored B under 0.5 s then falls back to the end of the file when played (see short_window_stored); range_s shows that", "rows": rows}
        rows = []
        for fields in ({"out": 9.98}, {"out": 9.99}, {"out": 9.995}, {"out": 10.0}, {"out": 10.004}, {"out": 10.5}):
            P.playlists[0].pop("trims", None)
            rows.append(_set_row(P, 2, fields, 10.004))
        cases["set_trim_out_vs_file_length"] = {"scenario": dict(base, track_under_test=2, file_length_s=10.004, input="set_trim(playlist 0, track 2, row.set) from an empty trim; the file is 10.004 s"),
                                                "_info": "the Out is compared with the file length itself, not with a rounded length: Out >= 10.004 - 0.01 (= 9.994) is dropped, so 9.99 is stored here but was dropped for a file of exactly 10 s; an Out past the end is clipped to the length rounded to 0.01 s (10.0)", "rows": rows}

        # ---- 3. fade length limits (file c.wav, 30 s, track 1)
        rows = []
        for key, start in (("fade_ms", None), ("fade_in_ms", "fade")):
            for v in (99, 99.4, 99.6, 100, 10000, 10000.4, 10000.6, 10001):
                P.playlists[0].pop("trims", None)
                f = {"out": 20, key: v}
                if start:
                    f["start"] = start
                rows.append(_set_row(P, 1, f, 30.0))
        cases["fade_length_limits"] = {"scenario": dict(base, track_under_test=1, file_length_s=30.0, input="set_trim(playlist 0, track 1, {out 20, fade_ms or fade_in_ms = value}) from an empty trim; the window (20 s) is longer than every value"),
                                       "_info": "both lengths are rounded to whole ms and must be 100..10000 ms (inclusive): outside that set_trim refuses everything in the call (accepted false, nothing stored). 99.4 rounds to 99 (refused), 99.6 to 100 (accepted)", "rows": rows}
        rows = []
        for fields in ({"out": 3, "fade_ms": 5000}, {"in": 2, "out": 3, "fade_ms": 5000, "start": "fade", "fade_in_ms": 5000}, {"in": 2, "out": 2.5, "fade_ms": 5000, "start": "fade", "fade_in_ms": 5000},
                       {"in": 2, "out": 2.5, "fade_ms": 100, "start": "fade", "fade_in_ms": 100}, {"fade_ms": 2000}, {"in": 29, "start": "fade", "fade_in_ms": 5000},
                       {"in": 25, "start": "fade", "fade_in_ms": 10000}, {"start": "fade", "fade_in_ms": 10000}, {"start": "fade", "fade_in_ms": 20000}, {"out": 3, "fade_ms": 5000, "end": "cut"}):
            P.playlists[0].pop("trims", None)
            rows.append(_set_row(P, 1, fields, 30.0))
        cases["fade_length_held_to_window"] = {"scenario": dict(base, track_under_test=1, file_length_s=30.0, input="set_trim(playlist 0, track 1, row.set) from an empty trim for each row"),
                                               "_info": "a fade length is held to the part that plays (B - A; the fade-in with no B: the rest of the file) but never below 100 ms; a fade length with no B is dropped (it belongs to B); the length is kept while the edge is Cut (end cut / start absent)", "rows": rows}
        rows = []
        P.playlists[0].pop("trims", None)
        for fields in ({"out": 3, "fade_ms": 5000}, {"out": 20}, {"in": 1}, {"out": 20, "fade_ms": 5000}, {"out": 3}, {"out": None}):
            rows.append(_set_row(P, 1, fields, 30.0))
        cases["fade_length_follows_window_changes"] = {"scenario": dict(base, track_under_test=1, file_length_s=30.0, input="set_trim(playlist 0, track 1, row.set) one after the other WITHOUT clearing between rows (each row changes what the previous one left)"),
                                                       "_info": "a stored fade length is re-clamped whenever the window shrinks, and never grows back when the window is widened again (row 2); removing B drops the fade length (last row)", "rows": rows}

        # the default fade at B is not stored, so it can be longer than the window: it is then held to the played part when it runs
        ok, d = await _deck_for(r, 0, {"in": 2, "out": 3})
        step = 0.125
        samples = []
        for i in range(0, 9):
            r.at(i * step)
            samples.append({"t_s": i * step, "vol": r6(d.vol), "live": d in P.decks})
        cases["default_fade_longer_than_window"] = {"scenario": dict(base, track_under_test=0, file_length_s=10.0, trim={"in": 2, "out": 3}, steps=["play track 0 from the start"], tick_step_s=step, sampled_at_s=[x["t_s"] for x in samples]),
                                                    "_info": "window [2, 3] (1 s) with the default 1500 ms fade (trim_fade_ms): the deck is started with end_fade_ms 1500, but Deck.update holds the fade to the length of one pass, so it starts at once (t = 0) and runs the whole window", "deck": {"end_fade_ms": d.end_fade_ms, "fade_ms_eff": P.fade_ms_of(0, 0)}, "rows": samples}

        # ---- 4. where the out-fade runs
        base4 = dict(base, track_under_test=0, file_length_s=10.0, trim={"out": 4, "fade_ms": 1000}, tick_step_s=0.25)
        sample_times = [0.0, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 6.75, 7.0, 7.25, 7.5, 7.75, 8.0, 8.25]

        async def outfade_case(end, switch=None, run_s=9.5):
            ok, d = await _deck_for(r, 0, {"out": 4, "fade_ms": 1000}, end=end)
            rows, ended = [], None
            steps = int(run_s / 0.25)
            for i in range(0, steps + 1):
                t = i * 0.25
                if switch and t == switch[0]:
                    P.set_end(0, 0, switch[1])
                r.at(t)
                if ended is None and d not in P.decks:
                    ended = t
                if t in sample_times:
                    rows.append({"t_s": t, "vol": r6(d.vol), "live": d in P.decks})
            return d, rows, ended
        for end, ideal_end, info in (("loop", None, "a looping deck never ends and never out-fades (vol stays 1 through every lap)"),
                                     ("once", 8.0, "two passes of the 4 s window: no fade in pass 1, the out-fade only in pass 2 (7 s .. 8 s), then it ends"),
                                     ("default", 4.0, "out-fade over the last second of the window (3 s .. 4 s), then it ends"),
                                     ("stop", 4.0, "same as default: stop only decides what follows")):
            d, rows, ended = await outfade_case(end)
            assert (ended is None) == (ideal_end is None) and (ended is None or 0 <= ended - ideal_end <= END_TOL + 1e-6)
            cases[f"out_fade_placement_{end}"] = {"scenario": dict(base4, end_action=end, steps=[f"set_end(0, 0, {end!r})", "play track 0", "tick every 0.25 s until 9.5 s"], sampled_at_s=list(sample_times)),
                                                  "_info": "window [0, 4], fade_ms 1000. The out-fade runs only in the LAST pass of a deck that ends; " + info, "ended_at_s": ended, "ideal_ended_at_s": ideal_end, "tolerance_s": END_TOL, "rows": rows}
        d, rows, ended = await outfade_case("once", switch=(1.0, "default"), run_s=6.0)
        assert ended is not None and 0 <= ended - 4.0 <= END_TOL + 1e-6
        cases["out_fade_once_switched_off_in_pass_1"] = {"scenario": dict(base4, end_action="once", switch_off_to="default", switch_off_at_s=1.0, steps=["set_end(0, 0, 'once')", "play track 0", "set_end(0, 0, 'default') at 1.0 s", "tick every 0.25 s until 6.0 s"], sampled_at_s=list(sample_times)),
                                                         "_info": "once switched off in pass 1: that pass becomes the last one, so the out-fade runs at its end (3 s .. 4 s) and the deck ends at 4 s", "ended_at_s": ended, "ideal_ended_at_s": 4.0, "tolerance_s": END_TOL, "rows": [x for x in rows if x["t_s"] <= 8.25]}
        d, rows, ended = await outfade_case("loop", switch=(1.0, "default"), run_s=6.0)
        assert ended is not None and 0 <= ended - 4.0 <= END_TOL + 1e-6
        cases["loop_switched_off_in_pass_1_end"] = {"scenario": dict(base4, end_action="loop", switch_off_to="default", switch_off_at_s=1.0, steps=["set_end(0, 0, 'loop')", "play track 0", "set_end(0, 0, 'default') at 1.0 s", "tick every 0.25 s until 6.0 s"]),
                                                    "_info": "loop switched off in pass 1: the running pass is played out and the deck ends at B (4 s). ONLY THE END IS CONTRACT. What the level does in that last pass is a Python quirk (AUDIO-SPEC quirk 10): the deck was started looping, so Python never out-fades it and it stops dead at B; the ideal (a port may do it) is the out-fade 3 s .. 4 s like the default case. The measured levels are in _info_python_vol.",
                                                    "ended_at_s": ended, "ideal_ended_at_s": 4.0, "tolerance_s": END_TOL, "_info_python_vol": [x for x in rows if x["t_s"] <= 4.25]}

        # ---- 5. when a start counts as "at A"
        rows = []
        P.playlists[0].pop("end_actions", None)
        for label, trim_, offs in (("A = 2 s, B = 8 s", {"in": 2, "out": 8, "start": "fade", "fade_in_ms": 1000}, (0.0, 0.05, 0.0501, 0.06, 1.9, 2.0, 2.04, 2.05, 2.06, 2.2)),
                                   ("A = 0 (no In), B = 8 s", {"out": 8, "start": "fade", "fade_in_ms": 1000}, (0.0, 0.05, 0.0501, 0.0599, 0.06, 0.07))):
            for off in offs:
                ok, d = await _deck_for(r, 0, trim_, end="loop", offset=off)
                row = _deck_row(d)
                rows.append({"case": label, "trim": trim_, "offset_s": off, "deck": {k: row[k] for k in ("base_s", "fade_in_ms", "start_vol", "fresh", "loop")}})
        for label, kw in (("paused start", {"paused": True}), ("start under a crossfade (500 ms)", {"xfade_ms": 500})):
            ok, d = await _deck_for(r, 0, {"in": 2, "out": 8, "start": "fade", "fade_in_ms": 1000}, end="loop", **kw)
            row = _deck_row(d)
            rows.append({"case": label, "trim": {"in": 2, "out": 8, "start": "fade", "fade_in_ms": 1000}, "offset_s": 0.0, "deck": {k: row[k] for k in ("base_s", "fade_in_ms", "start_vol", "fresh", "loop")}, "crossfade_ms": kw.get("xfade_ms", 0), "paused": bool(kw.get("paused"))})
        cases["fade_in_start_threshold"] = {"scenario": dict(base, track_under_test=0, file_length_s=10.0, end_action="loop", input="set_trim(row.trim), set_end(0, 0, 'loop'), then _start(playlist 0, track 0, offset = row.offset_s [, paused / crossfade_ms]); the deck is read right away"),
                                            "_info": "TWO thresholds, both on `offset` = the position handed to _start, in FILE seconds (not relative to A). (1) fade-in: applied only when offset <= 0.05 s (0.05 yes, 0.0501 no), not paused and not under a crossfade; a start at offset = A itself (2.0 here) is a part-way start and does NOT fade in. (2) deck.fresh (the loop / once / trigger gate, 'at the In point'): |start - A| < 0.06 s where start = A for offset <= 0.05 else max(A, offset); 2.05 is fresh, 2.06 is not (0.0599 / 0.06 with A = 0). base_s = where the sound begins: offsets below A start at A",
            "tolerance_by_key": SAMPLE_TOL_KEYS(["base_s", "offset_s"]),
            "_info_tolerance_by_key": "base_s is the exact float offset handed to _start (max(A, offset): 0.0501, 0.0599 with A = 0), not a frame count; 0.0501 s is 2404.8 samples, so a whole-frame engine differs by up to 4.2e-6 s. offset_s is the input itself (same value)", "rows": rows}

        # ---- 6. the fade-in is capped to the window minus the out-fade
        rows = []
        for label, trim_ in (("out-fade 1500, fade-in 2499", {"in": 0, "out": 4, "fade_ms": 1500, "start": "fade", "fade_in_ms": 2499}), ("out-fade 1500, fade-in 2500", {"in": 0, "out": 4, "fade_ms": 1500, "start": "fade", "fade_in_ms": 2500}),
                             ("out-fade 1500, fade-in 2501", {"in": 0, "out": 4, "fade_ms": 1500, "start": "fade", "fade_in_ms": 2501}), ("out-fade 1500, fade-in 3000", {"in": 0, "out": 4, "fade_ms": 1500, "start": "fade", "fade_in_ms": 3000}),
                             ("1 s window, out-fade 800, fade-in 500", {"in": 1, "out": 2, "fade_ms": 800, "start": "fade", "fade_in_ms": 500}), ("1 s window, out-fade 900, fade-in 500 (100 ms left)", {"in": 1, "out": 2, "fade_ms": 900, "start": "fade", "fade_in_ms": 500}),
                             ("1 s window, out-fade 901, fade-in 500 (99 ms left)", {"in": 1, "out": 2, "fade_ms": 901, "start": "fade", "fade_in_ms": 500}), ("1 s window, out-fade 1000, fade-in 500 (nothing left)", {"in": 1, "out": 2, "fade_ms": 1000, "start": "fade", "fade_in_ms": 500}),
                             ("1 s window, out-fade 1000, fade-in 1000", {"in": 1, "out": 2, "fade_ms": 1000, "start": "fade", "fade_in_ms": 1000}), ("1 s window, default out-fade (1500), fade-in 900", {"in": 1, "out": 2, "start": "fade", "fade_in_ms": 900}),
                             ("Out is Cut (no out-fade), 0.5 s window, fade-in 500", {"in": 1, "out": 1.5, "end": "cut", "start": "fade", "fade_in_ms": 500}), ("no Out (no out-fade), fade-in 900", {"in": 1, "start": "fade", "fade_in_ms": 900})):
            ok, d = await _deck_for(r, 0, trim_)
            row = _deck_row(d)
            rows.append({"case": label, "set": trim_, "accepted": bool(ok), "stored": dict(P.trim_of(0, 0)), "window_s": r6(d.hi - d.lo), "deck": {k: row[k] for k in ("end_fade_ms", "fade_in_ms", "fade_in_ramp_s")}})
        cases["fade_in_cap"] = {"scenario": dict(base, track_under_test=0, file_length_s=10.0, input="set_trim(row.set), then _start from the start (offset 0); the deck is read right away"),
                                "_info": "fade_in_ms of the deck = min(stored fade-in, window - out-fade) when that is >= 100 ms (inclusive: 100 left is kept, 99 left is not); otherwise it is min(stored fade-in, window) and the out-fade is NOT shortened (they then overlap: see fade_in_out_fade_overlap). end_fade_ms is 0 for a Cut at B or no B; the default out-fade (trim_fade_ms 1500) counts even when longer than the window", "rows": rows}
        step = 0.125
        for label, trim_ in (("fade-in 500 + out-fade 901 in a 1 s window", {"in": 1, "out": 2, "fade_ms": 901, "start": "fade", "fade_in_ms": 500}), ("fade-in 1000 + out-fade 1000 in a 1 s window", {"in": 1, "out": 2, "fade_ms": 1000, "start": "fade", "fade_in_ms": 1000})):
            ok, d = await _deck_for(r, 0, trim_)
            vols = []
            for i in range(0, 10):
                r.at(i * step)
                vols.append({"t_s": i * step, "vol": r6(d.vol), "live": d in P.decks})
            cases["fade_in_out_fade_overlap_" + ("901" if "901" in label else "1000")] = {"scenario": dict(base, track_under_test=0, file_length_s=10.0, trim=trim_, tick_step_s=step, steps=["play track 0 from the start"]),
                                                                                           "_info": "Only the deck values are contract (the fade-in keeps its whole length, the out-fade is not shortened). What the level does while they overlap is Python's (AUDIO-SPEC quirk 11, in _info_python_vol, not compared): the out-fade cannot start while another fade is running, so it starts at the first tick after the fade-in ends and runs over what is left (901: from 0.5 s, 0.5 s long; 1000: never, the deck ends at full level at B). A port may multiply the two envelopes instead.",
                                                                                           "deck": {"end_fade_ms": d.end_fade_ms, "fade_in_ms": d.fade_in_ms}, "_info_python_vol": vols}
    return cases


# ------------------------------------------------------------------------------------------------ end_actions.json
async def end_actions():
    cases = {}
    lib = {"a.wav": 2}
    stamps = (0.0, 1.0, 1.75, 2.0, 2.25, 3.75, 4.0, 4.25, 6.0, 9.0)
    step_s, run_s = 0.25, 9.0
    base = {"library_s": dict(lib), "playlist": ["a.wav"], "play_mode": "stop", "tick_step_s": step_s}
    once_off_s, loop_off_s = 1.0, 3.0

    def timeline(r, secs, step=0.25, actions=None):
        d0 = r.live()
        rows, ended = [], None
        for i in range(1, int(secs / step) + 1):
            r.fake.t += step
            if actions and (round(i * step, 6) in actions):
                actions[round(i * step, 6)]()
            r.P.tick()
            t = round(i * step, 6)
            d = r.live()
            if d is None and ended is None:
                ended = t
            if t in stamps:
                rows.append({"t_s": t, "live": d is not None, "pass_no": d.pass_no() if d else None, "remaining_s": r6(d.remaining()) if d else None})
        return rows, ended, d0

    async with Rig(lib, [{"name": "A", "tracks": ["a.wav"], "mode": "stop"}]) as r:
        await r.load("a.wav")
        for end in ("default", "once", "loop", "stop"):
            r.reset([{"name": "A", "tracks": ["a.wav"], "mode": "stop"}])
            r.P.set_end(0, 0, end)
            r.P.play(0, 0)
            d = r.live()
            first = {"passes": d.passes, "loop": d.loop}
            rows, ended, _ = timeline(r, run_s)
            ideal_end = {"default": 2.0, "once": 4.0, "loop": None, "stop": 2.0}[end]
            assert (ended is None) == (ideal_end is None) and (ended is None or 0 <= ended - ideal_end <= END_TOL + 1e-6)
            cases[f"track_2s_end_{end}"] = {"scenario": dict(base, end_action=end, run_s=run_s, steps=["set_end(0, 0, end_action)", "play track 0", f"tick every {step_s} s for {run_s} s"]), "rows_at_s": [x["t_s"] for x in rows], "_info": "2 s track, playlist mode stop; ticks every 0.25 s from the start (so ended_at_s is on that 0.25 s grid, and ideal_ended_at_s is the end of the last pass). passes: 2 for once; loop = started with loops=-1", "deck_at_start": first, "ended_at_s": ended, "ideal_ended_at_s": ideal_end, "tolerance_s": END_TOL, "rows": rows}
        r.reset([{"name": "A", "tracks": ["a.wav"], "mode": "stop"}])
        r.P.set_end(0, 0, "once")
        r.P.play(0, 0)
        rows, ended, _ = timeline(r, 6.0, actions={once_off_s: lambda: r.P.set_end(0, 0, "default")})
        cases["once_switched_off_in_pass_1"] = {"scenario": dict(base, end_action="once", switch_off_to="default", switch_off_at_s=once_off_s, run_s=6.0), "_info": "end action set back to default at 1.0 s: the pass that is running is played out, then it ends", "ended_at_s": ended, "ideal_ended_at_s": 2.0, "tolerance_s": END_TOL, "rows_at_s": [x["t_s"] for x in rows], "rows": rows}
        assert 0 <= ended - 2.0 <= END_TOL + 1e-6
        r.reset([{"name": "A", "tracks": ["a.wav"], "mode": "stop"}])
        r.P.set_end(0, 0, "loop")
        r.P.play(0, 0)
        rows, ended, _ = timeline(r, 6.0, actions={loop_off_s: lambda: r.P.set_end(0, 0, "default")})
        cases["loop_switched_off_in_pass_2"] = {"scenario": dict(base, end_action="loop", switch_off_to="default", switch_off_at_s=loop_off_s, run_s=6.0), "_info": "end action set back to default at 3.0 s (pass 2 running): that pass is played out, then it ends", "ended_at_s": ended, "ideal_ended_at_s": 4.0, "tolerance_s": END_TOL, "rows_at_s": [x["t_s"] for x in rows], "rows": rows}
        assert 0 <= ended - 4.0 <= END_TOL + 1e-6
        r.reset([{"name": "A", "tracks": ["a.wav"], "mode": "stop"}])
        order = []
        for _ in range(8):
            order.append(r.P.end_of(0, 0))
            r.P.set_end(0, 0)
        cases["end_action_cycle"] = {"scenario": {"playlist": ["a.wav"], "input": "set_end(0, 0) with no value, 8 times; sequence[0] is the value before the first call"}, "_info": "set_end with no value cycles default > once > loop > stop", "sequence": order}
    cases.update(await end_action_switching())
    return doc("end_actions", "Per-track end actions: pass counts, remaining time per pass and the moment the track ends (fake clock, 0.25 s steps).", cases)


# Switching an end action while the track is playing (added to Audio spec 1, no change of behaviour).
async def end_action_switching():
    lib = {"a.wav": 2, "b.wav": 2}
    step_s, run_s = 0.25, 9.0
    names = ["a.wav", "b.wav"]
    # (from, to, switch at s): every pair that is deliberate. "to once" is NOT pinned: see AUDIO-SPEC quirk 12.
    pairs = [("default", "loop", 1.0), ("default", "stop", 1.0), ("stop", "default", 1.0), ("stop", "loop", 1.0),
             ("once", "default", 1.0), ("once", "default", 3.0), ("once", "loop", 1.0), ("once", "loop", 3.0), ("once", "stop", 1.0), ("once", "stop", 3.0),
             ("loop", "default", 1.0), ("loop", "default", 3.0), ("loop", "stop", 1.0), ("loop", "stop", 3.0)]
    rows = []
    async with Rig(lib, [{"name": "A", "tracks": names, "mode": "stop"}]) as r:
        await r.load(*names)
        for frm, to, at in pairs:
            row = {"from": frm, "to": to, "switch_at_s": at, "ideal_ended_at_s": 2.0 if at < 2.0 else 4.0}
            for mode in ("stop", "loop_playlist"):
                r.reset([{"name": "A", "tracks": names, "mode": mode}])
                r.P.set_end(0, 0, frm)
                r.P.play(0, 0)
                d0 = r.live()
                ended, after = None, None
                for i in range(1, int(run_s / step_s) + 1):
                    r.fake.t += step_s
                    t = round(i * step_s, 6)
                    if t == at:
                        r.P.set_end(0, 0, to)
                    r.P.tick()
                    if ended is None and d0 not in r.P.decks:
                        ended = t
                        d = r.live()
                        after = {"track": d.pt[1], "pass_no": d.pass_no()} if d else None
                assert ended is not None and 0 <= ended - row["ideal_ended_at_s"] <= END_TOL + 1e-6, (frm, to, at, ended)
                row[f"play_mode_{mode}"] = {"ended_at_s": ended, "live_at_that_tick": after}
            rows.append(row)
    return {"end_action_switched_mid_play": {
        "scenario": {"library_s": dict(lib), "playlist": names, "play_modes": ["stop", "loop_playlist"], "tick_step_s": step_s, "run_s": run_s,
                     "steps": ["set_end(0, 0, from)", "play track 0 (2 s)", "set_end(0, 0, to) at switch_at_s of play", f"tick every {step_s} s; ended_at_s = first tick where that deck is gone; live_at_that_tick = what is live after that same tick (track index and pass_no, or null)"],
                     "row_inputs": "from / to / switch_at_s; each row is run once with the playlist mode stop and once with loop_playlist (2 tracks)"},
        "_info": "the pass that is running is always played out; the NEW action then decides what follows: default = the playlist mode (stop: nothing, loop_playlist: track 1), stop = nothing, loop = track 0 starts again (a restart: Python has a gap there, quirk 7; a port may loop seamlessly), and once / loop switched to something else ends after the RUNNING pass (a switched-off once in pass 1 ends after pass 1). ideal_ended_at_s = the end of the pass running at switch_at_s (2 s passes); measured is on the 0.25 s grid. NOT pinned: switching TO once while playing (default / stop / loop -> once): see AUDIO-SPEC quirk 12",
        "tolerance_s": END_TOL, "rows": rows}}


# ------------------------------------------------------------------------------------------------ play_modes.json
async def play_modes():
    cases = {}
    lib = {"a.wav": 2, "b.wav": 2, "c.wav": 2, "u.wav": 2, "v.wav": 1}
    pls = [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav"]}, {"name": "B", "tracks": ["u.wav", "v.wav"]}]
    modes, ends, from_tracks, seed, max_ticks, step_s = ("stop", "loop_playlist", "next_playlist", "shuffle"), ("default", "once", "loop", "stop"), (0, 2), 1234, 80, 0.25
    base = {"library_s": dict(lib), "playlists": {p_["name"]: p_["tracks"] for p_ in pls}, "playlist_under_test": 0}
    async with Rig(lib, pls) as r:
        P = r.P
        await r.load(*lib)
        rows = []
        for mode in modes:
            for end in ends:
                for t in from_tracks:
                    r.reset(pls)
                    random.seed(seed)
                    P.set_play_mode(0, mode)
                    P.set_play_mode(1, mode)
                    P.set_end(0, t, end)
                    P.play(0, t)
                    prev = r.live()
                    after = "same"
                    for _ in range(max_ticks):                  # up to 20 s: long enough for two passes of a 2 s track
                        r.fake.t += step_s
                        P.tick()
                        d = r.live()
                        if d is not prev:
                            after = "stopped" if d is None else {"playlist": d.pt[0], "track": d.pt[1]}
                            break
                    if mode == "shuffle" and isinstance(after, dict) and end in ("default", "once"):
                        after = {"playlist": after["playlist"], "any_other_track_of_the_playlist": after["track"] != t}   # the choice is random: only the property is the contract
                    rows.append({"mode": mode, "end_action": end, "track": t, "after": after})
        cases["after_a_track_ends"] = {"scenario": dict(base, play_modes=list(modes), end_actions=list(ends), from_tracks=list(from_tracks), mode_set_on_playlists=[0, 1], tick_step_s=step_s, max_ticks=max_ticks, shuffle_random_seed=seed,
                                                       steps=["set the play mode on both playlists", "set_end(0, from_track, end_action)", "play(0, from_track)", "tick every tick_step_s until the live deck changes or max_ticks"]), "_info": "playlist A has 3 tracks, B has 2. 'same' = the same deck is still playing (loop). shuffle: only 'another track of the same playlist' is promised",
                                       "rows": rows}
        rows = []                                              # next_in_order, pure
        for mode in ("stop", "loop_playlist"):
            r.reset(pls)
            P.set_play_mode(0, mode)
            rows.append({"mode": mode, "from_track": [0, 1, 2], "next_in_order": [P.next_in_order(0, t) for t in (0, 1, 2)]})
        r.reset(pls)
        P.set_play_mode(0, "stop")
        P.set_end(0, 1, "loop")
        rows.append({"mode": "stop, track 1 set to loop", "from_track": [0, 1, 2], "next_in_order": [P.next_in_order(0, t) for t in (0, 1, 2)]})
        cases["next_in_order"] = {"scenario": dict(base, row_inputs={"stop": {"play_mode": "stop"}, "loop_playlist": {"play_mode": "loop_playlist"}, "stop, track 1 set to loop": {"play_mode": "stop", "end_action_of_track_1": "loop"}},
                                                  input="next_in_order(0, t) for each t in the row's from_track; the row label names the playlist mode (and any end action) set before"), "_info": "indices to try, best first, for what follows track t (stop: nothing; loop_playlist: t+1 first then the rest in a ring; a looping track repeats itself)", "rows": rows}
        r.reset(pls)                                           # shuffle bag properties
        P.set_play_mode(0, "shuffle")
        seed_a, draws_a, seed_b, seed_c, draws_c = 20240229, 30, 7, 7, 300
        random.seed(seed_a)
        cur, seq = 0, []
        for _ in range(draws_a):
            cur = P.next_in_order(0, cur)[0]
            seq.append(cur)
        no_repeat = all(a != b for a, b in zip([0] + seq, seq))
        r.reset(pls)
        P.set_play_mode(0, "shuffle")
        random.seed(seed_b)
        first_round = [P.next_in_order(0, 0)[0]]
        first_round.append(P.next_in_order(0, first_round[0])[0])
        left_after_one = None
        r.reset(pls)
        P.set_play_mode(0, "shuffle")
        P.next_in_order(0, 0)
        left_after_one = len(P.shuffle_left(0))
        P.set_play_mode(0, "stop")
        forgot = len(P.shuffle_left(0)) == 0
        r.reset(pls)
        P.set_play_mode(0, "shuffle")
        random.seed(seed_c)
        counts, cur = {0: 0, 1: 0, 2: 0}, 0
        for _ in range(draws_c):
            cur = P.next_in_order(0, cur)[0]
            counts[cur] += 1
        cases["shuffle_bag"] = {"scenario": dict(base, play_mode="shuffle", start_track=0, draws_for_sequence=draws_a, draws_for_fair_share=draws_c, python_random_seeds=[seed_a, seed_b, seed_c], fair_share_range=[60, 140]), "_info": "properties are the contract; the sequence for a fixed Python random seed depends on the Python version and is NOT compared (_info_sequence)",
                                "never_the_same_track_twice_in_a_row": bool(no_repeat),
                                "every_draw_is_a_track_of_the_playlist": all(0 <= x < 3 for x in seq),
                                "first_round_from_track_0_is_a_permutation_of_tracks_1_and_2": sorted(first_round) == [1, 2],
                                "tracks_left_in_the_round_after_one_draw_from_track_0": left_after_one,
                                "changing_the_mode_forgets_the_round": bool(forgot),
                                "each_track_gets_a_fair_share_of_300_draws_60_to_140": all(60 <= v <= 140 for v in counts.values()),
                                "_info_sequence": seq, "_info_python": sys.version.split()[0]}
    return doc("play_modes", "What follows a track that ends, for every play mode and end action; next_in_order; the shuffle bag (properties, plus an informational sequence).", cases)


# ------------------------------------------------------------------------------------------------ triggers.json
async def triggers():
    cases = {}
    lib = {"main.wav": 120, "vo.wav": 3, "vo2.wav": 8}
    pls = [{"name": "A", "tracks": ["main.wav"]}]
    async with Rig(lib, pls) as r:
        P = r.P
        fires = []
        real_top = P._play_on_top

        def spy(p, t, tr):
            if p is None:                                         # only trigger points (the operator's own Play on Top has a playlist entry)
                fires.append({"t_s": round(r.fake.t - r.t0, 2), "file": tr["id"]})
            return real_top(p, t, tr)
        r.patch(P, "_play_on_top", spy)
        await r.load(*lib)

        async def run(label, triggers_, secs, trim_=None, seek=None, loop=False, info="", ideal=None):
            r.reset(pls)
            fires.clear()
            P.playlists[0].pop("trims", None)
            P.playlists[0].pop("triggers", None)
            P.set_end(0, 0, "loop" if loop else "default")
            if trim_:
                P.set_trim(0, 0, trim_)
            for tg in triggers_:
                _, err = P.set_triggers(0, 0, "add", dict(tg))
                assert err is None, err
            P.play(0, 0)
            r.rebase()
            fires.clear()
            r.run_for(secs, each=(lambda e: P.seek_live(seek[1]) if seek and abs(e - seek[0]) < 1e-9 else None))
            if ideal is None:                                  # the playhead reaches `at` after (at - A) seconds, and again every pass of a loop (once: the first pass only)
                lo = float((trim_ or {}).get("in", 0.0))
                hi = float((trim_ or {}).get("out", lib["main.wav"]))
                ideal = []
                for tg in triggers_:
                    if not tg.get("enabled", True) or not lo <= tg["at"] < hi:
                        continue
                    n = 0
                    while True:
                        t_ideal = (tg["at"] - lo) + n * (hi - lo)
                        if t_ideal > secs or (n and (not loop or tg.get("once"))):
                            break
                        ideal.append({"t_s": round(t_ideal, 3), "file": tg["file"]})
                        n += 1
                ideal.sort(key=lambda x: x["t_s"])
            else:
                ideal = [dict(x) for x in ideal]
            assert len(ideal) == len(fires), (label, ideal, fires)                 # the generator checks its own claim: measured = ideal + at most one tick
            for m, i in zip(fires, ideal):
                assert -1e-6 <= m["t_s"] - i["t_s"] <= TRIG_TOL + 1e-6 and m["file"] == i["file"], (label, m, i)
            scn = {"library_s": dict(lib), "playlist": pls[0]["tracks"], "main_track": "main.wav", "main_track_length_s": lib["main.wav"], "voice_over_lengths_s": {k: v for k, v in lib.items() if k != "main.wav"},
                   "end_action": "loop" if loop else "default", "run_s": secs, "trim": trim_ or {}, "seek": None if not seek else {"at_s": seek[0], "to_s": seek[1]}, "triggers": triggers_,
                   "steps": ["set the end action and the trim", "add the trigger points", "play track 0 and start counting", "tick every 50 ms for run_s (the seek, if any, at seek.at_s of play)"], "tick_s": 0.05}
            cases[label] = {"scenario": scn, "_info": info, "triggers": triggers_, "trim": trim_ or {}, "fires": list(fires), "ideal_fires": ideal, "tolerance_s": TRIG_TOL}
        await run("simple", [{"at": 10, "file": "vo.wav"}], 14, info="fires once when the playhead reaches `at` (within one 50 ms tick)")
        await run("two_in_order", [{"at": 5, "file": "vo.wav"}, {"at": 20, "file": "vo2.wav"}], 25, info="the first voice-over (3 s) is over before the second fires")
        await run("disabled", [{"at": 5, "file": "vo.wav", "enabled": False}], 8, info="a disabled trigger never fires")
        await run("trim_in_after_trigger", [{"at": 3, "file": "vo.wav"}], 6, trim_={"in": 4}, info="a trigger before the In point never fires")
        await run("trim_out_before_trigger", [{"at": 9, "file": "vo.wav"}], 10, trim_={"out": 8}, info="a trigger at or after the Out point never fires (track ends at 8 s)")
        await run("trigger_inside_trim", [{"at": 10, "file": "vo.wav"}], 10, trim_={"in": 6}, info="`at` is a position in the FILE: with A = 6 s it fires 4 s after the start")
        await run("seek_over_does_not_fire", [{"at": 10, "file": "vo.wav"}], 14, seek=(1.0, 20.0), ideal=[], info="seeking from 1 s to 20 s jumps over the trigger at 10 s: it never fires (without the seek it would)")
        await run("seek_back_rearms", [{"at": 10, "file": "vo.wav"}], 26, seek=(14.0, 2.0), ideal=[{"t_s": 10.0, "file": "vo.wav"}, {"t_s": 22.0, "file": "vo.wav"}], info="fires at 10 s; the voice-over (3 s) is over, seek back to 2 s at 14 s of play: what is ahead is armed again, so it fires again 8 s later (22 s of play). A seek while a voice-over plays on top is ignored (the live deck is the voice-over)")
        await run("loop_fires_every_pass", [{"at": 1, "file": "vo.wav"}], 14, trim_={"out": 6}, loop=True, info="a looping 6 s window (A=0, B=6) fires in every pass (the 3 s voice-over is over before the next pass)")
        await run("once_flag", [{"at": 1, "file": "vo.wav", "once": True}], 14, trim_={"out": 6}, loop=True, info="once: first pass only")
        await run("top_already_playing_skips", [{"at": 1, "file": "vo2.wav"}, {"at": 3, "file": "vo.wav"}], 14, ideal=[{"t_s": 1.0, "file": "vo2.wav"}], info="vo2 (8 s) is on top at 3 s, so the second trigger is skipped, not queued")
    return doc("triggers", "Trigger points: when the playlist's voice-overs fire (seconds after the start of the track, fake clock, 50 ms ticks; each fire is a Play on Top with no playlist entry). `fires` is what the Python player measured (it includes the tick); `ideal_fires` is the time at which the playhead reaches `at` ((at - A) after the start, plus whole passes in a loop); another engine compares its own times with the IDEAL ones within `tolerance_s`.", cases)


# ------------------------------------------------------------------------------------------------ ducking.json
def _runs(windows):
    """[(l, r), ...] -> [{"windows": n, "left": l, "right": r}, ...]: consecutive equal windows folded."""
    out = []
    for w in windows:
        if out and (out[-1]["left"], out[-1]["right"]) == tuple(w):
            out[-1]["windows"] += 1
        else:
            out.append({"windows": 1, "left": w[0], "right": w[1]})
    return out


def _pcm(windows):
    import numpy as np
    a = np.zeros((len(windows) * 480, 2), dtype="<i2")
    for i, (l, rr) in enumerate(windows):
        a[i * 480:(i + 1) * 480, 0], a[i * 480:(i + 1) * 480, 1] = l, rr
    return a.tobytes()


DUCK_VOICE = [(0.3, 0), (0.7, 16384), (0.5, 4096), (0.5, 0)]           # (seconds, constant sample value in both channels): 2 s, loud then quieter then silent
DUCK_CURVE_TOL = 2e-5                                                      # dB: the float32 key noise of duck_curve (see its _info_tolerance)
HOLD_RAMP = [0, 3000, 6000, 9000, 12000, 16000, 20000, 24000, 28000, 32000, 26000, 18000, 10000, 5000, 0, 0]     # left-channel sample value per 10 ms window (right = 0)


def _hold_percentile_case(dsp):
    """The hold depth is the 75th percentile of the active targets. The same curve is worked out here with the 60th and the 90th percentile and the
    committed values must differ from both (so a change of the percentile cannot pass unnoticed); cpl/ is not touched."""
    import numpy as np
    level, ratio, thr = 1.0, 6.0, -30.0
    key = dsp.duck_key(_pcm([(v, 0) for v in HOLD_RAMP]))

    def alt(pct):                                                          # dsp.duck_curve, line for line, with another percentile
        db = 20.0 * np.log10(np.maximum(key * max(level, 1e-4), 1e-6))
        tgt = np.minimum(np.clip(db - thr, 0.0, None) * (1.0 - 1.0 / ratio), 60.0)
        act = np.nonzero(tgt > 0.05)[0]
        seg = slice(int(act[0]), int(act[-1]) + 1)
        depth = float(np.percentile(tgt[seg][tgt[seg] > 0.05], pct))
        tgt[seg] = np.maximum(tgt[seg], depth)
        return depth, tgt.astype(np.float32)
    real = dsp.duck_curve(key, level, ratio, thr, True)
    nohold = dsp.duck_curve(key, level, ratio, thr, False)
    d75, c75 = alt(75)
    assert np.allclose(real, c75, atol=1e-6), "the generator's own 75th-percentile copy does not match dsp.duck_curve"
    for pct in (60, 90):
        d, c = alt(pct)
        assert abs(d - d75) > 0.5 and float(np.max(np.abs(c - real))) > 0.5, f"the hold-percentile case no longer tells {pct} from 75"
    return {"scenario": {"input": "duck_curve(key, level, ratio, threshold_db, hold) with the key of this signal", "format": "48 kHz, 2 channels, 16-bit little-endian", "window_samples": 480,
                         "windows": _runs([(v, 0) for v in HOLD_RAMP]), "level": level, "ratio": ratio, "threshold_db": thr},
            "tolerance": DUCK_CURVE_TOL,
            "_info": "hold = true keeps the 75th-percentile depth (of the windows above 0.05 dB) from the first to the last active window. The ramp has targets from 0 to about 25 dB, so the depth is clearly different for the 60th and the 90th percentile.",
            "_info_alternatives": {"depth_db_60th": r6(alt(60)[0]), "depth_db_75th": r6(d75), "depth_db_90th": r6(alt(90)[0])},
            "hold_depth_db": r6(d75), "reduction_db_hold_off": [r6(x) for x in nohold], "reduction_db_hold_on": [r6(x) for x in real]}


async def duck_loop_cases():
    """The real _duck_loop under the fake clock: one loop iteration = one 10 ms step of fake time (asyncio.sleep is replaced for the duration)."""
    import wave
    import numpy as np
    out = {}
    voice = DUCK_VOICE
    async with Rig({"bg.wav": 30, "pad.wav": 1}, [{"name": "bg", "tracks": ["bg.wav"]}, {"name": "top", "tracks": ["voice.wav"]}]) as r:
        P = r.P
        y = np.concatenate([np.full(int(48000 * sec), v, dtype="<i2") for sec, v in voice])
        with wave.open(str(r.dir / "media" / "library" / "voice.wav"), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(np.repeat(y[:, None], 2, axis=1).tobytes())
        P.scan_library()
        P.DURS["voice.wav"] = (0, 0, 2.0)
        await r.load("bg.wav", "voice.wav")
        real_sleep = asyncio.sleep
        for _ in range(100):                                               # the level key of a loaded track is worked out in the background
            if str(P.LIB / "voice.wav") in P._key:
                break
            await real_sleep(0.05)
        assert str(P.LIB / "voice.wav") in P._key
        async def fake_sleep(delay, *a, **k):                              # yield first, advance after: when the loop computes, the clock already shows its time, and a sample taken between turns shows the state computed at that time
            await real_sleep(0)
            r.fake.t += delay
        for label, settings in (("production_defaults_hold_on", {"duck_threshold_db": -30.0, "duck_ratio": 6.0, "duck_attack_ms": 10, "duck_release_ms": 500, "duck_hold": True, "top_track_pct": 100}),
                                ("slow_attack_hold_off", {"duck_threshold_db": -30.0, "duck_ratio": 6.0, "duck_attack_ms": 40, "duck_release_ms": 200, "duck_hold": False, "top_track_pct": 100})):
            r.reset([{"name": "bg", "tracks": ["bg.wav"]}, {"name": "top", "tracks": ["voice.wav"]}], cfg=settings)
            P.DUCK["gr"] = 0.0
            asyncio.sleep = fake_sleep
            try:
                P.play(0, 0)
                bg = r.live()
                r.rebase()
                cols = {"t_s": [], "top_pos_s": [], "target_db": [], "gr_db": [], "bg_multiplier": []}

                def sample(top=None):
                    cols["t_s"].append(round(r.fake.t - r.t0, 3))
                    pos, tgt = None, None
                    if top is not None and top in P.decks:
                        pos = top.fpos()
                        cur = P.DUCK["curve"]
                        i = int((pos - P.DUCK["origin"]) / P.DUCK_STEP) + 2                    # the loop reads the curve 20 ms ahead of the playhead
                        tgt = float(cur[i]) if cur is not None and 0 <= i < len(cur) else 0.0
                    cols["top_pos_s"].append(r6(pos))
                    cols["target_db"].append(r6(tgt))
                    cols["gr_db"].append(r6(P.DUCK["gr"]))
                    cols["bg_multiplier"].append(r6(bg.duck))
                for _ in range(50):                                                              # 0.5 s of background alone (no loop is running yet)
                    r.fake.t += 0.01
                    if round(r.fake.t - r.t0, 3) % 0.05 < 1e-6:
                        P.tick()
                    sample()
                voice_start = round(r.fake.t - r.t0, 3)
                assert P.play_on_top(1, 0)
                top = r.live()
                assert top.top
                await real_sleep(0)                                                                # the loop starts and takes its first time stamp (0.5 s)
                sample(top)
                for k in range(1, 620):                                                          # until the voice-over (2 s) is over and the release has finished (the smoothing snaps to 0 dB below 0.05 dB)
                    await real_sleep(0)
                    if k % 5 == 0:
                        P.tick()
                    sample(top)
                    if P.DUCK["task"] is None or P.DUCK["task"].done():                         # the loop ends by itself when the release is over (the clock only moves while it runs)
                        break
            finally:
                asyncio.sleep = real_sleep
            out[label] = {"scenario": {"background": {"file": "bg.wav", "length_s": 30}, "voice_over_file": "voice.wav", "see": "the `scenario` of the duck_loop case, plus `settings` here"}, "settings": settings, "step_s": 0.01, "look_ahead_s": 0.02, "voice_over": {"file": "voice.wav", "starts_at_s": voice_start, "length_s": 2.0, "level_pct": settings["top_track_pct"],
                                                                                                    "segments_s_and_sample_value": [[sec, v] for sec, v in voice]},
                          "samples": cols, "peak_reduction_db": r6(max(cols["gr_db"])), "final_multiplier": cols["bg_multiplier"][-1]}
            P.stop_all()
    return out


async def ducking():
    import numpy as np
    cases = {}
    async with Rig({"a.wav": 1}) as r:
        dsp = r.app.mod("dsp")
        win = [(0, 0)] * 5 + [(16384, 8192)] * 10 + [(3277, 0)] * 5 + [(0, 0)] * 5 + [(1000, 16384)] * 3
        key = dsp.duck_key(_pcm(win))
        pcm_scn = {"format": "48 kHz, 2 channels, 16-bit little-endian", "window_samples": 480, "window_s": 0.01, "input": "every 10 ms window holds ONE constant sample value per channel", "windows": _runs(win)}
        cases["duck_key"] = {"scenario": pcm_scn, "_info": "RMS (0..1) of the louder channel per 10 ms window of 48 kHz stereo 16-bit; the input is, per 10 ms: 5 silent, 10 at (16384, 8192), 5 at (3277, 0), 5 silent, 3 at (1000, 16384)",
                             "key": [r6(x) for x in key]}
        rows = []
        for level, ratio, thr, hold in ((1.0, 6.0, -30.0, False), (1.0, 6.0, -30.0, True), (1.0, 2.0, -20.0, False), (0.5, 4.0, -30.0, False), (1.0, 1.0, -30.0, False), (1.0, 100.0, -60.0, False), (2.0, 6.0, -30.0, True)):
            tg = dsp.duck_curve(key, level, ratio, thr, hold)
            rows.append({"level": level, "ratio": ratio, "threshold_db": thr, "hold": hold, "reduction_db": [r6(x) for x in tg]})
        cases["duck_curve"] = {"scenario": dict(pcm_scn, input="the key of the duck_key case (same windows) is passed to duck_curve with each row's level, ratio, threshold_db and hold"),
                               "tolerance": DUCK_CURVE_TOL,
                               "_info_tolerance": "case-level tolerance (dB), overrides the file's 2e-6: the Python key is float32 and carries about 1e-6 relative noise on the (3277, 0) windows, which moves the reduction by up to about 1.2e-5 dB",
                               "_info": "dB of reduction wanted per 10 ms before smoothing: max(0, dB(key*level) - threshold) * (1 - 1/ratio), capped at 60 dB; hold keeps the 75th-percentile depth from the first to the last active window",
                               "rows": rows}
        cases["duck_curve_hold_percentile"] = _hold_percentile_case(dsp)
        rows = []
        smooth_cases = ((10, 500, [12.0] * 30 + [0.0] * 120), (50, 1000, [20.0] * 20 + [6.0] * 40 + [0.0] * 200), (1, 1, [10.0, 0.0, 10.0, 0.0]))
        for attack, release, tgt_seq in smooth_cases:
            gr, series = 0.0, []
            for tg in tgt_seq:
                gr = dsp.duck_smooth(gr, tg, 0.01, attack, release)
                series.append(r6(gr))
            rows.append({"attack_ms": attack, "release_ms": release, "dt_s": 0.01, "target_db": tgt_seq if len(tgt_seq) <= 8 else {"pattern": "constant segments", "segments": _segments(tgt_seq)}, "gr_db": series})
        cases["duck_smooth"] = {"scenario": {"initial_gr_db": 0.0, "dt_s": 0.01, "input": "each row: attack_ms, release_ms and the target series (segments = runs of equal target, `steps` long); dsp.duck_smooth is applied once per 10 ms step"}, "_info": "one step per 10 ms: gr += (tgt - gr) * (1 - exp(-dt/tau)); tau = attack when tgt > gr else release (min 1 ms); snaps to 0 when tgt == 0 and gr < 0.05",
                                "rows": rows}
        cases["background_gain"] = {"scenario": {"input": "each row's gr_db"}, "_info": "the background deck volume is multiplied by 10^(-gr/20) (Deck.duck)", "rows": [{"gr_db": g, "multiplier": r6(10 ** (-g / 20.0))} for g in (0, 3, 6, 12, 20, 40, 60)]}
        rows = []
        for rms, gain, ratio, thr in ((0.5, 0.0, 6.0, -30.0), (0.01, 0.0, 6.0, -30.0), (0.01, 20.0, 6.0, -30.0), (0.1, -10.0, 3.0, -25.0), (0.0, 0.0, 6.0, -30.0)):
            rows.append({"rms": rms, "gain_db": gain, "ratio": ratio, "threshold_db": thr, "reduction_db": r6(dsp.input_target_db(rms, gain, ratio, thr))})
        cases["input_target_db"] = {"scenario": {"input": "each row: rms (0..1), gain_db, ratio, threshold_db"}, "_info": "Live input detector: the same gain computation as duck_curve (hold off), with its own threshold", "rows": rows}
        loop_scn = {"background": {"file": "bg.wav", "length_s": 30, "playlist": 0, "track": 0, "started_by": "play(0, 0)"}, "background_alone_s": 0.5,
                    "voice_over": {"file": "voice.wav", "playlist": 1, "track": 0, "started_by": "play_on_top(1, 0) at 0.5 s", "stereo_48k": True, "segments_s_and_sample_value": [[a_, b_] for a_, b_ in DUCK_VOICE]},
                    "step_s": 0.01, "tick_every_steps": 5, "max_steps": 620, "settings_per_case": "each entry of `cases` holds its `settings`"}
        cases["duck_loop"] = {"scenario": loop_scn, "_info": "the REAL _duck_loop and Play on Top under the fake clock: background deck + a 2 s voice-over (0.3 s silence, 0.7 s at 16384, 0.5 s at 4096, 0.5 s silence, stereo 48 kHz), sampled every 10 ms from 0.5 s before the voice-over until after the release. target_db = the duck_curve value the loop reads at top_pos + 20 ms (look-ahead); gr_db = smoothed reduction; bg_multiplier = Deck.duck of the background (applied only when it moved by more than 0.0005, so it can trail 10^(-gr/20) by that). Index 49 is the last background-only sample (t = 0.5 s, voice-over not started), index 50 is the voice-over starting at the same time (top_pos 0); from index 51 every row is 10 ms later, with the reduction computed by the loop at that time.",
                              "cases": await duck_loop_cases()}
    return doc("ducking", "Sidechain ducking maths (cpl/dsp.py): level key, reduction curve, attack/release smoothing and the multiplier applied to the background.", cases)


def _segments(seq):
    out, run = [], 1
    for a, b in zip(seq, seq[1:] + [None]):
        if a == b:
            run += 1
        else:
            out.append({"db": a, "steps": run})
            run = 1
    return out


# ------------------------------------------------------------------------------------------------ levelmatch.json
async def levelmatch():
    import numpy as np
    cases = {}

    def sine(db_peak, secs, hz=1000.0, stereo=True, silent_second_channel=False):
        n = np.arange(int(48000 * secs))
        y = np.round(32768 * 10 ** (db_peak / 20) * np.sin(2 * np.pi * hz * n / 48000)).astype("<i2")
        a = np.stack([y, np.zeros_like(y) if silent_second_channel else y], axis=1)
        return a.tobytes()
    async with Rig({"a.wav": 1, "b.wav": 1, "c.wav": 1}, [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav"]}]) as r:
        dsp, L, P = r.app.mod("dsp"), r.app.mod("loudness"), r.P
        rows, signals = [], []
        for label, spec in (("1 kHz sine, -20 dBFS peak, 5 s, stereo", dict(db_peak=-20, secs=5)), ("1 kHz sine, -6 dBFS peak, 5 s", dict(db_peak=-6, secs=5)), ("1 kHz sine, -30 dBFS peak, 5 s", dict(db_peak=-30, secs=5)),
                            ("100 Hz sine, -20 dBFS peak, 5 s", dict(db_peak=-20, secs=5, hz=100.0)), ("10 kHz sine, -20 dBFS peak, 5 s", dict(db_peak=-20, secs=5, hz=10000.0)),
                            ("1 kHz sine, -20 dBFS, left channel only", dict(db_peak=-20, secs=5, silent_second_channel=True)), ("silence 5 s", dict(silence_secs=5)),
                            ("too short (0.3 s)", dict(db_peak=-20, secs=0.3)), ("1 kHz sine, -20 dBFS, 12 s", dict(db_peak=-20, secs=12))):
            if "silence_secs" in spec:
                raw = bytes(48000 * 4 * spec["silence_secs"])
                signals.append({"signal": label, "kind": "silence", "duration_s": float(spec["silence_secs"]), "channels": 2})
            else:
                raw = sine(**spec)
                signals.append({"signal": label, "kind": "sine", "frequency_hz": spec.get("hz", 1000.0), "peak_dbfs": float(spec["db_peak"]), "amplitude": r6(10 ** (spec["db_peak"] / 20)),
                                "duration_s": float(spec["secs"]), "channels": 2, "second_channel": "silent" if spec.get("silent_second_channel") else "same as the first"})
            v = dsp.lufs_from_pcm(raw)
            rows.append({"signal": label, "lufs": None if v is None else round(v, 3)})
        cases["lufs_from_pcm"] = {"scenario": {"format": "48 kHz, 16-bit little-endian, interleaved stereo", "synthesis": "sample[n] = round(32768 * 10^(peak_dbfs/20) * sin(2*pi*frequency_hz*n/48000)), identical in both channels unless second_channel says silent; silence = all zero",
                                               "signals": signals}, "_info": "integrated loudness (ITU-R BS.1770 K-weighting, 400 ms blocks, -70 LUFS absolute and -10 LU relative gates) of 48 kHz 16-bit stereo; None = silent or shorter than 0.4 s. Rounded to 3 decimals (compared with a 0.01 LU allowance: _tolerance_lufs)",
                                  "rows": rows}
        rows = []
        lufs = {"a.wav": -14.0, "b.wav": -23.0, "c.wav": None}
        for fid, v in lufs.items():
            L.LOUD[fid] = (0, 0, v)
        norm_rows = (("off", {"mode": "off"}), ("track: reference b (-23)", {"mode": "track", "ref": 1}), ("track: reference a (-14), never boosts", {"mode": "track", "ref": 0}),
                     ("lufs: target -18", {"mode": "lufs", "lufs": -18.0}), ("lufs: target -10 (above all: no boost)", {"mode": "lufs", "lufs": -10.0}), ("lufs: target -60 (clamped)", {"mode": "lufs", "lufs": -80.0}))
        LUFS_MIN, LUFS_MAX = -60.0, 0.0                                       # the limits set_norm clamps to (cpl/loudness.py)
        for label, cfg_ in norm_rows:
            P.playlists[0].pop("norm", None)
            P.playlists[0]["norm"] = dict(L.NORM_DEFAULT)
            L.set_norm(0, cfg_.get("mode"), cfg_.get("ref"), cfg_.get("lufs"))
            rows.append({"setting": label, "measured_lufs": [lufs[x] for x in ("a.wav", "b.wav", "c.wav")], "gain_db": [None if L.norm_gain_db(0, t) is None else r6(L.norm_gain_db(0, t)) for t in range(3)],
                         "gain_linear": [r6(L.norm_gain(0, t)) for t in range(3)], "typed": dict(cfg_), "stored": dict(P.playlists[0]["norm"])})
            if cfg_.get("lufs") is not None:
                assert P.playlists[0]["norm"]["lufs"] == max(LUFS_MIN, min(LUFS_MAX, round(cfg_["lufs"], 1))), "the clamp limits in the generator no longer match set_norm"
        cases["norm_gain"] = {"scenario": {"playlist": ["a.wav", "b.wav", "c.wav"], "measured_lufs": lufs, "input": "set_norm(playlist 0, mode, ref, lufs) with each row's `typed` values (ref = track index); `stored` is what was kept; norm_gain_db / norm_gain are read for tracks 0..2",
                                           "lufs_clamp_db": {"min": LUFS_MIN, "max": LUFS_MAX, "step": 0.1}}, "_info": "gain_db = min(0, target - measured), target = the reference track's LUFS (track mode) or the fixed LUFS (lufs mode, -60..0, 0.1 steps); never boosts; None = not applicable (off, or the track has no measurement); linear = 10^(dB/20), 1.0 when no gain", "rows": rows}
        rows = []                                           # applied to a live deck
        r.reset()
        P.playlists[0]["norm"] = dict(L.NORM_DEFAULT)
        deck_target = -23.0
        L.set_norm(0, "lufs", None, deck_target)
        await r.load("a.wav")
        P.play(0, 0)
        d = r.live()
        rows.append({"track": "a.wav (-14 LUFS), target -23", "deck_gain": r6(d.gain), "deck_gain_db": r6(20 * math.log10(d.gain))})
        L.set_norm(0, "off")
        rows.append({"track": "after switching level match off", "deck_gain": r6(d.gain)})
        cases["applied_to_deck"] = {"scenario": {"playlist": ["a.wav", "b.wav", "c.wav"], "measured_lufs": lufs, "playing": "a.wav (playlist 0, track 0)", "playing_file": "a.wav",
                                                 "row_inputs": {"a.wav (-14 LUFS), target -23": {"set_norm": {"mode": "lufs", "lufs": deck_target}, "then": "play track 0"}, "after switching level match off": {"set_norm": {"mode": "off"}}}}, "_info": "Deck.gain follows level match immediately (apply_gain_live); the channel volume is vol * gain * duck * duck_in * live_volume", "rows": rows}
    d = doc("levelmatch", "Level match: integrated loudness (LUFS) of synthetic signals and the per-track gain it gives (only ever turns a track down).", cases)
    d["tolerance_lufs"] = 0.01
    return d


# ------------------------------------------------------------------------------------------------ resume.json
async def resume():
    cases = {}
    pls = [{"name": "A", "tracks": ["a.wav", "b.wav"]}]
    rlib = {"a.wav": 60, "b.wav": 60}
    rcfg = {"resume_on_start": True, "resume_max_age_s": 1800, "resume_save_s": 5}
    base = {"library_s": dict(rlib), "playlist": pls[0]["tracks"], "track_ids": {"0": "a.wav", "1": "b.wav"}, "config": rcfg, "age_limit_s": rcfg["resume_max_age_s"]}
    async with Rig(rlib, pls, cfg=rcfg) as r:
        P = r.P
        await r.load("a.wav", "b.wav")

        def saved():
            try:
                d = json.loads(P.RESUME.read_text())
            except FileNotFoundError:
                return None
            d.pop("saved", None)                                    # wall-clock stamp of the fake clock
            return {k: (r6(v) if isinstance(v, float) else v) for k, v in d.items()}
        rows = []
        rec_inputs, rec_track, pause_wait_s = {}, 1, 20.0
        for label, setup, at_s in (("playing, 12.5 s in", None, 12.5), ("paused at 7.25 s", "pause", 7.25)):
            rec_inputs[label] = {"play_track": rec_track, "at_s": at_s, "paused": setup == "pause", "clock_at_save_s": pause_wait_s if setup == "pause" else at_s}
            r.reset(pls)
            P.RESUME.unlink(missing_ok=True)
            P.play(0, rec_track)
            r.rebase()
            r.at(at_s)
            if setup == "pause":
                P.pause_all()
                r.at(pause_wait_s)                                  # time passes while paused: the position does not
            P.save_resume(force=True)
            rows.append({"case": label, "record": saved()})
        r.reset(pls)                                                # what is NOT recorded
        P.RESUME.unlink(missing_ok=True)
        P.play(0, 0)
        r.at(3.0)
        P.stop_all()
        P.save_resume()
        rows.append({"case": "after a deliberate stop", "record": saved()})
        rec_inputs["after a deliberate stop"] = {"play_track": 0, "at_s": 3.0, "then": {"action": "stop_all"}, "then_text": "stop_all, save_resume"}
        rec_inputs["while fading out"] = {"play_track": 0, "at_s": 3.0, "then": {"action": "fade_out", "fade_ms": 1000}, "then_text": "fade_out(1000 ms), save_resume"}
        P.play(0, 0)
        r.at(3.0)
        P.fade_out(1000)
        P.save_resume()
        rows.append({"case": "while fading out", "record": saved()})
        cases["record"] = {"scenario": dict(base, row_inputs=rec_inputs, input="save_resume(force) after the steps of the row; `record` is resume.json without its wall-clock `saved` stamp"), "_info": "save_resume: pt = [playlist, track], id = library file, pos = seconds in the FILE (a paused track keeps its position), paused flag; removed when nothing plays or a fade-out is running", "rows": rows}
        rows = []
        for label, rec, age in (("fresh record", {"pt": [0, 1], "id": "b.wav", "pos": 33.5, "paused": False}, 10), ("paused record", {"pt": [0, 0], "id": "a.wav", "pos": 8.25, "paused": True}, 10),
                                ("older than resume_max_age_s", {"pt": [0, 0], "id": "a.wav", "pos": 8.25, "paused": False}, 4000),
                                ("playlist edited: the track moved", {"pt": [0, 0], "id": "b.wav", "pos": 5.0, "paused": False}, 10), ("file no longer in any playlist", {"pt": [0, 0], "id": "gone.wav", "pos": 5.0, "paused": False}, 10)):
            r.reset(pls)
            P.RESUME.write_text(json.dumps(dict(rec, saved=r.clock.time() - age)))
            P.try_resume()
            pend = P.S.pending
            row = {"case": label, "record": rec, "age_s": age, "pending": None if pend is None else {"pt": pend["pt"], "offset_s": r6(pend["offset"]), "paused": pend["paused"], "xfade_ms": pend["xfade"]}}
            for _ in range(20):
                await asyncio.sleep(0)
            d = r.live()
            row["started"] = None if d is None else {"pt": d.pt, "base_s": r6(d.base), "paused": d.paused_at is not None, "start_vol": r6(d.vol), "fade_in_ms": d.fade_in_ms}
            row["record_kept"] = P.RESUME.exists()
            rows.append(row)
        cases["try_resume"] = {"scenario": dict(base, input="resume.json is written with the row's `record` and saved = now - age_s, then try_resume() runs (start-up) and 20 event-loop turns pass; `record` / `age_s` are in the row"), "_info": "at start-up. offset = where in the file the sound begins; a resumed start never fades in (start_vol 1, fade_in_ms 0), even when the track has a fade-in at A; an old or unknown record is dropped", "rows": rows}
        r.reset(pls)
        rt_trim = {"in": 2.0, "out": 40.0, "start": "fade", "fade_in_ms": 1500}
        rt_rec = {"pt": [0, 0], "id": "a.wav", "pos": 20.0, "paused": False}
        rt_age = 5
        P.playlists[0]["trims"] = {"a.wav": rt_trim}
        P.RESUME.write_text(json.dumps(dict(rt_rec, saved=r.clock.time() - rt_age)))
        P.try_resume()
        for _ in range(20):
            await asyncio.sleep(0)
        d = r.live()
        cases["resume_inside_a_trim"] = {"scenario": dict(base, trim_of_track_0=rt_trim, record=rt_rec, age_s=rt_age), "_info": "trim A=2 B=40 with a fade-in; resume at 20 s", "started": None if d is None else {"base_s": r6(d.base), "lo_s": r6(d.lo), "hi_s": r6(d.hi), "start_vol": r6(d.vol), "fade_in_ms": d.fade_in_ms, "fresh": d.fresh}}
    return doc("resume_flow", "Resume: what resume.json records and how a restart carries on (position, paused flag, age limit, no fade-in).", cases)


GROUPS = {"fades": fades, "xfade": xfade, "trim": trim, "end_actions": end_actions, "play_modes": play_modes, "triggers": triggers, "ducking": ducking, "levelmatch": levelmatch, "resume_flow": resume}


async def _all():
    return {name: await fn() for name, fn in GROUPS.items()}


def build_all():
    """name -> fixture document, freshly measured from the code."""
    import warnings
    warnings.simplefilter("ignore")
    saved = dict(os.environ)
    try:
        random.seed(0)
        docs = asyncio.run(_all())
        for name, d in docs.items():                      # every case describes its own inputs
            for k, c in d["cases"].items():
                assert "scenario" in c, f"{name}/{k} has no scenario"
                for k2, c2 in (c.get("cases") or {}).items():
                    assert "scenario" in c2, f"{name}/{k}/{k2} has no scenario"
        return docs
    finally:
        os.environ.clear()
        os.environ.update(saved)


def dumps(obj):
    text = json.dumps(obj, indent=1, sort_keys=False, ensure_ascii=False)

    def one_line(m):                                     # the sample columns of duck_loop: one line per column instead of one number per line
        return re.sub(r"\[\s*([^\[\]{}]*?)\s*\]", lambda a: "[" + re.sub(r",\s+", ", ", a.group(1).strip()) + "]", m.group(0))
    return re.sub(r'"samples": \{[^{}]*\}', one_line, text) + "\n"


def strip_info(x):
    """Remove the "_info*" keys (explanations, never compared)."""
    if isinstance(x, dict):
        return {k: strip_info(v) for k, v in x.items() if not str(k).startswith("_info")}
    if isinstance(x, list):
        return [strip_info(v) for v in x]
    return x


def diff(a, b, tol, path="", out=None, limit=40, tbk=None, key=None):
    """Readable list of differences between two JSON values; numbers may differ by `tol`."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a) + [k for k in b if k not in a]:                 # document order, never set order (stable output)
            if k not in a:
                out.append(f"{path}/{k}: only in the new output = {json.dumps(b[k])[:80]}")
            elif k not in b:
                out.append(f"{path}/{k}: only in the committed fixture = {json.dumps(a[k])[:80]}")
            else:
                diff(a[k], b[k], tol, f"{path}/{k}", out, limit, tbk, k)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} (committed) vs {len(b)} (new)")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, tol, f"{path}[{i}]", out, limit, tbk, key)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if abs(a - b) > (tbk or {}).get(key, tol):                       # tolerance_by_key: the nearest dict key above the number
            out.append(f"{path}: committed {a} vs new {b}")
    elif a != b:
        out.append(f"{path}: committed {json.dumps(a)[:80]} vs new {json.dumps(b)[:80]}")
    return out


def compare(new_docs):
    """-> list of readable problems between freshly built documents and the committed files (empty = equal)."""
    problems = []
    for name, d in new_docs.items():
        f = FIXTURES / f"{name}.json"
        if not f.exists():
            problems.append(f"{name}.json: not committed")
            continue
        old = json.loads(f.read_text())
        tol = max(TOL, float(d.get("tolerance_lufs", 0))) if name == "levelmatch" else TOL
        so, sn = strip_info(old), strip_info(d)
        for line in diff({k: v for k, v in so.items() if k != "cases"}, {k: v for k, v in sn.items() if k != "cases"}, tol, name):
            problems.append(line)
        oc, nc = so.get("cases", {}), sn.get("cases", {})
        for k in list(oc) + [k for k in nc if k not in oc]:
            if k not in oc or k not in nc:
                problems.append(f"{name}/cases/{k}: only in the {'new output' if k not in oc else 'committed fixture'}")
                continue
            ctol = nc[k].get("tolerance", tol) if isinstance(nc[k], dict) else tol          # a case-level tolerance overrides the file-level one
            tbk = {str(a): float(b) for a, b in nc[k].get("tolerance_by_key", {}).items()} if isinstance(nc[k], dict) else {}
            for line in diff(oc[k], nc[k], float(ctol), f"{name}/cases/{k}", tbk=tbk):
                problems.append(line)
    for f in sorted(FIXTURES.glob("*.json")):
        if f.stem not in new_docs:
            problems.append(f"{f.name}: committed but not generated any more")
    return problems


def main(argv):
    docs = build_all()
    if "--write" in argv:
        FIXTURES.mkdir(exist_ok=True)
        for name, d in docs.items():
            (FIXTURES / f"{name}.json").write_text(dumps(d))
        print(f"wrote {len(docs)} fixtures to {FIXTURES} (spec version {SPEC_VERSION})")
        return 0
    problems = compare(docs)
    if problems:
        print("the golden audio fixtures differ from the code:\n  " + "\n  ".join(problems[:60]))
        print("\nIf the change of audio behaviour is intended: regenerate with --write, bump SPEC_VERSION, add an 'Audio spec N' line to CHANGELOG.md (docs/AUDIO-SPEC.md).")
        return 1
    print(f"golden audio fixtures match ({len(docs)} files, spec version {SPEC_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
