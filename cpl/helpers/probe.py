"""Helper process (python player.py --probe FILE): print the length in seconds of one audio file.
Runs when this module is imported by the launcher (player.py); imports nothing of the app."""
import os, sys
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")      # as at the top of the old player.py: a pygame banner on stdout would corrupt the child's output

# Helper process: print the length in seconds of one audio file (decoded out here so the player's audio never stalls).
os.environ["SDL_AUDIODRIVER"] = "dummy"
try:
    os.nice(19)
except Exception:
    pass
import pygame
pygame.mixer.init()
print(pygame.mixer.Sound(sys.argv[2]).get_length())
sys.exit(0)
