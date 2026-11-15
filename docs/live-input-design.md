# Live input: design notes

Moved from the user guide. The operator page is `docs/wiki/Live-Input.md`.

## Isolation

- **Isolation:** capture runs in its own process (`python player.py --input`, `cpl/helpers/input_worker.py`), the only writer of a shared ring (`cpl/helpers/ring.py`: one mono channel, 48 kHz int16, 5.5 s, a memory-mapped file in `_input/`). The **detector** (`cpl/liveinput.py`) and the **Solo tap** (inside the preview worker) are two readers of that ring, each with its **own read pointer** and a read-only mapping. The detector runs in the player process as a small 10 ms task (a few hundred samples copied, one RMS per block, a few float operations; nothing is added to the 50 ms tick): next to the shared ducking settings, with one source of truth and no settings protocol, while the helper stays a dumb pipe that is safe to lose.

## Clock drift

- **Clock drift is ignored in 2.7.5.** Duck only never plays the input into Live, so a separate analog interface cannot drift against the output. It must be revisited (resampling or drift correction) when Play only or Both ships.

## HTTP API and variables

- **Companion / HTTP:** `/input/armed/<on|off|toggle>` and `/input/ducknow/<on|off|toggle>` . Variables `mp_input_armed`, `mp_input_duck_now`, `mp_input_signal`, `mp_input_ducking` (1 / 0). `GET /api/input` (state, device list); `POST /api/input` `{device, channel, gain_db, armed}` (400 with a reason for an unknown device, a channel outside 1-64 or a gain outside −12..+24; nothing changes on a refusal); `POST /api/input/solo` `{on}`; `POST /api/input/ducknow` `{on}`. `/api/state` has an `input` block, the meter stream (`/api/live`, `/api/meters`) has `in_gr` and `input` `{present, signal, level_db}`.

## Settings keys

- **Settings keys** (`state.json`, written as you change them): `input_device`, `input_channel`, `input_gain_db`, `input_armed`. A saved device that is not present at start shows **No input** ("not found") and is picked up when it appears; a bad saved value falls back to its default.
