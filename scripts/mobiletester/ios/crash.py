"""Crash reports of apps: .ips files. A simulator's land on the Mac in ~/Library/Logs/DiagnosticReports; a real
device keeps its own, which sync_device copies into the device's state folder so the same code reads both.

An .ips file is one JSON header line (app, bundle id, time) followed by the JSON report (exception, the
crashed thread's frames, the loaded images).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path, PurePosixPath

from ..core import state
from . import devicectl


def reports_dir() -> Path:
    return Path(os.environ.get("MT_CRASH_DIR", Path.home() / "Library" / "Logs" / "DiagnosticReports"))


def read(path: Path) -> tuple[dict, dict]:
    header, _, body = path.read_text(encoding="utf-8", errors="replace").partition("\n")
    try:
        return json.loads(header), json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        return {}, {}


def find(executable: str, bundle_id: str, since: float, directory: Path | None = None) -> list[Path]:
    """Reports of this app written after `since` (epoch seconds), oldest first.

    The file name starts with the executable's name; the header's bundle id rules out a Mac process that
    happens to have the same name.
    """
    directory = directory or reports_dir()
    if not executable or not directory.is_dir():
        return []
    found = []
    for path in directory.glob(f"{executable}-*.ips"):
        if path.stat().st_mtime <= since:
            continue
        header, _ = read(path)
        if header.get("bundleID") in (bundle_id, None) and header.get("app_name", executable) == executable:
            found.append(path)
    return sorted(found, key=lambda p: p.stat().st_mtime)


def summary(path: Path, frames: int = 4) -> str:
    """'EXC_BAD_ACCESS (SIGSEGV), Segmentation fault: 11; in Habits: HabitList.delete(_:) < ...'."""
    header, body = read(path)
    exc = body.get("exception") or {}
    what = exc.get("type", "crash") + (f" ({exc['signal']})" if exc.get("signal") else "")
    indicator = (body.get("termination") or {}).get("indicator")
    if indicator and indicator not in what:
        what += f", {indicator}"
    threads = body.get("threads") or []
    thread = next((t for t in threads if t.get("triggered")), threads[body.get("faultingThread", 0)]
                  if len(threads) > body.get("faultingThread", 0) else {})
    images = body.get("usedImages") or []
    names = []
    for frame in (thread.get("frames") or [])[:frames]:
        image = images[frame["imageIndex"]].get("name", "?") if frame.get("imageIndex", -1) < len(images) else "?"
        names.append(frame.get("symbol") or f"{image}+{frame.get('imageOffset', 0)}")
    app = header.get("app_name") or body.get("procName", "app")
    return f"{what}; in {app}: {' < '.join(names)}" if names else f"{what} in {app}"


def crash_time(path: Path) -> float | None:
    """The crash's own time from the header ('2026-10-24 09:12:01.00 +0200'), as epoch seconds."""
    stamp = read(path)[0].get("timestamp", "")
    try:
        return datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S.%f %z").timestamp()
    except ValueError:
        return None


def device_reports_dir(udid: str) -> Path:
    return state.device_dir(udid) / "crashes"


def wanted_on_device(names: list[str], executable: str) -> list[str]:
    """The device's crash log paths that belong to this executable (the device keeps every app's, and the
    system's, in subfolders too)."""
    return [n for n in names if PurePosixPath(n).name.startswith(f"{executable}-") and n.endswith(".ips")]


def sync_device(udid: str, executable: str) -> Path:
    """Copy this app's crash reports that aren't here yet from the device; returns the local folder.

    Each copy gets the crash's time as its modification time, so `find(since=...)` means the same as on a
    simulator: crashes after that moment, not reports copied after it.
    """
    local = device_reports_dir(udid)
    local.mkdir(parents=True, exist_ok=True)
    for name in wanted_on_device(devicectl.crash_logs(udid), executable):
        target = local / PurePosixPath(name).name
        if target.is_file():
            continue
        devicectl.copy_crash_log(udid, name, target)
        if when := crash_time(target):
            os.utime(target, (when, when))
    return local
