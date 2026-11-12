"""Helper process (python player.py --decode FILE FREQ FMT CHANS): decode one audio file, raw PCM to stdout.
Runs when this module is imported by the launcher (player.py); imports nothing of the app."""
import os, sys
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")      # as at the top of the old player.py: a pygame banner on stdout would corrupt the child's output

# Helper process: decode one audio file and write raw PCM to stdout, then exit.
# Decoding MP3/OGG/FLAC inside the player freezes its audio output for seconds, so it is done out here.
os.environ["SDL_AUDIODRIVER"] = "dummy"
try:
    os.nice(10)                      # never compete with the audio thread for CPU
except Exception:
    pass
import pygame
_path, _freq, _fmt, _chans = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
pygame.mixer.pre_init(_freq, _fmt, _chans, 1024)
pygame.mixer.init()
if pygame.mixer.get_init() != (_freq, _fmt, _chans):
    sys.exit(3)
sys.stdout.buffer.write(pygame.mixer.Sound(_path).get_raw())
sys.stdout.buffer.flush()
sys.exit(0)
