# Known test failures: none

The 38 failures of the first baseline (`tests/reports/baseline-pre-split/`, tag `pre-split`) were all fixed before the Python split (tag `post-fixes`). `python tests/run.py` now gives 370 passed, 0 failed, 1 skipped (macOS memory readout); see `tests/reports/baseline-post-fixes/`. Any failure is a regression.

| Group (tests) | Fix | Commit |
|---|---|---|
| Superscript digits in command paths (11) | `is_uint()` (ASCII digits only) replaces `str.isdigit()` everywhere | d33d299 |
| Non-finite crossfade time and other numbers (4) | `OverflowError`/finite checks in `set_xfade`, `set_trim`, `set_norm`, `set_live_volume`, `seek_live`, duck step, preview volume, transition settings, OSC ms | c0efd8b |
| Non-numeric playlist/track id in the URL (10) | `route_int()` gives 404 | 238488d |
| Malformed add bodies and uploads (4) | 400 for bad `files`/`index`, and for a body that is not multipart | 6892b95 |
| Preview control bad numbers (6) | 400 for non-numeric or non-finite `seek`/`vol` | 291a02a |
| `focus_t<N>` description (1) | slice `k[7:]`; golden `api_variables.json` updated in 35cc3b7 | b8e8064 |
| Playlist name length on create (1) | `PL_NAME_MAX` shared with rename | b92a794 |
| S2: ducking leak after stop-all (1) | `stop_all()` clears the duck state | 27d12f5 |

## Without ffmpeg (found by the `/nope/ffmpeg` run of split step P5/P6)

`python tests/run.py` with `CPTEST_EXTRA_CONFIG='{"ffmpeg_path": "/nope/ffmpeg"}'` (CLAUDE.md Testing step 5) used to fail `test_storage_formats_ffmpeg_shapes` on every build (split-P4 and later): it expected `GET /api/formats?deep=1` to answer 200, but without ffmpeg the deep format check is refused with 415 `ffmpeg was not found`, which is correct. The deep call is now its own test, `test_the_deep_format_check_is_accepted`, that skips with that reason when the instance has no ffmpeg; the 415 answer itself is asserted in `tests/api/test_file_facts.py`. With ffmpeg both pass; without it the shapes test passes and the deep test is skipped. Not an application bug.

## Found by the gap tests (branch `split`, tag `split-gap`)

No test had to be marked `xfail`: the player behaved as the tests expected everywhere the gap tests look (resume, fades and crossfades, auto-advance, ducking numbers, tick order, and the captured output). Every assertion that failed on the first run was a wrong assumption in the test, corrected (arithmetic of a paused fade, the value of a fade near its end, the timing of the advance matrix, and the alignment of the ducking release in the captured file). Things the investigations found that are NOT test failures, for you to decide:

| # | Observation | Evidence | Status |
|---|---|---|---|
| 1 | A track whose file is deleted AFTER the warm-up decoded it is flagged "missing" but still plays, from RAM (decoded sounds are cached by path; a rescan does not drop them; only delete-through-the-API, rename and eviction do). The old `test_missing_file_in_a_playlist...` raced with the warm-up and failed once in the P2 full run. | the test now restarts the player (empty cache) for the "fails safely" case and has a second test, `test_a_file_that_vanished_after_it_was_decoded_is_flagged_but_still_plays_from_memory`, that documents the cached case; 40 runs each on v2.7.0 and split-P3, 0 failures | open question: acceptable for a show (it keeps playing); not checked: a file REPLACED on disk by another with the same name would also keep playing the old audio until evicted or restarted |
| 2 | The `--preview` helper (preview / mirror / Solo worker) sometimes ends badly when the player closes its stdin: exit by SIGSEGV (2 of 300 runs on split-P1, 8 of 300 on split-P3) and a traceback from its status thread (`Exception in thread ... (_status)`, 4 of 300 on split-P1, 2 of 300 on split-P3). The same code runs on both builds (the helper only moved in P2), so this is older than the split. | loops of 150-300 runs in the investigation (stdin closed 20-100 ms after a play command; the loop script was not kept) | most likely cause (not proven; the 3-line traceback is cut off by the interpreter shutting down, and PYTHONFAULTHANDLER printed no C stack): the daemon status thread keeps calling into pygame / SDL while the interpreter and the mixer are being torn down. It affects only the helper process at its exit (the player process and its main output are separate processes); the player starts a new helper when it needs one |
| 3 | The Solo monitor (and the Mirror output) start playing a new live track 90 ms to about 0.6 s late, so the first samples are missing there; the live output is intact. | `tests/tools/onset_capture.py`, 117 runs per build, v2.7.0 and split-P3 identical | fix proposed separately, not made |

