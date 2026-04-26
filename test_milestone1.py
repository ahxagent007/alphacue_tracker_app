"""
Quick smoke-test for Milestone 1.
Run from inside the tracker_app directory:
    cd tracker_app && python test_milestone1.py
"""

import sys
import os

# Make sure imports resolve when run directly
sys.path.insert(0, os.path.dirname(__file__))

from utils.logger import get_logger
import config

log = get_logger("milestone1_test")

def test_config():
    log.info("=== Milestone 1 — Config & Logger smoke-test ===")
    log.debug("BASE_DIR          : %s", config.BASE_DIR)
    log.debug("TEMP_IMAGE_DIR    : %s", config.TEMP_IMAGE_DIR)
    log.debug("LOG_FILE          : %s", config.LOG_FILE)
    log.debug("CAPTURE_INTERVAL  : %s seconds", config.CAPTURE_INTERVAL_SECONDS)
    log.debug("IMAGE_QUALITY     : %s", config.IMAGE_QUALITY)
    log.debug("MAX RESOLUTION    : %sx%s", config.MAX_IMAGE_WIDTH, config.MAX_IMAGE_HEIGHT)
    log.debug("DRIVE_FOLDER_ID   : %s", config.GOOGLE_DRIVE_FOLDER_ID)
    log.info("Config loaded successfully.")

def test_dirs():
    for label, path in [
        ("temp_images", config.TEMP_IMAGE_DIR),
        ("logs",        config.LOG_DIR),
    ]:
        os.makedirs(path, exist_ok=True)
        exists = os.path.isdir(path)
        log.info("Directory %-15s → %s  [%s]", label, path, "OK" if exists else "MISSING")

if __name__ == "__main__":
    test_config()
    test_dirs()
    log.info("=== All Milestone 1 checks passed ===")
