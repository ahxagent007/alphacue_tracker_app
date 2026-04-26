"""
Milestone 3 headless unit-test.
Mocks cv2.VideoCapture so the module can be validated without a physical webcam.
Run: cd tracker_app && python test_milestone3_headless.py
"""

import sys, os, types
sys.path.insert(0, os.path.dirname(__file__))

# ── mock cv2 before the real import ──────────────────────────────────────────
import numpy as np

fake_cv2 = types.ModuleType("cv2")

# Constants the module uses
fake_cv2.CAP_DSHOW      = 700
fake_cv2.COLOR_BGR2RGB  = 4

def _fake_cvt_color(frame, _code):
    """Simulate BGR→RGB by just returning the array unchanged (colours don't matter in tests)."""
    return frame

fake_cv2.cvtColor = _fake_cvt_color

class FakeCapture:
    """Mimics cv2.VideoCapture with a solid-colour 1280×720 BGR frame."""
    def __init__(self, *_args, **_kwargs):
        self._open   = True
        self._reads  = 0

    def isOpened(self):
        return self._open

    def read(self):
        self._reads += 1
        # Return a solid blue (BGR) frame
        frame = np.full((720, 1280, 3), fill_value=(200, 120, 30), dtype=np.uint8)
        return True, frame

    def release(self):
        self._open = False

fake_cv2.VideoCapture = FakeCapture
sys.modules["cv2"] = fake_cv2

# ── now import the module under test ─────────────────────────────────────────
from capture.webcam import take_webcam_photo
from utils.logger import get_logger
from PIL import Image

log = get_logger("milestone3_headless")

if __name__ == "__main__":
    log.info("=== Milestone 3 — Headless unit-test ===")

    path = take_webcam_photo()

    assert path is not None,           "take_webcam_photo() must return a path"
    assert os.path.exists(path),       f"File must exist on disk: {path}"
    assert path.endswith(".jpg"),      "Extension must be .jpg"
    assert "webcam_" in path,          "Filename must contain 'webcam_'"

    size_kb = os.path.getsize(path) / 1024
    assert size_kb > 0,               "File must not be empty"

    # Verify it's a valid JPEG PIL can reopen
    reopened = Image.open(path)
    assert reopened.format == "JPEG", f"Expected JPEG, got {reopened.format}"
    assert reopened.mode   == "RGB",  f"Expected RGB, got {reopened.mode}"
    w, h = reopened.size
    assert w == 1280 and h == 720,    f"Expected 1280x720, got {w}x{h}"

    log.info("PASS  path=%s", path)
    log.info("      size=%.1f KB  dimensions=%s  format=%s",
             size_kb, reopened.size, reopened.format)

    # Clean up
    os.remove(path)
    log.info("Temp file cleaned up.")
    log.info("=== All assertions passed ===")
