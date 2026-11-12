"""Test-only hook shared by the helper processes (a copy of _test_dev_dir in cpl/legacy.py until `config` exists, split step P3)."""
import os
from pathlib import Path


def test_dev_dir():
    """Test-only hook: CP_TEST_DEVICES=<folder> makes the device list come from <folder>/mock_devices.json and logs what is opened
    (init.log, worker.log). Unset (always, in production) it does nothing."""
    d = os.environ.get("CP_TEST_DEVICES")
    return Path(d) if d else None


def test_input_dir():
    """Test-only hook: CP_TEST_INPUT=<folder> replaces the capture device of the Live input with a synthetic source driven by <folder>/feed.json
    (see tests/api/test_live_input.py). Unset (always, in production) it does nothing."""
    d = os.environ.get("CP_TEST_INPUT")
    return Path(d) if d else None
