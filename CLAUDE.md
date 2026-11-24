# Cue Media Engine (CueME)

Cue Media Engine (CueME): playlist audio player for live AV work (L252 Media Production), controlled from Bitfocus Companion and from its own web page. (The code and folders keep the earlier name: `cpl/`, `companionplayer`, `cp_`, `mp_`.) One Python file plus a `static/` folder of web files, no build step.

## Before you start

- Prompts from JC begin with `TARGET REPO: <name>`. This repo is `cue-media-engine`. If the name is different (for example `cue-media-engine-stage-ui` or `kinship`), stop and say so before changing anything. A prompt with no such line is fine to run.
- JC's chat sessions save prompts in `prompts/` (gitignored, numbered files). Run one with `@prompts/NN-name.md`. Never commit that folder.
- Read the topic file before working in its area:
  - `docs/claude/architecture.md`: the `cpl/` modules, how the engine, web page and commands work, the control surface (HTTP, OSC, command grammar, variables).
  - `docs/claude/companion-module.md`: the Companion module and its version rules.
  - `docs/claude/testing.md`: the test harness, page-equality check and the manual test methods.
  - `docs/AUDIO-SPEC.md`: what counts as audio behaviour.
- **Audio behaviour is a contract with CueME Stage** (the Swift app, repo `cue-media-engine-stage`). It keeps a read-only copy of `docs/AUDIO-SPEC.md` and the `tests/golden-audio/` fixtures, synced by its `scripts/sync-audio-spec.sh`. A change that alters a number in the spec changes the spec; say in your report that Stage needs a re-sync.

## Layout

| File | What it is |
|---|---|
| `player.py` | Launcher only (31 lines): puts its folder on `sys.path`, checks that `cpl/` and `static/` exist, starts a helper (`--probe/--decode/--dl/--preview/--input`, imported from `cpl/helpers/` BEFORE any app import) or imports `cpl.legacy` and calls `run()`. The child processes are started from this path (`LAUNCHER`). |
| `cpl/` | The app, split into modules (since 2.7.1; plan and status: `docs/split-plan.md`, steps P1-P6 done). Foundation modules: `clock` (the one time source; tests install a fake), `util`, `dsp`, `config` (paths, `CFG`), `state` (shared state and hook lists). To find a function, grep `cpl/`; list the files with `ls cpl/`. The full module inventory is in `docs/claude/architecture.md`. |
| `static/` | The web files, read at start-up: `index.html` (page skeleton, head theme script inline), `style.css`, `app.js` (classic script; carries two include lines `//@include icons.js` and `//@include tour.js`), `icons.js` (`const ICONS`), `tour.js` (`const TOUR`), and the separate pages `help.html`, `stage.html`, `variables.html`. `build_ui()` puts them together into ONE page (index.html has `<!--@include style.css-->` and `<!--@include app.js-->`), then does the four generated-piece replacements and asserts no `@@` or include marker is left; the result is cached (`CP_DEV_UI=1` re-reads the files on every request of `/`, for editing without a restart). The player exits with a message if `static/` is incomplete. **Deploy `player.py`, `cpl/` and `static/` together.** |
| `requirements.txt` | `pygame` (Linux/Mac), `pygame-ce` (Windows, via markers), `python-osc`, `aiohttp`, `numpy`, `scipy`, `yt-dlp`. |
| `run-player.bat` | Windows launcher (CRLF): creates `.venv`, runs `pip install --upgrade -r requirements.txt` only when `requirements.txt` differs from the stamp `.venv\\requirements.installed` (a failed update is not fatal when the core packages are already installed, e.g. offline), checks that `cpl\\__init__.py` and `static\\help.html` exist, then runs `player.py`. `run-player.command` is the macOS twin (executable, mode 100755). `deploy/deploy.sh` and `deploy/deploy.ps1` copy `player.py`, `cpl/`, `static/` (and `run-player.bat` on Windows) from the source clone to the install folder. `tests/test_launchers.py` fails if one is empty (a deploy commit once emptied `run-player.bat`). |
| `packaging/` | The Debian package: `build-deb.sh` (host, Docker) runs `build-in-container.sh` in `debian:<codename>`; `control.in`, the maintainer scripts `postinst`/`prerm`/`postrm`, the unit `cue-media-engine.service`, the `/etc/default` file `default`, `lintian-overrides`. Built for Debian 12/13 x amd64/arm64 by `.github/workflows/deb.yml`: on `release/**` pushes (artifacts only, version `<APP_VERSION>~ci.<sha>`) and on `v*` tags (version from the tag via `ci-version.sh`, draft Release). See `packaging/README.md`; tested by `tests/test_deb_packaging.py`. |
| `README.md` | Short landing page (pitch, security, quick start, links). The user guide is in `docs/wiki/` (staged for the GitHub wiki; see `docs/wiki/README.md`); developer detail (API, data shapes, design notes) is in `docs/api-reference.md` and `docs/live-input-design.md`. Keep them in step with the code. |
| `config.json` | Created at first run. Read with a tolerant parser (trailing commas are accepted). |
| `playlists.json`, `state.json`, `durations.json` | Runtime data. Do not hand-edit while the player runs. |
| `media/library/` | The audio library (folders allowed). |

