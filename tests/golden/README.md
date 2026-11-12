# Golden outputs (pre-split)

Captured by `python tests/golden/capture.py` from a disposable harness instance (`Instance(wav_only=True)`: the 12 generated WAV files only, no MP3/FLAC, because their bytes depend on the ffmpeg version). `harness/golden.setup()` then creates two playlists ("Golden A": tone_a, tone_b, Sub/tone_d; "Golden B": short_1s, the file with spaces) and sets a loop end action (`0/1/end/loop`) and a track crossfade (`0/0/xftime/2`). `SHA256SUMS` holds the hashes of the stored (normalised) files; `tests/test_pages_equal.py` compares a fresh capture with them.

Captured: `GET /` (root.html), `/help`, `/stage` (default query), `/variables`, `/api/state`, `/api/playlists`, `/api/variables`, `/api/library`.

## What is normalised (everything else is compared byte for byte)

* HTML pages (`/`, `/help`, `/stage`, `/variables`): nothing, raw bytes.
* JSON outputs: parsed and re-written with sorted keys, indent 1, UTF-8 (so key order cannot matter), then:
  * the keys `mem`, `rev`, `storage`, `disk_free`, `allowance`, `storage_free`, `storage_library` are removed at any depth (RAM and disk figures, the revision counter that depends on start-up timing, disk space);
  * the 2.8.0 `health` block in `/api/state`: `status` and `detail` (the old light) are compared; every other key of it (state, summary, checks: they depend on the machine's disk, devices and uptime) becomes `"<varies>"`;
  * the keys `ram` (the block in `/api/state`, and each track's state in `/api/playlists`) and `ram_in` keep their place but the value becomes `"<varies>"` (2.7.3: it depends on how far the background warm-up has got); `ram_total` is compared as it is;
  * entries of `/api/variables` -> `vars` named `storage_free` / `storage_library` are removed;
  * every string matching `127.0.0.1:<digits>` becomes `127.0.0.1:PORT` (random test port in `feedback` and `target`).
* No timestamps, uptimes or random ids were found in these outputs; two captures from two instances gave identical hashes.

Implementation: `tests/harness/golden.py` (`DROP_KEYS`, `DROP_VARS`, `PORT_RE`). Keep this file in step with it.
