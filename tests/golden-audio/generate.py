#!/usr/bin/env python3
"""Golden audio fixtures: what the Python player does with sound, written as JSON for any other engine to match (docs/AUDIO-SPEC.md).

    PYTHONHASHSEED=0 python tests/golden-audio/generate.py            # check: regenerate in memory, compare with tests/golden-audio/fixtures/
    PYTHONHASHSEED=0 python tests/golden-audio/generate.py --write    # regenerate and overwrite the committed fixtures

Everything is measured from the real code (a copy of the app imported in-process, fake clock from cpl/clock.py, SDL dummy mixer): nothing here
changes the player. A fixture file is {"spec_version", "name", "about", "tolerance", "cases": {...}}; numbers are rounded to 6 decimals.
Keys that start with "_info" are explanatory and never compared.
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
                                    "rows": [{"x": f, "up": r6(math.sin(f * math.pi / 2)), "down": r6(math.cos(f * math.pi / 2))} for f in [i / 16 for i in range(17)]]}
    async with Rig({"a.wav": 12, "b.wav": 12}, [{"name": "A", "tracks": ["a.wav", "b.wav"]}]) as r:
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
            cases[f"crossfade_{ms}ms"] = {"fade_ms": ms, "start": {"new": 0.0, "old": 1.0}, "rows": rows}
        r.reset()                                           # a zero-length crossfade is a cut
        r.P.play(0, 0)
        old = r.live()
        r.P.play(0, 1, 0)
        cases["crossfade_0ms_is_a_cut"] = {"new_vol": r6(r.live().vol), "old_removed": old not in r.P.decks, "decks": len(r.P.decks)}
        r.reset()                                           # fade out
        r.P.play(0, 0)
        d = r.live()
        r.rebase()
        r.P.fade_out(2000)
        rows = []
        for f in FRACS:
            r.at(f * 2.0)
            rows.append({"x": f, "vol": r6(d.vol), "playing": d in r.P.decks})
        cases["fade_out_2000ms"] = {"rows": rows, "live_after": r.live() is None}
        r.reset()                                           # pause freezes a fade; the pause time is not counted
        r.P.play(0, 0)
        old = r.live()
        r.rebase()
        r.P.play(0, 1, 1000)
        new = r.live()
        r.at(0.25)
        a = (r6(new.vol), r6(old.vol))
        r.P.pause_all()
        r.at(5.25)
        b = (r6(new.vol), r6(old.vol))
        r.P.resume_all()
        r.at(5.5)
        cases["pause_freezes_a_fade"] = {"at_0_25": {"new": a[0], "old": a[1]}, "after_5s_pause": {"new": b[0], "old": b[1]},
                                         "0_25s_after_resume": {"new": r6(new.vol), "old": r6(old.vol)}}
    return doc("fades", "Gain of the decks during equal-power fades, read from Deck.vol at fixed fake-clock times (the mixer channel quantises to 128 steps; Deck.vol is the contract).", cases)


# ------------------------------------------------------------------------------------------------ xfade.json
async def xfade():
    cases = {}
    async with Rig({"a.wav": 12, "b.wav": 12}, [{"name": "A", "tracks": ["a.wav", "b.wav"]}], cfg={"crossfade_ms": 3000, "default_transition": "crossfade"}) as r:
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
        cases["precedence"] = {"_info": "result = explicit (?ms=) if given, else the track's own time if set (0 allowed), else the master crossfade_ms", "rows": rows}
        rows = []
        for secs in (0, 0.5, 30, 30.0004, 31, -1, "abc"):
            ok = P.set_xfade(0, 1, secs)
            rows.append({"seconds": secs, "accepted": bool(ok), "stored_ms": P.xfade_of(0, 1)})
            P.set_xfade(0, 1, None)
        cases["own_time_limits"] = {"_info": "accepted 0..30 s, stored in whole ms", "rows": rows}
        out = []                                            # the length really used by Go / play_default with the crossfade transition
        for label, own in (("master", None), ("own 1.5 s", 1.5)):
            r.reset(cfg={"crossfade_ms": 3000})
            P.set_xfade(0, 1, own)
            P.play(0, 0)
            P.play_default(0, 1)
            out.append({"case": label, "fade_len_s": r6(r.live().fade["len"])})
        cases["play_default_uses_it"] = {"rows": out}
    return doc("xfade", "Crossfade time precedence (explicit ?ms= > per-track > master crossfade_ms) and the fade length that play_default really starts.", cases)


# ------------------------------------------------------------------------------------------------ trim.json
async def trim():
    cases = {}
    lib = {"a.wav": 10, "b.wav": 12}
    async with Rig(lib, [{"name": "A", "tracks": ["a.wav", "b.wav"]}], cfg={"trim_fade_ms": 1500, "trim_fadein_ms": 0}) as r:
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
        cases["trim_range_of_stored_data"] = {"_info": "file is 10 s; trim_range clamps stored values: A at most 0.5 s before the end; a window under 0.5 s falls back to the end of the file", "rows": raw_rows}
        cases["windows"] = {"_info": "file is 10 s. range_s = (A, B) in file seconds; set_trim REFUSES a window shorter than 0.5 s (accepted false, nothing stored); A is held 0.5 s before the end; fade_out_ms = own fade_ms else config trim_fade_ms (1500); the fade-in is applied only while start == 'fade'", "rows": rows}
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
        cases["deck_start"] = {"_info": "what _start sets on the Deck. base = where in the file the sound begins, duration = length of one pass of the window", "rows": rows}
        r.reset()                                           # the fade-out ahead of B
        P.playlists[0].pop("trims", None)
        P.set_trim(0, 0, {"out": 6, "end": "fade", "fade_ms": 2000})
        P.play(0, 0)
        d = r.live()
        r.rebase()
        rows = []
        for t in (0, 3.5, 3.9375, 4.0, 4.25, 4.5, 5.0, 5.5, 5.75, 5.9375):
            r.at(t)
            rows.append({"t_s": t, "vol": r6(d.vol), "fading": d.fade is not None})
        r.at(6.25)
        cases["fade_out_ahead_of_B"] = {"_info": "window 0..6 s, fade_ms 2000: the fade (cos) starts when 2 s are left and ends at B; then the track ends by itself", "rows": rows, "ended": d not in P.decks, "live_after": r.live() is None}
        r.reset()                                           # fade-in at A
        P.playlists[0].pop("trims", None)
        P.set_trim(0, 0, {"in": 2, "start": "fade", "fade_in_ms": 1500})
        P.play(0, 0)
        d = r.live()
        r.rebase()
        rows = []
        for f in FRACS:
            r.at(f * 1.5)
            rows.append({"x": f, "vol": r6(d.vol)})
        cases["fade_in_at_A"] = {"_info": "fade_in_ms 1500: sin(x*pi/2) up to full level", "rows": rows}
    return doc("trim", "Trim windows (A/B), fade-in at A, fade or cut at B: what set_trim stores, what _start sets on the deck, and the gain curve near B.", cases)


# ------------------------------------------------------------------------------------------------ end_actions.json
async def end_actions():
    cases = {}
    lib = {"a.wav": 2}
    stamps = (0.0, 1.0, 1.75, 2.0, 2.25, 3.75, 4.0, 4.25, 6.0, 9.0)

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
            rows, ended, _ = timeline(r, 9.0)
            ideal_end = {"default": 2.0, "once": 4.0, "loop": None, "stop": 2.0}[end]
            assert (ended is None) == (ideal_end is None) and (ended is None or 0 <= ended - ideal_end <= END_TOL + 1e-6)
            cases[f"track_2s_end_{end}"] = {"_info": "2 s track, playlist mode stop; ticks every 0.25 s from the start (so ended_at_s is on that 0.25 s grid, and ideal_ended_at_s is the end of the last pass). passes: 2 for once; loop = started with loops=-1", "deck_at_start": first, "ended_at_s": ended, "ideal_ended_at_s": ideal_end, "tolerance_s": END_TOL, "rows": rows}
        r.reset([{"name": "A", "tracks": ["a.wav"], "mode": "stop"}])
        r.P.set_end(0, 0, "once")
        r.P.play(0, 0)
        rows, ended, _ = timeline(r, 6.0, actions={1.0: lambda: r.P.set_end(0, 0, "default")})
        cases["once_switched_off_in_pass_1"] = {"_info": "end action set back to default at 1.0 s: the pass that is running is played out, then it ends", "ended_at_s": ended, "ideal_ended_at_s": 2.0, "tolerance_s": END_TOL, "rows": rows}
        assert 0 <= ended - 2.0 <= END_TOL + 1e-6
        r.reset([{"name": "A", "tracks": ["a.wav"], "mode": "stop"}])
        r.P.set_end(0, 0, "loop")
        r.P.play(0, 0)
        rows, ended, _ = timeline(r, 6.0, actions={3.0: lambda: r.P.set_end(0, 0, "default")})
        cases["loop_switched_off_in_pass_2"] = {"_info": "end action set back to default at 3.0 s (pass 2 running): that pass is played out, then it ends", "ended_at_s": ended, "ideal_ended_at_s": 4.0, "tolerance_s": END_TOL, "rows": rows}
        assert 0 <= ended - 4.0 <= END_TOL + 1e-6
        r.reset([{"name": "A", "tracks": ["a.wav"], "mode": "stop"}])
        order = []
        for _ in range(8):
            order.append(r.P.end_of(0, 0))
            r.P.set_end(0, 0)
        cases["end_action_cycle"] = {"_info": "set_end with no value cycles default > once > loop > stop", "sequence": order}
    return doc("end_actions", "Per-track end actions: pass counts, remaining time per pass and the moment the track ends (fake clock, 0.25 s steps).", cases)


# ------------------------------------------------------------------------------------------------ play_modes.json
async def play_modes():
    cases = {}
    lib = {"a.wav": 2, "b.wav": 2, "c.wav": 2, "u.wav": 2, "v.wav": 1}
    pls = [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav"]}, {"name": "B", "tracks": ["u.wav", "v.wav"]}]
    async with Rig(lib, pls) as r:
        P = r.P
        await r.load(*lib)
        rows = []
        for mode in ("stop", "loop_playlist", "next_playlist", "shuffle"):
            for end in ("default", "once", "loop", "stop"):
                for t in (0, 2):
                    r.reset(pls)
                    random.seed(1234)
                    P.set_play_mode(0, mode)
                    P.set_play_mode(1, mode)
                    P.set_end(0, t, end)
                    P.play(0, t)
                    prev = r.live()
                    after = "same"
                    for _ in range(80):                         # up to 20 s: long enough for two passes of a 2 s track
                        r.fake.t += 0.25
                        P.tick()
                        d = r.live()
                        if d is not prev:
                            after = "stopped" if d is None else {"playlist": d.pt[0], "track": d.pt[1]}
                            break
                    if mode == "shuffle" and isinstance(after, dict) and end in ("default", "once"):
                        after = {"playlist": after["playlist"], "any_other_track_of_the_playlist": after["track"] != t}   # the choice is random: only the property is the contract
                    rows.append({"mode": mode, "end_action": end, "track": t, "after": after})
        cases["after_a_track_ends"] = {"_info": "playlist A has 3 tracks, B has 2. 'same' = the same deck is still playing (loop). shuffle: only 'another track of the same playlist' is promised",
                                       "rows": rows}
        rows = []                                              # next_in_order, pure
        for mode in ("stop", "loop_playlist"):
            r.reset(pls)
            P.set_play_mode(0, mode)
            rows.append({"mode": mode, "from_track": [0, 1, 2], "next_in_order": [P.next_in_order(0, t) for t in (0, 1, 2)]})
        r.reset(pls)
        P.set_play_mode(0, "stop")
        P.set_end(0, 1, "loop")
        rows.append({"mode": "stop, track 1 set to loop", "next_in_order": [P.next_in_order(0, t) for t in (0, 1, 2)]})
        cases["next_in_order"] = {"_info": "indices to try, best first, for what follows track t (stop: nothing; loop_playlist: t+1 first then the rest in a ring; a looping track repeats itself)", "rows": rows}
        r.reset(pls)                                           # shuffle bag properties
        P.set_play_mode(0, "shuffle")
        random.seed(20240229)
        cur, seq = 0, []
        for _ in range(30):
            cur = P.next_in_order(0, cur)[0]
            seq.append(cur)
        no_repeat = all(a != b for a, b in zip([0] + seq, seq))
        r.reset(pls)
        P.set_play_mode(0, "shuffle")
        random.seed(7)
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
        random.seed(7)
        counts, cur = {0: 0, 1: 0, 2: 0}, 0
        for _ in range(300):
            cur = P.next_in_order(0, cur)[0]
            counts[cur] += 1
        cases["shuffle_bag"] = {"_info": "properties are the contract; the sequence for a fixed Python random seed depends on the Python version and is NOT compared (_info_sequence)",
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
            cases[label] = {"_info": info, "triggers": triggers_, "trim": trim_ or {}, "fires": list(fires), "ideal_fires": ideal, "tolerance_s": TRIG_TOL}
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
def _pcm(windows):
    import numpy as np
    a = np.zeros((len(windows) * 480, 2), dtype="<i2")
    for i, (l, rr) in enumerate(windows):
        a[i * 480:(i + 1) * 480, 0], a[i * 480:(i + 1) * 480, 1] = l, rr
    return a.tobytes()


async def duck_loop_cases():
    """The real _duck_loop under the fake clock: one loop iteration = one 10 ms step of fake time (asyncio.sleep is replaced for the duration)."""
    import wave
    import numpy as np
    out = {}
    voice = [(0.3, 0), (0.7, 16384), (0.5, 4096), (0.5, 0)]            # (seconds, constant sample value in both channels): 2 s, loud then quieter then silent
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
            out[label] = {"settings": settings, "step_s": 0.01, "look_ahead_s": 0.02, "voice_over": {"file": "voice.wav", "starts_at_s": voice_start, "length_s": 2.0, "level_pct": settings["top_track_pct"],
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
        cases["duck_key"] = {"_info": "RMS (0..1) of the louder channel per 10 ms window of 48 kHz stereo 16-bit; the input is, per 10 ms: 5 silent, 10 at (16384, 8192), 5 at (3277, 0), 5 silent, 3 at (1000, 16384)",
                             "key": [r6(x) for x in key]}
        rows = []
        for level, ratio, thr, hold in ((1.0, 6.0, -30.0, False), (1.0, 6.0, -30.0, True), (1.0, 2.0, -20.0, False), (0.5, 4.0, -30.0, False), (1.0, 1.0, -30.0, False), (1.0, 100.0, -60.0, False), (2.0, 6.0, -30.0, True)):
            tg = dsp.duck_curve(key, level, ratio, thr, hold)
            rows.append({"level": level, "ratio": ratio, "threshold_db": thr, "hold": hold, "reduction_db": [r6(x) for x in tg]})
        cases["duck_curve"] = {"_info": "dB of reduction wanted per 10 ms before smoothing: max(0, dB(key*level) - threshold) * (1 - 1/ratio), capped at 60 dB; hold keeps the 75th-percentile depth from the first to the last active window",
                               "rows": rows}
        rows = []
        for attack, release, tgt_seq in ((10, 500, [12.0] * 30 + [0.0] * 120), (50, 1000, [20.0] * 20 + [6.0] * 40 + [0.0] * 200), (1, 1, [10.0, 0.0, 10.0, 0.0])):
            gr, series = 0.0, []
            for tg in tgt_seq:
                gr = dsp.duck_smooth(gr, tg, 0.01, attack, release)
                series.append(r6(gr))
            rows.append({"attack_ms": attack, "release_ms": release, "dt_s": 0.01, "target_db": tgt_seq if len(tgt_seq) <= 8 else {"pattern": "constant segments", "segments": _segments(tgt_seq)}, "gr_db": series})
        cases["duck_smooth"] = {"_info": "one step per 10 ms: gr += (tgt - gr) * (1 - exp(-dt/tau)); tau = attack when tgt > gr else release (min 1 ms); snaps to 0 when tgt == 0 and gr < 0.05",
                                "rows": rows}
        cases["background_gain"] = {"_info": "the background deck volume is multiplied by 10^(-gr/20) (Deck.duck)", "rows": [{"gr_db": g, "multiplier": r6(10 ** (-g / 20.0))} for g in (0, 3, 6, 12, 20, 40, 60)]}
        rows = []
        for rms, gain, ratio, thr in ((0.5, 0.0, 6.0, -30.0), (0.01, 0.0, 6.0, -30.0), (0.01, 20.0, 6.0, -30.0), (0.1, -10.0, 3.0, -25.0), (0.0, 0.0, 6.0, -30.0)):
            rows.append({"rms": rms, "gain_db": gain, "ratio": ratio, "threshold_db": thr, "reduction_db": r6(dsp.input_target_db(rms, gain, ratio, thr))})
        cases["input_target_db"] = {"_info": "Live input detector: the same gain computation as duck_curve (hold off), with its own threshold", "rows": rows}
        cases["duck_loop"] = {"_info": "the REAL _duck_loop and Play on Top under the fake clock: background deck + a 2 s voice-over (0.3 s silence, 0.7 s at 16384, 0.5 s at 4096, 0.5 s silence, stereo 48 kHz), sampled every 10 ms from 0.5 s before the voice-over until after the release. target_db = the duck_curve value the loop reads at top_pos + 20 ms (look-ahead); gr_db = smoothed reduction; bg_multiplier = Deck.duck of the background (applied only when it moved by more than 0.0005, so it can trail 10^(-gr/20) by that). Index 49 is the last background-only sample (t = 0.5 s, voice-over not started), index 50 is the voice-over starting at the same time (top_pos 0); from index 51 every row is 10 ms later, with the reduction computed by the loop at that time.",
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
        rows = []
        for label, raw in (("1 kHz sine, -20 dBFS peak, 5 s, stereo", sine(-20, 5)), ("1 kHz sine, -6 dBFS peak, 5 s", sine(-6, 5)), ("1 kHz sine, -30 dBFS peak, 5 s", sine(-30, 5)),
                           ("100 Hz sine, -20 dBFS peak, 5 s", sine(-20, 5, 100.0)), ("10 kHz sine, -20 dBFS peak, 5 s", sine(-20, 5, 10000.0)),
                           ("1 kHz sine, -20 dBFS, left channel only", sine(-20, 5, silent_second_channel=True)), ("silence 5 s", bytes(48000 * 4 * 5)),
                           ("too short (0.3 s)", sine(-20, 0.3)), ("1 kHz sine, -20 dBFS, 12 s", sine(-20, 12))):
            v = dsp.lufs_from_pcm(raw)
            rows.append({"signal": label, "lufs": None if v is None else round(v, 3)})
        cases["lufs_from_pcm"] = {"_info": "integrated loudness (ITU-R BS.1770 K-weighting, 400 ms blocks, -70 LUFS absolute and -10 LU relative gates) of 48 kHz 16-bit stereo; None = silent or shorter than 0.4 s. Rounded to 3 decimals (compared with a 0.01 LU allowance: _tolerance_lufs)",
                                  "rows": rows}
        rows = []
        lufs = {"a.wav": -14.0, "b.wav": -23.0, "c.wav": None}
        for fid, v in lufs.items():
            L.LOUD[fid] = (0, 0, v)
        for label, cfg_ in (("off", {"mode": "off"}), ("track: reference b (-23)", {"mode": "track", "ref": 1}), ("track: reference a (-14), never boosts", {"mode": "track", "ref": 0}),
                            ("lufs: target -18", {"mode": "lufs", "lufs": -18.0}), ("lufs: target -10 (above all: no boost)", {"mode": "lufs", "lufs": -10.0}), ("lufs: target -60 (clamped)", {"mode": "lufs", "lufs": -80.0})):
            P.playlists[0].pop("norm", None)
            P.playlists[0]["norm"] = dict(L.NORM_DEFAULT)
            L.set_norm(0, cfg_.get("mode"), cfg_.get("ref"), cfg_.get("lufs"))
            rows.append({"setting": label, "measured_lufs": [lufs[x] for x in ("a.wav", "b.wav", "c.wav")], "gain_db": [None if L.norm_gain_db(0, t) is None else r6(L.norm_gain_db(0, t)) for t in range(3)],
                         "gain_linear": [r6(L.norm_gain(0, t)) for t in range(3)], "stored": dict(P.playlists[0]["norm"])})
        cases["norm_gain"] = {"_info": "gain_db = min(0, target - measured), target = the reference track's LUFS (track mode) or the fixed LUFS (lufs mode, -60..0, 0.1 steps); never boosts; None = not applicable (off, or the track has no measurement); linear = 10^(dB/20), 1.0 when no gain", "rows": rows}
        rows = []                                           # applied to a live deck
        r.reset()
        P.playlists[0]["norm"] = dict(L.NORM_DEFAULT)
        L.set_norm(0, "lufs", None, -23.0)
        await r.load("a.wav")
        P.play(0, 0)
        d = r.live()
        rows.append({"track": "a.wav (-14 LUFS), target -23", "deck_gain": r6(d.gain), "deck_gain_db": r6(20 * math.log10(d.gain))})
        L.set_norm(0, "off")
        rows.append({"track": "after switching level match off", "deck_gain": r6(d.gain)})
        cases["applied_to_deck"] = {"_info": "Deck.gain follows level match immediately (apply_gain_live); the channel volume is vol * gain * duck * duck_in * live_volume", "rows": rows}
    d = doc("levelmatch", "Level match: integrated loudness (LUFS) of synthetic signals and the per-track gain it gives (only ever turns a track down).", cases)
    d["tolerance_lufs"] = 0.01
    return d


# ------------------------------------------------------------------------------------------------ resume.json
async def resume():
    cases = {}
    pls = [{"name": "A", "tracks": ["a.wav", "b.wav"]}]
    async with Rig({"a.wav": 60, "b.wav": 60}, pls, cfg={"resume_on_start": True, "resume_max_age_s": 1800, "resume_save_s": 5}) as r:
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
        for label, setup in (("playing, 12.5 s in", None), ("paused at 7.25 s", "pause")):
            r.reset(pls)
            P.RESUME.unlink(missing_ok=True)
            P.play(0, 1)
            r.rebase()
            r.at(12.5 if setup is None else 7.25)
            if setup == "pause":
                P.pause_all()
                r.at(20.0)                                          # time passes while paused: the position does not
            P.save_resume(force=True)
            rows.append({"case": label, "record": saved()})
        r.reset(pls)                                                # what is NOT recorded
        P.RESUME.unlink(missing_ok=True)
        P.play(0, 0)
        r.at(3.0)
        P.stop_all()
        P.save_resume()
        rows.append({"case": "after a deliberate stop", "record": saved()})
        P.play(0, 0)
        r.at(3.0)
        P.fade_out(1000)
        P.save_resume()
        rows.append({"case": "while fading out", "record": saved()})
        cases["record"] = {"_info": "save_resume: pt = [playlist, track], id = library file, pos = seconds in the FILE (a paused track keeps its position), paused flag; removed when nothing plays or a fade-out is running", "rows": rows}
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
        cases["try_resume"] = {"_info": "at start-up. offset = where in the file the sound begins; a resumed start never fades in (start_vol 1, fade_in_ms 0), even when the track has a fade-in at A; an old or unknown record is dropped", "rows": rows}
        r.reset(pls)
        P.playlists[0]["trims"] = {"a.wav": {"in": 2.0, "out": 40.0, "start": "fade", "fade_in_ms": 1500}}
        P.RESUME.write_text(json.dumps({"pt": [0, 0], "id": "a.wav", "pos": 20.0, "paused": False, "saved": r.clock.time() - 5}))
        P.try_resume()
        for _ in range(20):
            await asyncio.sleep(0)
        d = r.live()
        cases["resume_inside_a_trim"] = {"_info": "trim A=2 B=40 with a fade-in; resume at 20 s", "started": None if d is None else {"base_s": r6(d.base), "lo_s": r6(d.lo), "hi_s": r6(d.hi), "start_vol": r6(d.vol), "fade_in_ms": d.fade_in_ms, "fresh": d.fresh}}
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
        return asyncio.run(_all())
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


def diff(a, b, tol, path="", out=None, limit=40):
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
                diff(a[k], b[k], tol, f"{path}/{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} (committed) vs {len(b)} (new)")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, tol, f"{path}[{i}]", out, limit)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if abs(a - b) > tol:
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
        for line in diff(strip_info(old), strip_info(d), tol, name):
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
