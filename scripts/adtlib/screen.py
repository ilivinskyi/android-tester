"""Screen change detection from plain screenshots (no accessibility involved).

Used to wait until the UI has settled instead of sleeping a fixed time, and to notice taps that
did nothing visible (swallowed by an overlay, landed on dead space, stale coordinates).
"""

from __future__ import annotations

import io
import time

from PIL import Image, ImageChops

from .adb import Adb

# Half the resolution of a typical phone: a changed digit in a quantity stepper still covers
# dozens of pixels, while comparing stays fast.
SIGNATURE_SIZE = (540, 1200)
# Per-pixel grey-level change that counts as "different" (ignores compression noise).
_PIXEL_DELTA = 24
# Fewer changed pixels than this is noise, not a change.
_MIN_CHANGED = 12
# The status bar (clock, notification icons) changes on its own.
_STATUS_BAR = 0.05


def signature(adb: Adb) -> Image.Image:
    png = adb.exec_out("screencap", "-p", timeout=20)
    image = Image.open(io.BytesIO(png)).convert("L")
    return image.resize(SIGNATURE_SIZE, Image.BILINEAR)


def differs(a: Image.Image, b: Image.Image) -> bool:
    """Whether two signatures show a real change: ignores the status bar, noise and a blinking cursor."""
    top = round(a.height * _STATUS_BAR)
    a, b = a.crop((0, top, a.width, a.height)), b.crop((0, top, b.width, b.height))
    mask = ImageChops.difference(a, b).point(lambda v: 255 if v > _PIXEL_DELTA else 0)
    if mask.histogram()[255] < _MIN_CHANGED:
        return False
    left, upper, right, lower = mask.getbbox()
    width, height = right - left, lower - upper
    # A text cursor is a thin vertical bar; anything wider is content.
    return not (width <= 3 and height >= 3 * width)


def wait_stable(adb: Adb, timeout: float = 5.0, interval: float = 0.25) -> tuple[Image.Image, bool]:
    """Poll until two consecutive screenshots match. Returns the last signature and whether it settled.

    Spinners and video never settle; the caller gets the last frame after the timeout.
    """
    deadline = time.monotonic() + timeout
    previous = signature(adb)
    while time.monotonic() < deadline:
        time.sleep(interval)
        current = signature(adb)
        if not differs(previous, current):
            return current, True
        previous = current
    return previous, False
