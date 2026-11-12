"""Shared application state (docs/split-plan.md section 4, split step P4).

Imported everywhere as `from cpl import state as S`.
  * Stable containers (never rebound, only changed in place, so importing them by name is safe; tests/test_state_identity.py):
    playlists, FOLDER_COLORS, FOLDER_ICONS, FOLDER_FLAGS, LIBDIRS, library, focus, decks, ISSUES, DEV_MISSING, DURS.
  * Rebindable scalars are read and written ONLY as S.<name> (never `from cpl.state import <scalar>`): they move here group by group.
  * bump() owns `rev`.
This module imports nothing from the application.
"""

playlists = []                    # [{"name": str, "tracks": [library id, ...]}]
FOLDER_COLORS = {}                 # library folder path -> "#rrggbb" (saved in playlists.json)
FOLDER_ICONS = {}                  # library folder path -> icon name (see ICONS in the web page; saved in playlists.json)
FOLDER_FLAGS = {}                  # library folder path -> {"fav": True, "hidden": True} (only the flags that are set; saved in playlists.json; web page only, never in snapshot())
LIBDIRS = set()                   # every folder under media/library (relative, "/" separated), including empty ones
library = {}                      # library id (path inside media/library, "/" separated) -> size in bytes
focus = [0, 0]                    # [playlist, track] - the cursor (the Cue), never plays by itself
decks = []                        # every Deck currently producing sound (live + fading out)
DEV_MISSING = {}                  # {"output": name} when the saved main output was not there at start-up; kept in state.json until another is chosen
ISSUES = {}                       # problems that make the status light red, by key
DURS = {}                         # library id -> (size, mtime_ns, seconds) ; seconds 0 = unreadable

rev = 0                           # bumped whenever the library or playlists change (web page polls it)

live_deck = None                  # the newest deck = "live"
cue_cleared = False               # True after /clear: no track is cued until one is picked or Next / Prev is used
known = None                      # library ids seen at the last save, to report files added offline
last_scan = {"new": [], "gone": [], "missing": {}}
MONITOR = False                   # solo: the live audio plays on the preview output and the preview itself is muted
LAST_LOAD_ERR = None              # (time, message) of the latest track that failed to load
boot_done = False


on_change = []                    # hook list: callables run by bump() after rev += 1, in this order; the owner of each handler registers it at import (F2)

on_save = []                      # hook list: callables run by save() after the file is written and bump() has run (F3)


def _no_notify(*args, **kwargs):
    return None


notify = _no_notify               # hook: set at import by stateout (push); callers below stateout do S.notify() where they used to call push() (F6)


def bump():
    global rev
    rev += 1
    for hook in on_change:
        hook()
pending = None                  # a trigger waiting for its track: {"token", "pt", "fid", "name", "xfade"}
pending_n = 0
