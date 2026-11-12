"""numpy-only audio maths with no application imports (docs/split-plan.md 2.1). Step P2 holds what the --preview helper needs;
the ducking maths and lufs_from_pcm join in P3."""
import math
try:
    import numpy as np
except ImportError:                       # meters are optional; everything else works without numpy
    np = None
METER_WIN = 0.05                          # seconds per level reading


def compute_env(raw):
    """Peak level (0..1) of every 50 ms of 48 kHz / 16-bit / stereo audio -> float32 array of shape (n, 2).
    Done in small blocks so a long track doesn't need a big temporary copy."""
    if np is None or not raw:
        return None
    a = np.frombuffer(raw, dtype=np.int16)
    a = a[: len(a) // 2 * 2].reshape(-1, 2)
    win = int(48000 * METER_WIN)
    full = len(a) // win
    out = []
    step = 400                            # windows per block (~ 8 MB of temporary int32)
    for i in range(0, full, step):
        blk = a[i * win:min(full, i + step) * win].reshape(-1, win, 2)
        out.append(np.abs(blk.astype(np.int32)).max(axis=1))
    if len(a) > full * win:
        out.append(np.abs(a[full * win:].astype(np.int32)).max(axis=0, keepdims=True))
    return (np.concatenate(out).astype(np.float32) / 32768.0) if out else None


# ---------------------------------------------------------------- Play on Top: sidechain ducking
# The track played on top is a file that is already in RAM, so what it asks of the background is worked out up front:
# every 10 ms of it is measured, run through threshold / ratio, and the result is a list of "turn the background down
# by X dB". While it plays, a small loop reads that list at the top track's position and applies attack / release.
DUCK_STEP = 0.01


def duck_key(raw):
    """Loudness (0..1 RMS, louder channel) of every 10 ms of a track. Worked out once when the track is loaded; the
    ducking settings are applied to it later by duck_curve, which is cheap."""
    if np is None or not raw:
        return None
    a = np.frombuffer(raw, dtype=np.int16)
    a = a[: len(a) // 2 * 2].reshape(-1, 2)
    win = int(48000 * DUCK_STEP)
    n = len(a) // win
    if n < 1:
        return None
    key = np.empty(n, dtype=np.float32)
    step = 500                                       # windows per block, so a long track needs no big temporary copy
    for i in range(0, n, step):
        blk = a[i * win:min(n, i + step) * win].reshape(-1, win, 2).astype(np.float32) / 32768.0
        key[i:i + len(blk)] = np.sqrt((blk * blk).mean(axis=1)).max(axis=1)
    return key


def duck_curve(key, level, ratio, threshold_db, hold):
    """dB of reduction wanted for each 10 ms of the top track (before attack and release), or None without numpy.
    ratio / threshold_db / hold are the duck_ratio / duck_threshold_db / duck_hold settings, passed in by the caller (this module reads no config)."""
    if np is None or key is None or len(key) == 0:
        return None
    db = 20.0 * np.log10(np.maximum(key * max(level, 1e-4), 1e-6))
    ratio = max(1.0, float(ratio))
    tgt = np.clip(db - float(threshold_db), 0.0, None) * (1.0 - 1.0 / ratio)
    tgt = np.minimum(tgt, 60.0)
    if hold:                             # stay down from the first loud moment to the last, at the typical depth
        act = np.nonzero(tgt > 0.05)[0]
        if len(act):
            seg = slice(int(act[0]), int(act[-1]) + 1)
            depth = float(np.percentile(tgt[seg][tgt[seg] > 0.05], 75))
            tgt[seg] = np.maximum(tgt[seg], depth)
    return tgt.astype(np.float32)


def duck_smooth(gr, tgt, dt, attack_ms, release_ms):
    """One step of the attack / release smoothing of the reduction (dB): `gr` moves toward `tgt` with the attack time constant when going
    down (tgt > gr) and the release time constant when coming back. The ONE implementation: the Play on Top loop and the Live input detector
    both call it, so the same settings give the same movement. Snaps to 0 once the target is 0 and the rest is under 0.05 dB."""
    tau = max(1.0, float(attack_ms if tgt > gr else release_ms)) / 1000.0
    gr += (tgt - gr) * (1.0 - math.exp(-dt / tau))
    if tgt == 0.0 and gr < 0.05:
        gr = 0.0
    return gr


def input_blocks(samples, win):
    """RMS (0..1) of every whole block of `win` frames of int16 audio from the Live input: `samples` is (n,) for one channel or (n, nch).
    Returns (levels, used): one list of per-channel RMS values per block, and the number of frames used."""
    if np is None or len(samples) < win:
        return [], 0
    a = np.asarray(samples)
    if a.ndim == 1:
        a = a[:, None]
    n = len(a) // win
    c = a.shape[1]
    b = a[:n * win].reshape(n, win, c).astype(np.float32) / 32768.0
    return np.sqrt((b * b).mean(axis=1)).tolist(), n * win


def input_target_db(rms, gain_db, ratio, threshold_db):
    """dB of reduction the Live input asks for at a block level `rms` (0..1, before the input gain). The SAME gain computation as the
    Play on Top ducking (duck_curve, hold off), so the threshold and the ratio mean exactly what they mean there."""
    c = duck_curve(np.array([rms], dtype=np.float32), 10.0 ** (float(gain_db) / 20.0), ratio, threshold_db, False)
    return 0.0 if c is None else float(c[0])


def lufs_from_pcm(raw):
    """Integrated loudness (ITU-R BS.1770 / EBU R128, LUFS) of 48 kHz 16-bit stereo PCM, or None when the track is
    too short (< 0.4 s), silent, or scipy/numpy is missing."""
    if np is None:
        return None
    from scipy.signal import lfilter
    a = np.frombuffer(raw, dtype="<i2")
    n = (len(a) // 2) // 4800 * 4800
    if n < 4800 * 4:
        return None
    x = a[:n * 2].reshape(-1, 2)
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]
    z1, z2 = np.zeros((2, 2)), np.zeros((2, 2))
    sub = []
    step = 4800 * 300                                   # 30 s at a time keeps memory small on the Pi
    for s in range(0, n, step):
        c = x[s:min(n, s + step)].astype(np.float64) / 32768.0
        y, z1 = lfilter(b1, a1, c, axis=0, zi=z1)
        y, z2 = lfilter(b2, a2, y, axis=0, zi=z2)
        sub.append((y * y).sum(axis=1).reshape(-1, 4800).mean(axis=1))      # energy of each 100 ms
    sub = np.concatenate(sub)
    blocks = np.convolve(sub, np.ones(4) / 4, mode="valid")                  # 400 ms blocks, 75 % overlap
    lb = -0.691 + 10 * np.log10(np.maximum(blocks, 1e-12))
    keep = blocks[lb > -70.0]
    if len(keep) == 0:
        return None
    rel = -0.691 + 10 * np.log10(keep.mean()) - 10.0
    keep = blocks[lb > max(-70.0, rel)]
    if len(keep) == 0:
        return None
    return float(-0.691 + 10 * np.log10(keep.mean()))