The Companion module is a separate project (`companion-module-companionplayer`, see `docs/claude/companion-module.md`).

## Where it runs

- **Production target:** Linux (Debian), headless, run as a systemd service, with audio out through a USB audio interface. Bitfocus Companion usually runs on the same machine; shell-command support must be enabled in Companion for buttons that run `systemctl`.
- **Windows:** supported for testing and portable rigs (pygame-ce).
- **macOS:** runs, but the memory readout is not implemented there.

## Run it

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python player.py
```

Web UI: `http://<host>:8080`. Defaults in `CFG`: `http_port` 8080, `osc_in_port` 9000, `companion_host` 127.0.0.1, `companion_osc_port` 12321, `var_prefix` `mp_`, `cache_mb` 768.

## Conventions and gotchas

- **Audio spec (golden fixtures):** `docs/AUDIO-SPEC.md` (spec version N, "matches v2.8.0") is the contract for everything the player does with sound; a second engine (CueME Stage, Swift) is built to match it. `tests/golden-audio/` holds `generate.py` (measures the real code with the fake clock and the dummy mixer; `PYTHONHASHSEED=0 python tests/golden-audio/generate.py [--write]`), the committed `fixtures/*.json` (each carries `spec_version`; a file may not be named like a runtime file in `.gitignore`, e.g. `resume.json`), and `renders/` (WAV renders of the real mixer with `render.py --check|--write|--repeat`, a separate command: not bit-for-bit repeatable, so tolerances). `tests/engine/test_golden_audio.py` is run by `tests/run.py` and fails with a readable diff. **Rule: any change that alters audio behaviour (fades, crossfade times, end actions, trim, triggers, ducking, level match, play modes, resume) must regenerate the fixtures, bump `SPEC_VERSION` in `generate.py` and the first line of `docs/AUDIO-SPEC.md`, and add a CHANGELOG line "Audio spec N".** The PR template has the checklist. A fix that only changes what is not audio (page, HTTP, OSC, health, settings) needs none of this.
- **Gates (run by `tests/run.py`):** `tests/test_gates.py` (time only through `cpl.clock`, no function-local `cpl` imports, helpers import no app code, the import graph equals/contains-in `import_allowlist.json` and is acyclic, nothing imports `cpl.legacy`), `tests/test_no_bare_state.py` (no `global` of a shared name, no bare use of a moved scalar, `cpl.state` only as `S`, containers never rebound, `S.x =` only in the writer table, only the listed module-private names may be rebound with `global`, no by-name import of a patched function), `tests/test_state_identity.py`, `tests/test_state_hooks.py` (hooks are registered after the import and called in order), `tests/test_launchers.py`, `tests/test_module_version.py` (player 2.7.x + module 2.7.0 = ok). Moves between modules are proved with `tests/tools/verify_move.py` / `verify_step.py` (normalised AST) and done with `tests/tools/move_defs.py` / `state_rewrite.py`.
- **Release:** bump `APP_VERSION` (`cpl/config.py`), regenerate the golden hashes in their own commit (`python tests/test_pages_equal.py --update`, only the version fields may differ), update `CHANGELOG.md`, run the full suite twice, tag `vX.Y.Z-rcN` on the release branch. `dist/*.zip` is built with `git archive` and not committed.
- **Split workflow (branch `split`, plan `docs/split-plan.md`):** commits are prefixed with the step (`P4:`, `P5/P6:`, `Tests:`). After creating a `split-*` tag, push the branch and that tag only: `git push origin split` and `git push origin <tag>` (set the upstream once with `git push -u origin split`). Push only `split`, `split-*` tags, the `release/*` branch of a release and its `vX.Y.Z-rcN` tags: never `main` (see the promotion rule below), never `--force`, never delete or move a pushed tag; if a pushed tag would have to move, stop and ask. If a push fails or hangs (`git ls-remote` hung once), report it and carry on; do not retry with force. Report the pushed refs in each stop report. To test a split build on the NUC or Windows the branch/tag must be pushed (see the deploy note in the plan).
- **Promotion rule (main):** `main` is only ever updated by a fast-forward promotion of a tested `release/*` branch (`git push origin <tested-commit>:refs/heads/main`, never forced), on the owner's explicit request, and the release tag `vX.Y.Z` (annotated, on that same commit) is created at the promotion and pushed alone. First verify that `origin/main` is an ancestor of the release commit, that the `-rcN` tag and the release branch tip are the same commit, and that the remote has no `vX.Y.Z` yet. 2.7.2 was promoted this way (`077cabb` = `v2.7.2-rc4` = `v2.7.2`).
- The minimum Python is 3.11 (Debian 12): no nested same-type quotes in f-strings, no `type` statements or generic syntax; `tests/test_py311_syntax.py` and the `.deb` build check it.
- Line endings: `.gitattributes` has `* text=auto eol=lf`, so `static/` and `player.py` are LF in every checkout (only `*.bat` / `*.ps1` are CRLF). As a second guard `_static()` turns CRLF into LF when it reads a file, so a copy with CRLF (autocrlf off in the repo, or files copied by hand on Windows) still assembles the identical page and the `//@include` / `<!--@include` marker checks still match; LF files are read byte for byte. Test: `tests/test_static_crlf.py` (CRLF copy of `static/`, golden hashes of `/`, `/help`, `/stage`, `/variables`).
- Version: `APP_VERSION` in player.py is the one product version (Settings footer line `CompanionPlayer x.y.z`, `/api/state` `version` and `player_version`, Companion variable `player_version`). The Companion module has the same major.minor and warns (log + variable `version_match`) when they differ. Bump it together with the module version and `CHANGELOG.md`.
- `player.py` plus `static/`: no build step. The UI is plain files in `static/` (no Python string quoting any more); keep `app.js` a classic script (148 inline `on*=` handlers need globals) and the include markers once each.
- Update the user guide (`docs/wiki/`; put API and storage detail in `docs/api-reference.md`, not in the guide), the README only if the quick start changes, and the in-page Help (`static/help.html`) and tour (`static/tour.js`) when behaviour changes.
- The page keeps no state in the browser except small per-viewer conveniences (theme, tour-seen flag in `localStorage`).
- Backups of earlier versions are kept in `backups/` as `player.pre-*.py` (never next to the working copy); delete them once a version has proven itself.
- Modal `<dialog>`s must stay `position:fixed` (CSS `dialog:modal`): never give `dialog` a bare `position:relative` (it made every modal open in the page flow and jump the page). Dialogs are height-limited and scroll inside, with their last `.row` sticky.
- Companion button text uses a literal `\n` for a line break.
- The player must keep running while Companion restarts; Companion reconnects by polling.
- Do not add a CPU-heavy task to the main tick; audio glitches are the failure that matters most.
- Docker Compose files, if any are added, are named `compose.yml`.
- The `.deb` (`packaging/`) installs to `/opt/cue-media-engine`, runs the unit `cue-media-engine` as user `cueme`, and never restarts the service on upgrade (it prints the restart command instead).

## Open ideas

- Optional: Companion variables for the resource monitor (currently shown only in the web page).
- Optional: macOS support (launcher, startup entry, memory readout).
