## What and why

<!-- One or two sentences. -->

## Checklist

- [ ] `python tests/run.py` passes (and `python tests/test_pages_equal.py`, if the page changed).
- [ ] **Changes audio behaviour?** (fades, crossfades, trim, end actions, triggers, ducking, level match, play modes, resume: see `docs/AUDIO-SPEC.md`)
  - [ ] No, it does not.
  - [ ] Yes: fixtures regenerated (`PYTHONHASHSEED=0 python tests/golden-audio/generate.py --write`), spec version bumped (`SPEC_VERSION` in `tests/golden-audio/generate.py` and the first line of `docs/AUDIO-SPEC.md`), CHANGELOG line "Audio spec N" added.
- [ ] CHANGELOG, Help (`static/help.html`) and the wiki updated where behaviour changed.
