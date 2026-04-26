"""
Milestone 4 headless unit-test — Image compression.
Creates real JPEG fixtures and verifies compress_image() behaviour.
Run: cd tracker_app && python test_milestone4_headless.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from PIL import Image

from utils.compressor import compress_image
from utils.logger import get_logger
from config import TEMP_IMAGE_DIR, IMAGE_QUALITY, MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT

log = get_logger("milestone4_headless")


def _make_jpeg(filename: str, width: int, height: int, quality: int = 95) -> str:
    """Create a synthetic high-quality JPEG fixture and return its path."""
    os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)
    path  = os.path.join(TEMP_IMAGE_DIR, filename)
    # Random noise gives worst-case (largest) JPEG size — good stress test
    data  = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    Image.fromarray(data).save(path, format="JPEG", quality=quality)
    return path


# ---------------------------------------------------------------------------
# Test 1 — Already-small image: must not be upscaled, file should shrink
# ---------------------------------------------------------------------------
def test_small_image():
    log.info("── Test 1: small image (640×480) ──")
    path     = _make_jpeg("test_small.jpg", 640, 480)
    orig_kb  = os.path.getsize(path) / 1024

    result   = compress_image(path, keep_original=False)

    assert result == path,              "Should return same path (overwrite mode)"
    assert os.path.exists(result),     "Compressed file must exist"

    comp_kb  = os.path.getsize(result) / 1024
    reopened = Image.open(result)
    assert reopened.size == (640, 480), f"Small image must not be resized, got {reopened.size}"
    assert comp_kb <= orig_kb,         f"Compressed file ({comp_kb:.1f} KB) must be ≤ original ({orig_kb:.1f} KB)"

    log.info("PASS  %.1f KB → %.1f KB  dims=%s", orig_kb, comp_kb, reopened.size)
    os.remove(path)


# ---------------------------------------------------------------------------
# Test 2 — Oversized image: must be downscaled to fit within max bounds
# ---------------------------------------------------------------------------
def test_oversized_image():
    log.info("── Test 2: oversized image (2560×1440) ──")
    path    = _make_jpeg("test_large.jpg", 2560, 1440)
    orig_kb = os.path.getsize(path) / 1024

    result  = compress_image(path, keep_original=False)

    assert result is not None,         "compress_image must succeed"
    reopened = Image.open(result)
    w, h     = reopened.size
    assert w <= MAX_IMAGE_WIDTH,       f"Width {w} exceeds max {MAX_IMAGE_WIDTH}"
    assert h <= MAX_IMAGE_HEIGHT,      f"Height {h} exceeds max {MAX_IMAGE_HEIGHT}"

    comp_kb = os.path.getsize(result) / 1024
    log.info("PASS  %.1f KB → %.1f KB  original=2560x1440  resized=%dx%d",
             orig_kb, comp_kb, w, h)
    os.remove(result)


# ---------------------------------------------------------------------------
# Test 3 — keep_original=True: original untouched, _compressed sibling created
# ---------------------------------------------------------------------------
def test_keep_original():
    log.info("── Test 3: keep_original=True ──")
    path          = _make_jpeg("test_keep.jpg", 800, 600)
    orig_size     = os.path.getsize(path)
    expected_copy = path.replace(".jpg", "_compressed.jpg")

    result = compress_image(path, keep_original=True)

    assert result == expected_copy,        f"Expected sibling path, got {result}"
    assert os.path.exists(expected_copy),  "_compressed sibling must exist"
    assert os.path.getsize(path) == orig_size, "Original must be untouched"

    log.info("PASS  original intact (%d B)  sibling=%s", orig_size, os.path.basename(result))
    os.remove(path)
    os.remove(expected_copy)


# ---------------------------------------------------------------------------
# Test 4 — Missing file: must return None gracefully
# ---------------------------------------------------------------------------
def test_missing_file():
    log.info("── Test 4: missing file ──")
    result = compress_image("/tmp/does_not_exist_xyz.jpg")
    assert result is None, f"Expected None for missing file, got {result}"
    log.info("PASS  returned None as expected")


# ---------------------------------------------------------------------------
# Test 5 — RGBA input: must be converted to RGB without crashing
# ---------------------------------------------------------------------------
def test_rgba_input():
    log.info("── Test 5: RGBA input (PNG with alpha) ──")
    os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)
    path = os.path.join(TEMP_IMAGE_DIR, "test_rgba.png")
    data = np.random.randint(0, 255, (480, 640, 4), dtype=np.uint8)
    Image.fromarray(data, mode="RGBA").save(path, format="PNG")

    # Rename to .jpg so compress_image picks it up correctly
    jpg_path = path.replace(".png", ".jpg")
    os.rename(path, jpg_path)

    result = compress_image(jpg_path, keep_original=False)
    assert result is not None, "compress_image must handle RGBA input"
    reopened = Image.open(result)
    assert reopened.mode == "RGB", f"Output must be RGB, got {reopened.mode}"
    log.info("PASS  RGBA → RGB conversion succeeded  dims=%s", reopened.size)
    os.remove(result)


if __name__ == "__main__":
    log.info("=== Milestone 4 — Compressor unit-tests ===")
    test_small_image()
    test_oversized_image()
    test_keep_original()
    test_missing_file()
    test_rgba_input()
    log.info("=== All 5 tests passed ===")
