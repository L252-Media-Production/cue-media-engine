# Baseline before the split (tag `pre-split`, commit 68fb05e)

Run on macOS arm64, Python 3.12.14, pygame 2.6.1, ffmpeg 8.1.1.

* `python tests/run.py`: **367 tests, 328 passed, 38 failed, 1 skipped**. The failures already existed; they were NOT fixed in the split task. Names in `failed-and-skipped.txt`, detail in `report.md`.
  * 1 x S2 (`test_stopall_while_ducked_does_not_leak_the_duck_into_the_next_play_on_top`), 36 x S3, 1 x S4: mostly "odd input gives HTTP 500 instead of 4xx" (xftime inf, non-numeric playlist id, preview ctl bad numbers, malformed add bodies) and a variable-description completeness check.
  * Skipped: memory readout is not implemented on macOS.
* Stand-alone scripts (`standalone/*.txt`): test_devices, test_devices_ui, test_layout_share, test_live_output, test_move_button all pass; test_triggers: 38 tests OK.
* Compare a later run with: `grep -E '^(FAILED|SKIPPED)' <pytest output> | sort | diff - failed-and-skipped.txt`
