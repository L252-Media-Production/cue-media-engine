#!/usr/bin/env python3
"""
Cue Media Engine launcher. The program itself is in cpl/ (and the web files in static/): deploy player.py, cpl/ and static/ together.

Runs on macOS, Linux (including Raspberry Pi) and Windows.
    python player.py                         start the player
    python player.py --probe|--decode|--dl|--preview|--input ...    the child processes the player starts itself (handled in cpl/ before any heavy import)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))              # "python -I" does not put the script's folder on sys.path; the cpl package lives next to this file
_gone = [d for d in ("cpl", "static") if not (HERE / d).is_dir()]
if _gone:
    print(f"Cue Media Engine: the folder(s) {', '.join(str(HERE / d) for d in _gone)} not found.\n"
          "Deploy player.py, cpl/ and static/ together (copy all three).", file=sys.stderr)
    sys.exit(1)

# The child processes the player starts from this file run first and import none of the app (no aiohttp, no python-osc, no config):
# each module under cpl/helpers/ does its job when it is imported and ends with sys.exit.
_HELPERS = {"--probe": "probe", "--decode": "decode", "--dl": "dl", "--preview": "preview_worker", "--input": "input_worker"}
if len(sys.argv) > 1 and sys.argv[1] in _HELPERS:
    import importlib
    importlib.import_module("cpl.helpers." + _HELPERS[sys.argv[1]])
    sys.exit(0)

for _s in (sys.stdout, sys.stderr):        # line buffering: a service without PYTHONUNBUFFERED=1 still logs promptly (found on the Pi: nothing reached the journal)
    try:
        _s.reconfigure(line_buffering=True)
    except (AttributeError, ValueError, OSError):
        pass

import cpl.legacy as app                   # the player itself

if __name__ == "__main__":
    app.run()
