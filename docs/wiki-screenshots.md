# Wiki screenshots

The user guide is the GitHub wiki, a separate repo cloned next to this one (`../cue-media-engine.wiki`). Screenshots live there in `images/` and are produced by a script in this repo, so they can be re-shot after any UI change.

## Rules

- Images go in `../cue-media-engine.wiki/images/`, named after the page and the subject: `trim-dialog.png`, `live-input-card.png`.
- Embed with a relative path: `![Trim dialog](images/trim-dialog.png)`, with a one-line caption or lead-in sentence.
- Capture from a harness instance (generated library, dummy audio, fixed content), never from a real show. One skin and theme (the default), viewport 1280 wide, device scale 1. A phone-width shot (390 wide) only where the layout really differs.
- Crop to the feature (element screenshot), not the whole page. Under about 300 KB each; a few focused shots per page, not dozens. Wiki history keeps every version, so do not re-shoot unchanged images (the script must skip files whose pixels did not change).
- Commit the images and the page edits together in the wiki repo; the capture script is committed in this repo.

## Prompt: build the capture script

> Write `tests/tools/wiki_shots.py`, a stand-alone Playwright script (not part of `tests/run.py`) that captures the wiki screenshots.
>
> - Start a disposable player the way the other Playwright tests do (`harness.appcopy.copy_app`, own `cptest-*` folder, random port, `SDL_AUDIODRIVER=dummy`, generated library of short WAVs with readable names, a few playlists, one track playing so the Live card is populated). Read `tests/README.md` and an existing test such as `tests/test_trim_dialog.py` first and reuse its helpers.
> - Take a SHOTS table: `name -> (setup steps, element selector, viewport)`. Start with `trim-dialog` (`#trdlg` open on a track with A and B set), `live-input-card` (`#inpc` expanded, using the `CP_TEST_INPUT` feed so it shows a signal and ducking), `live-card` (Live meters and transport while playing), `playlists` (playlist header and rows with a trim badge), `layout-edit` (edit mode toolbars). Keep the table easy to extend.
> - Fix everything that makes shots unstable: freeze or hide clocks and elapsed times, disable animations (`prefers-reduced-motion` / injected CSS), wait for fonts and for `rev` to settle, and use the page's own theme and skin defaults.
> - Write PNGs to the directory given by `--out` (default `../cue-media-engine.wiki/images`), crop to the element, and only overwrite a file when the pixels changed (compare decoded pixels, not bytes). Print which files changed. Support `--only name,name`, `--list`, and `--phone` for the 390 px variants.
> - Do not touch the wiki pages or commit anything. Afterwards, list which wiki pages should embed which image and where.
> - Run it twice and confirm the second run changes nothing. Run `tests/test_gates.py` if you touched anything under `tests/` that it scans.

## Adding screenshots for another page

1. Add an entry to the SHOTS table in `tests/tools/wiki_shots.py` (setup steps, selector, viewport).
2. Run `python tests/tools/wiki_shots.py --only <name>` and look at the PNG.
3. In `../cue-media-engine.wiki`, add the embed to the page, then commit images and page together and push.
4. When the UI of a documented feature changes, re-run the script (all shots), review `git status` in the wiki repo, and commit only the images that really changed.
