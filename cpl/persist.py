"""Writing playlists.json (save) and state.json (save_state).

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import json, shutil

from cpl import state as S
from cpl.config import CFG, DATA, STATE
from cpl.state import DEV_MISSING, FOLDER_COLORS, FOLDER_FLAGS, FOLDER_ICONS, bump, library, playlists
from cpl.util import atomic_write, log_once


def save():
    text = json.dumps({"version": 2, "playlists": playlists, "known": sorted(library),
                       "folder_colors": FOLDER_COLORS, "folder_icons": FOLDER_ICONS, "folder_flags": FOLDER_FLAGS}, indent=2)
    if DATA.exists():
        try:
            shutil.copy2(DATA, DATA.with_suffix(".bak"))      # one generation back, in case the new file is ever bad
        except OSError as e:
            print("could not write playlists.bak:", e)
    atomic_write(DATA, text)
    bump()
    for hook in S.on_save:                # request_loudness (registered below, F3)
        hook()


def save_state():
    """Remember the choices made in the web page (output device, play mode); they override config.json."""
    try:
        atomic_write(STATE, json.dumps({"audio_device": CFG["audio_device"] or DEV_MISSING.get("output"), "preview_device": CFG["preview_device"], "mirror_device": CFG["mirror_device"], "mirror_enabled": CFG["mirror_enabled"], "output_aliases": CFG["output_aliases"],
                                        "preview_volume": CFG["preview_volume"], "live_volume": CFG["live_volume"], "time_warning": CFG["time_warning"], "go_transition": CFG["go_transition"],
                                        "input_device": CFG["input_device"], "input_channel": CFG["input_channel"], "input_channels": CFG["input_channels"], "input_gain_db": CFG["input_gain_db"], "input_threshold_db": CFG["input_threshold_db"], "input_armed": CFG["input_armed"],
                                        "watchdog": CFG["watchdog"], "player_name": CFG["player_name"], "push_enabled": CFG["push_enabled"], "push_url": CFG["push_url"], "push_events": CFG["push_events"], "push_hold": CFG["push_hold"], "health_preview_amber": CFG["health_preview_amber"]}))
    except Exception as e:
        log_once("state.json", "could not save state.json (the chosen output device will not be remembered)", e)
