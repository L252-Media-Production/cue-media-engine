"""A small generated test library: WAV files with known tones and lengths (stdlib only), plus an MP3 and a FLAC when ffmpeg exists."""
import math, shutil, struct, subprocess, wave
from pathlib import Path

# id (relative to media/library) -> (frequency Hz, seconds, level dBFS, channels, sample rate)
WAVS = {
    "tone_a.wav": (440, 3.0, -12, 2, 44100),
    "tone_b.wav": (880, 3.0, -12, 2, 44100),
    "tone_c.wav": (220, 4.0, -12, 2, 44100),
    "short_1s.wav": (660, 1.0, -12, 2, 44100),
    "short_1s_b.wav": (700, 1.0, -12, 2, 44100),
    "short_1s_c.wav": (770, 1.0, -12, 2, 44100),
    "short_2s.wav": (550, 2.0, -12, 2, 44100),
    "loud.wav": (1000, 6.0, -6, 2, 44100),
    "quiet.wav": (1000, 6.0, -30, 2, 44100),
    "long_120s.wav": (300, 120.0, -20, 1, 22050),                 # for seek tests
    "Sub/tone_d.wav": (660, 2.0, -12, 2, 44100),                  # inside a folder
    "Name with spaces & ünï.wav": (500, 2.0, -12, 2, 44100),   # awkward characters in an id
}
FFMPEG_FILES = {"tone_e.mp3": (440, 3.0), "tone_f.flac": (330, 3.0)}


def write_tone(path, freq, secs, db, ch=2, rate=44100):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    amp = 32767 * 10 ** (db / 20.0)
    n = int(round(secs * rate))
    fade = int(0.005 * rate)                                         # 5 ms edges: no clicks, and the end is clean
    frames = bytearray()
    for i in range(n):
        g = min(1.0, i / fade, (n - 1 - i) / fade) if fade else 1.0
        v = int(amp * g * math.sin(2 * math.pi * freq * i / rate))
        frames += struct.pack("<h", v) * ch
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(bytes(frames))


def ffmpeg_exe():
    return shutil.which("ffmpeg")


def generate(lib_dir, ffmpeg_files=True):
    """Write the library into lib_dir. Returns {id: duration_seconds}. ffmpeg_files=False: WAV files only (byte-identical on every machine)."""
    lib_dir = Path(lib_dir)
    out = {}
    for fid, (f, s, db, ch, rate) in WAVS.items():
        write_tone(lib_dir / fid, f, s, db, ch, rate)
        out[fid] = s
    ff = ffmpeg_exe() if ffmpeg_files else None
    if ff:
        for fid, (f, s) in FFMPEG_FILES.items():
            r = subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={f}:duration={s}", "-ac", "2", "-ar", "44100",
                                str(lib_dir / fid)], capture_output=True, timeout=60)
            if r.returncode == 0 and (lib_dir / fid).exists():
                out[fid] = s
    return out
