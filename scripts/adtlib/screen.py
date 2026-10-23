"""Screen change detection from plain screenshots (no accessibility involved).

Used to wait until the UI has settled instead of sleeping a fixed time, and to notice taps that
did nothing visible (swallowed by an overlay, landed on dead space, stale coordinates).
"""

from __future__ import annotations

import io
import time

from PIL import Image, ImageChops

from .adb import Adb

# Small enough to compare quickly, large enough that a toggled checkbox still shows up.
_SIGNATURE_SIZE = (216, 480)
# Per-pixel grey-level change that counts as "different" (ignores compression noise).
_PIXEL_DELTA = 24
# Share of changed pixels below which two screens count as the same. A blinking text cursor
# stays below it; a checkbox toggle or a new screen is far above.
SAME_SCREEN = 0.0005


def signature(adb: Adb) -> Image.Image:
    png = adb.exec_out("screencap", "-p", timeout=20)
    image = Image.open(io.BytesIO(png)).convert("L")
    return image.resize(_SIGNATURE_SIZE, Image.BILINEAR)


def changed_ratio(a: Image.Image, b: Image.Image) -> float:
    diff = ImageChops.difference(a, b).point(lambda v: 255 if v > _PIXEL_DELTA else 0)
    return diff.histogram()[255] / (a.width * a.height)


def wait_stable(adb: Adb, timeout: float = 5.0, interval: float = 0.25) -> tuple[Image.Image, bool]:
    """Poll until two consecutive screenshots match. Returns the last signature and whether it settled.

    Spinners and video never settle; the caller gets the last frame after the timeout.
    """
    deadline = time.monotonic() + timeout
    previous = signature(adb)
    while time.monotonic() < deadline:
        time.sleep(interval)
        current = signature(adb)
        if changed_ratio(previous, current) < SAME_SCREEN:
            return current, True
        previous = current
    return previous, False
