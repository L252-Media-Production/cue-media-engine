"""Which audio driver SDL actually selected (alsa, coreaudio, pipewire, pulseaudio, wasapi, dummy ...), for the health report.

pygame has no mixer.get_driver(), so the old report always said "unknown". SDL itself knows: SDL_GetCurrentAudioDriver() returns the name of
the driver in use, or NULL while no audio device has been opened. It is read through ctypes from the same SDL2 library pygame loaded, once a
device is open, and the first good answer is kept. Nothing here touches a device or the stream.
"""
import ctypes, ctypes.util, glob, os


def _candidates():
    try:
        import pygame
        base = os.path.dirname(pygame.__file__)
    except Exception:
        base = ""
    found = []
    if base:
        for pat in ("SDL2.dll", "libSDL2-*.dylib", "libSDL2.so*", "libSDL2-*.so*", ".dylibs/libSDL2-*.dylib",
                    "../pygame.libs/libSDL2-*.so*", "../pygame_ce.libs/libSDL2-*.so*", "../pygame.libs/SDL2.dll"):
            found += sorted(glob.glob(os.path.join(base, pat)))
    sys_lib = ctypes.util.find_library("SDL2")
    if sys_lib:
        found.append(sys_lib)
    return [p for p in found if "SDL2_" not in os.path.basename(p)]


def sdl_getter():
    """-> a function returning SDL's current audio driver name (str) or None, or None when no SDL2 library can be loaded."""
    for path in _candidates():
        try:
            lib = ctypes.CDLL(path)
            fn = lib.SDL_GetCurrentAudioDriver
            fn.restype = ctypes.c_char_p
            fn.argtypes = []
        except Exception:
            continue

        def get(fn=fn):
            v = fn()
            return v.decode("utf-8", "replace") if v else None
        return get
    return None


class Driver:
    """Reads the driver name once a device is open and keeps it. `getter` is injected by tests (a fake SDL layer)."""

    def __init__(self, getter=None):
        self._getter, self._loaded = getter, getter is not None
        self.name = None

    def read(self, device_open):
        if self.name:
            return self.name
        if not device_open:
            return None                    # SDL names no driver before a device is open
        if not self._loaded:
            self._getter, self._loaded = sdl_getter(), True
        try:
            v = self._getter() if self._getter else None
        except Exception:
            v = None
        v = (v or "").strip().lower()
        if v:
            self.name = v
        return self.name

    def text(self, device_open):
        """The value of the "Audio driver:" line."""
        n = self.read(device_open)
        if n:
            return n
        return "not detected (no audio device is open yet)" if not device_open else "not detected (SDL did not name a driver)"
