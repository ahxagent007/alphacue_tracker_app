# =============================================================================
# utils/compressor.py — JPEG compression + optional downscale via Pillow
#
# Usage:
#   from utils.compressor import compress_image
#   compressed_path = compress_image("/path/to/image.jpg")
#
# The function overwrites the original file by default.
# Pass keep_original=True to write a separate "_compressed" copy instead.
# =============================================================================

import os

from PIL import Image

from config import IMAGE_QUALITY, MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT
from utils.logger import get_logger

log = get_logger(__name__)


def _get_output_path(filepath: str, keep_original: bool) -> str:
    """Derive the output path from the input path.

    Args:
        filepath:      Absolute path to the source image.
        keep_original: If True, returns a sibling file with ``_compressed``
                       appended before the extension.  If False, returns
                       ``filepath`` unchanged (overwrite in-place).

    Returns:
        Absolute path where the compressed file should be written.
    """
    if not keep_original:
        return filepath

    root, ext = os.path.splitext(filepath)
    return f"{root}_compressed{ext}"


def _resize_if_needed(img: Image.Image) -> tuple[Image.Image, bool]:
    """Downscale ``img`` if either dimension exceeds the configured maximum.

    Uses ``Image.LANCZOS`` (high-quality downsampling).  Never upscales.

    Args:
        img: PIL Image to (possibly) resize.

    Returns:
        ``(image, was_resized)`` — the (possibly new) Image and a bool flag.
    """
    w, h = img.size
    if w <= MAX_IMAGE_WIDTH and h <= MAX_IMAGE_HEIGHT:
        return img, False

    img.thumbnail((MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT), Image.LANCZOS)
    return img, True


def compress_image(filepath: str, keep_original: bool = False) -> str | None:
    """Compress a JPEG image: resize if oversized, then re-encode at target quality.

    Steps
    -----
    1. Validate the file exists.
    2. Open with Pillow; convert to RGB (drops alpha — JPEG requirement).
    3. Downscale if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT.
    4. Re-save as JPEG at IMAGE_QUALITY, with ``optimize=True``.
    5. Log original vs compressed size (KB) and compression ratio.

    Args:
        filepath:      Absolute path to the JPEG file to compress.
        keep_original: When ``False`` (default) the file is overwritten.
                       When ``True`` a ``_compressed`` sibling is created
                       and the original is left untouched.

    Returns:
        Absolute path to the compressed file on success, ``None`` on failure.
    """
    if not os.path.exists(filepath):
        log.error("compress_image: file not found — %s", filepath)
        return None

    output_path = _get_output_path(filepath, keep_original)

    try:
        original_kb = os.path.getsize(filepath) / 1024
        log.debug("Compressing %s  (%.1f KB)…", os.path.basename(filepath), original_kb)

        img = Image.open(filepath)

        # Ensure RGB — JPEG encoder rejects palette / RGBA modes
        if img.mode != "RGB":
            img = img.convert("RGB")

        original_dims = img.size  # record before thumbnail mutates in-place

        img, was_resized = _resize_if_needed(img)

        if was_resized:
            log.debug(
                "Resized %s → %s (max %dx%d)",
                original_dims, img.size,
                MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT,
            )

        img.save(
            output_path,
            format   = "JPEG",
            quality  = IMAGE_QUALITY,
            optimize = True,   # extra Huffman-table pass; ~5-10 % smaller, negligible CPU cost
        )

        compressed_kb = os.path.getsize(output_path) / 1024
        ratio         = (1 - compressed_kb / original_kb) * 100 if original_kb > 0 else 0

        log.info(
            "Compressed  %-40s  %.1f KB → %.1f KB  (%.0f%% smaller)",
            os.path.basename(output_path),
            original_kb,
            compressed_kb,
            ratio,
        )

        return output_path

    except Exception:
        log.exception("Compression failed for %s", filepath)
        return None
