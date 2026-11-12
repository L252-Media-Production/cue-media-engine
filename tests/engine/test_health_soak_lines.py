"""2.8.0 follow-up 3: the two soak lines of the report (Process memory, Open files): format, 'not available', and no effect on the checks."""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from cpl import health as H      # noqa: E402

STATUS = "Name:\tpython\nVmPeak:\t  900000 kB\nVmRSS:\t  421888 kB\nThreads:\t12\n"


class SoakLines(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="soak-"))

    def test_process_memory_from_vmrss_on_linux(self):
        f = self.d / "status"
        f.write_text(STATUS)
        self.assertEqual(H.process_memory_text(str(f), "linux"), "Process memory: 412 MB")

    def test_process_memory_from_getrusage_on_macos_same_wording(self):
        self.assertEqual(H.process_memory_text(platform="darwin", rusage=300 * 1048576), "Process memory: 300 MB")

    def test_process_memory_not_available_without_proc_or_vmrss_or_elsewhere(self):
        self.assertEqual(H.process_memory_text(str(self.d / "missing"), "linux"), "Process memory: not available")
        f = self.d / "status"
        f.write_text("Name:\tpython\n")
        self.assertEqual(H.process_memory_text(str(f), "linux"), "Process memory: not available")
        self.assertEqual(H.process_memory_text(platform="win32"), "Process memory: not available")

    def test_open_files_counts_fd_entries_less_the_listing_itself(self):
        fd = self.d / "fd"
        fd.mkdir()
        for i in range(5):
            (fd / str(i)).write_text("")
        self.assertEqual(H.open_files_text(str(fd), "linux", own_fd=0), "Open files: 5")
        self.assertEqual(H.open_files_text(str(fd), "linux"), "Open files: 4")
        self.assertEqual(H.open_files_text(str(self.d / "empty-missing"), "linux"), "Open files: not available")

    def test_open_files_not_available_elsewhere(self):
        for plat in ("darwin", "win32"):
            self.assertEqual(H.open_files_text(platform=plat), "Open files: not available")

    def test_the_lines_do_not_touch_the_checks(self):
        inp = {"starting": False, "live": {"name": "x", "present": True, "open": True}, "preview": {"configured": False}, "engine": {},
               "companion": {"polled": True, "silent_s": 0, "host_found": True}, "disk": {"free": 200 * 1024 ** 3, "total": 500 * 1024 ** 3},
               "cache": {"measured": True}, "uptime_s": 5}
        before = H.compact(H.evaluate(inp))
        H.process_memory_text(), H.open_files_text()
        self.assertEqual(H.compact(H.evaluate(inp)), before)
        self.assertEqual([c["id"] for c in before["checks"]], list(H.ORDER))
        self.assertEqual(len(H.ORDER), 7)

    def test_the_real_values_have_the_expected_shape(self):
        self.assertRegex(H.process_memory_text(), r"^Process memory: (\d+ MB|not available)$")
        self.assertRegex(H.open_files_text(), r"^Open files: (\d+|not available)$")
