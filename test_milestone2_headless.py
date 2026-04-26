"""
Milestone 2 headless unit-test.
Mocks pyautogui so the module can be validated without a physical display.
Run: cd tracker_app && python test_milestone2_headless.py
"""

import sys, os, types
sys.path.insert(0, os.path.dirname(__file__))

# ── mock pyautogui before the real import ────────────────────────────────────
from PIL import Image
import io

fake_pyautogui = types.ModuleType("pyautogui")

def _fake_screenshot():
    """Return a solid-colour 1280×720 PIL image (simulates a real screenshot)."""
    img = Image.new("RGB", (1280, 720), color=(30, 120, 200))
    return img

fake_pyautogui.screenshot = _fake_screenshot
sys.modules["pyautogui"] = fake_pyautogui

# ── now import the module under test ─────────────────────────────────────────
from capture.screenshot import take_screenshot
from utils.logger import get_logger

log = get_logger("milestone2_headless")

if __name__ == "__main__":
    log.info("=== Milestone 2 — Headless unit-test ===")

    path = take_screenshot()

    assert path is not None,              "take_screenshot() must return a path"
    assert os.path.exists(path),          f"File must exist on disk: {path}"
    assert path.endswith(".jpg"),         "Extension must be .jpg"
    assert "screenshot_" in path,        "Filename must contain 'screenshot_'"

    size_kb = os.path.getsize(path) / 1024
    assert size_kb > 0,                  "File must not be empty"

    # Verify it's a valid JPEG that PIL can reopen
    reopened = Image.open(path)
    assert reopened.format == "JPEG",    f"Expected JPEG, got {reopened.format}"
    assert reopened.mode  == "RGB",      f"Expected RGB, got {reopened.mode}"

    log.info("PASS  path=%s", path)
    log.info("      size=%.1f KB  dimensions=%s  format=%s",
             size_kb, reopened.size, reopened.format)

    # Clean up temp file
    os.remove(path)
    log.info("Temp file cleaned up.")
    log.info("=== All assertions passed ===")
