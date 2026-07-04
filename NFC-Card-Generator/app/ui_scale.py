import os
import sys

from PyQt6.QtCore import QSize


def is_macos():
    return sys.platform == 'darwin'


def _read_scale():
    raw = os.environ.get('NFC_CARD_GENERATOR_UI_SCALE')
    if raw:
        try:
            value = float(raw)
            return max(0.65, min(1.25, value))
        except ValueError:
            pass
    # macOS Retina/HiDPI can make fixed PyQt UI dimensions feel oversized.
    # Keep exported artwork at full resolution, but use a smaller logical UI
    # scale on macOS. This can still be overridden for testing with:
    # NFC_CARD_GENERATOR_UI_SCALE=0.8 python3 main.py
    return 0.72 if is_macos() else 1.0


UI_SCALE = _read_scale()


def scale(value):
    return max(1, int(round(value * UI_SCALE)))


def scaled_size(width, height):
    return QSize(scale(width), scale(height))
