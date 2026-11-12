"""The Live input's capture ring: one or two channels per frame (int16, 48 kHz) in a memory-mapped file, shared by three processes.

The capture helper (cpl/helpers/input_worker.py) is the only WRITER. The player's detector and the preview worker's Solo tap are READERS, each with its
own read pointer (a plain integer they keep themselves), so one can never move, block or starve the other. A reader maps the file read-only: nothing
a reader does can change what the others see. The number of channels per frame (1 for a single channel, 2 for a stereo pair) is in the header and
only changes together with the epoch (when the helper opens the device again), so a reader that sees a new epoch starts again. Imports only stdlib and numpy (helper rule)."""
import mmap, os, struct

import numpy as np

RATE = 48000
CAP = 1 << 18                       # frames kept (5.46 s)
HDR = 64                            # header: u64 frames written (offset 0), u64 epoch (offset 8; bumped when the device is (re)opened), u64 channels per frame (offset 16)
SIZE = HDR + CAP * 2 * 2            # room for a stereo pair
SAFE = 4096                         # a reader that is further behind than CAP - SAFE frames has lost data and skips ahead


class Ring:
    def __init__(self, path, writer=False, create=False):
        self.path, self.writer = str(path), writer
        if create:
            with open(self.path, "wb") as f:
                f.truncate(SIZE)
        self._f = open(self.path, "r+b" if writer else "rb")
        self._m = mmap.mmap(self._f.fileno(), SIZE, access=mmap.ACCESS_WRITE if writer else mmap.ACCESS_READ)
        self._raw = np.frombuffer(self._m, dtype=np.int16, count=CAP * 2, offset=HDR)
        if create:
            struct.pack_into("<Q", self._m, 16, 1)

    @property
    def written(self):
        return struct.unpack_from("<Q", self._m, 0)[0]

    @property
    def epoch(self):
        return struct.unpack_from("<Q", self._m, 8)[0]

    @property
    def nch(self):
        n = struct.unpack_from("<Q", self._m, 16)[0]
        return n if n in (1, 2) else 1

    def _frames(self, nch):
        return self._raw[:CAP * nch].reshape(CAP, nch)

    def new_epoch(self, nch=None):
        """Writer: the device was (re)opened (with `nch` channels per frame, default: keep). Readers see the epoch change and start from the write position."""
        if not self.writer:
            raise PermissionError("read-only ring")
        if nch is not None:
            if nch not in (1, 2):
                raise ValueError("a ring carries 1 or 2 channels")
            struct.pack_into("<Q", self._m, 16, nch)
        struct.pack_into("<Q", self._m, 8, self.epoch + 1)

    def write(self, samples):
        """Writer: append int16 frames: shape (n,) for a one-channel ring or (n, nch). The counter is updated last, after the data."""
        if not self.writer:
            raise PermissionError("read-only ring")
        nch = self.nch
        samples = np.asarray(samples)
        if samples.ndim == 1:
            samples = samples[:, None]
        if samples.shape[1] != nch:
            raise ValueError(f"the ring carries {nch} channel(s) per frame, got {samples.shape[1]}")
        n = len(samples)
        if n == 0:
            return
        if n > CAP:
            samples, n = samples[-CAP:], CAP
        w = self.written
        i = w % CAP
        k = min(n, CAP - i)
        f = self._frames(nch)
        f[i:i + k] = samples[:k]
        if k < n:
            f[:n - k] = samples[k:]
        struct.pack_into("<Q", self._m, 0, w + n)

    def read(self, ptr):
        """Reader: everything written since `ptr`, an int16 array of shape (n, nch). Returns (new_ptr, frames, lost). `lost` is True when the reader fell so far
        behind that the oldest frames were overwritten, or the writer reopened the device while we copied; it then continues from the newest data."""
        ep, nch = self.epoch, self.nch
        f = self._frames(nch)
        w = self.written
        if ptr > w:                                   # the ring was recreated: start again
            return w, f[:0].copy(), True
        lost = False
        if w - ptr > CAP - SAFE:
            ptr, lost = w - (CAP - SAFE), True
        n = w - ptr
        if n == 0:
            return ptr, f[:0].copy(), lost
        i = ptr % CAP
        k = min(n, CAP - i)
        out = np.concatenate([f[i:i + k], f[:n - k]]) if k < n else f[i:i + k].copy()
        if self.written - ptr > CAP - 256 or self.epoch != ep:   # the writer lapped us, or reopened the device, while we copied
            return self.written, f[:0].copy(), True
        return w, out, lost

    def close(self):
        try:
            self._raw = None
            self._m.close()
            self._f.close()
        except Exception:
            pass
