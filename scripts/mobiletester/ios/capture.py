"""Background evidence on the simulator: screen recording and the app's unified log.

`simctl io recordVideo` writes one file for the whole session and finishes it on SIGINT. It prints
"Recording started" once frames flow; that moment is the video's wall-clock start, so clips can be cut by
action-log times (core/clip.py).
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from pathlib import Path

from ..core import state
from ..core.clip import build_timeline, duration
from ..core.proc import detached_kwargs, is_alive, terminate
from .simctl import xcrun


class CaptureError(Exception):
    pass


def _file(udid: str, name: str) -> Path:
    return state.device_dir(udid) / name


def record_start(udid: str, out: Path, wait: float = 10.0) -> int:
    rec_file = _file(udid, "recording.json")
    if (running := state.read_json(rec_file)) and is_alive(running["pid"]):
        raise CaptureError(f"a recording is already running (pid {running['pid']}): `idt record stop` first")
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    log = _file(udid, "recording.log")
    with log.open("wb") as fh:
        proc = subprocess.Popen([xcrun(), "simctl", "io", udid, "recordVideo", "--codec=h264", "--force", str(out)],
                                stdout=fh, stderr=subprocess.STDOUT, **detached_kwargs())
    wall_start = None
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline and proc.poll() is None:
        if "Recording started" in log.read_text(errors="replace"):
            wall_start = time.time()
            break
        time.sleep(0.05)
    if proc.poll() is not None:
        raise CaptureError(f"recordVideo exited: {log.read_text(errors='replace').strip()}")
    state.write_json(rec_file, {"pid": proc.pid, "out": str(out), "wall_start": wall_start or time.time()})
    return proc.pid


def record_stop(udid: str, discard: bool = False) -> Path | None:
    rec_file = _file(udid, "recording.json")
    running = state.read_json(rec_file)
    if not running:
        return None
    pid, out = running["pid"], Path(running["out"])
    if is_alive(pid):
        # SIGINT makes recordVideo write the file's index; without it the video can't be played.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGINT)
        deadline = time.monotonic() + 20
        while is_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.2)
        if is_alive(pid):
            terminate(pid)
    rec_file.unlink(missing_ok=True)
    if discard:
        out.unlink(missing_ok=True)
        return None
    if out.is_file():
        timeline = build_timeline([(running["wall_start"], duration(out))])
        state.write_json(out.with_suffix(".timeline.json"), {"chunks": timeline})
    return out


def log_start(udid: str, process: str, out: Path) -> int:
    """Stream the app's unified log (its own messages, errors and faults) into `out`."""
    log_file = _file(udid, "applog.json")
    if (running := state.read_json(log_file)) and is_alive(running["pid"]):
        terminate(running["pid"])
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("ab") as fh:
        proc = subprocess.Popen(
            [xcrun(), "simctl", "spawn", udid, "log", "stream", "--style", "compact", "--level", "info",
             "--predicate", f'process == "{process}"'],
            stdout=fh, stderr=subprocess.STDOUT, **detached_kwargs())
    state.write_json(log_file, {"pid": proc.pid, "out": str(out), "process": process})
    return proc.pid


def log_stop(udid: str) -> Path | None:
    log_file = _file(udid, "applog.json")
    running = state.read_json(log_file)
    if not running:
        return None
    if is_alive(running["pid"]):
        terminate(running["pid"])
    log_file.unlink(missing_ok=True)
    return Path(running["out"])
