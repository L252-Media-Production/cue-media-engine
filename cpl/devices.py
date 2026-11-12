"""Output device listing and opening the mixer.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import json, re

import pygame

from cpl.config import CFG
from cpl.helpers.common import test_dev_dir as _test_dev_dir
from cpl.state import DEV_MISSING, ISSUES


# ---------------------------------------------------------------- output devices
def init_mixer(device):
    _td = _test_dev_dir()
    if _td:
        open(_td / "init.log", "a", encoding="utf-8").write(json.dumps(device) + "\n")
        if device and device not in json.load(open(_td / "mock_devices.json", encoding="utf-8")):
            raise RuntimeError("Couldn't find the audio device")   # what SDL does for a name it does not know
        device = None
    pygame.mixer.pre_init(frequency=48000, size=-16, channels=2, buffer=1024)
    # allowedchanges=0: SDL converts to 48 kHz / 16-bit / stereo itself instead of opening the device in another format,
    # because the meters, ducking and level matching all read the decoded audio as exactly that.
    if device:
        pygame.mixer.init(devicename=device, allowedchanges=0)
    else:
        pygame.mixer.init(allowedchanges=0)
    pygame.mixer.set_num_channels(16)
    pygame.mixer.set_reserved(1)           # channel 0 belongs to the watchdog's silent heartbeat (cpl/watchdog.py); tracks never get it
    got = pygame.mixer.get_init()
    if got != (48000, -16, 2):
        ISSUES["audio_fmt"] = f"the output runs as {got}, not 48000 Hz 16-bit stereo; meters and ducking may be off"
        print("Warning:", ISSUES["audio_fmt"])
    else:
        ISSUES.pop("audio_fmt", None)


def _natkey(name):
    """Case-insensitive natural order: 'Out 2' before 'Out 10', '1-2' before '11-12'. Runs of spaces count as one in the
    sort key only (the names themselves are never changed), so 'Transmit  1-2' and 'Transmit 11-12' sort together."""
    return [int(x) if i % 2 else x for i, x in enumerate(re.split(r"(\d+)", re.sub(r"\s+", " ", name.strip().casefold())))]


def list_devices():
    """The output device names exactly as SDL reports them (double spaces and all: they are what pygame must be given
    back), in natural order. Callers must never strip or normalise them."""
    _td = _test_dev_dir()
    if _td:
        return sorted(json.load(open(_td / "mock_devices.json", encoding="utf-8")), key=_natkey)
    try:
        from pygame._sdl2 import audio as sdl_audio
        return sorted(sdl_audio.get_audio_device_names(False), key=_natkey)
    except Exception:
        return []


def list_capture_devices():
    """The input (capture) device names as SDL reports them, natural order, for the Live input. Needs the audio subsystem (the mixer is open by then);
    a test folder (CP_TEST_DEVICES) may hold mock_inputs.json."""
    _td = _test_dev_dir()
    if _td:
        try:
            return sorted(json.load(open(_td / "mock_inputs.json", encoding="utf-8")), key=_natkey)
        except (OSError, ValueError):
            return []
    try:
        from pygame._sdl2 import audio as sdl_audio
        return sorted(sdl_audio.get_audio_device_names(True), key=_natkey)
    except Exception:
        return []


def dev_notices(names):
    """Plain-language notes for saved outputs that are not among the current devices (shown by the page)."""
    out = {}
    hint = " Start the device (for Dante Virtual Soundcard, run it), then press Refresh devices and choose it again."
    if DEV_MISSING.get("output"):
        out["output"] = f"The saved output \"{DEV_MISSING['output']}\" was not found, so the system default is in use." + hint
    if CFG["preview_device"] and CFG["preview_device"] not in names:
        out["preview"] = f"The saved preview output \"{CFG['preview_device']}\" was not found." + hint
    if CFG["input_device"] and CFG["input_device"] not in list_capture_devices():
        out["input"] = f"The saved input device \"{CFG['input_device']}\" was not found. It is retried every few seconds and picked up when it appears." + hint
    if CFG["mirror_device"] and CFG["mirror_device"] not in names:
        out["mirror"] = f"The saved mirror output \"{CFG['mirror_device']}\" was not found." + hint
    return out
