"""Background evidence capture: logcat streaming and chunked screen recording."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import state
from .adb import Adb, AdbError, detached_kwargs, is_alive, terminate

# --- logcat ----------------------------------------------------------------------------------


def logcat_start(adb: Adb, out_file: Path, clear: bool = True) -> int:
    proc_file = state.device_dir(adb.serial) / "logcat.json"
    if (running := state.read_json(proc_file)) and is_alive(running["pid"]):
        raise AdbError(f"logcat already running (pid {running['pid']}) -> {running['file']}; stop it first")
    if clear:
        adb.run("logcat", "-c", check=False)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("wb") as fh:
        proc = adb.popen("logcat", "-v", "threadtime", stdout=fh)
    state.write_json(proc_file, {"pid": proc.pid, "file": str(out_file.resolve())})
    return proc.pid


def logcat_stop(adb: Adb) -> Path | None:
    proc_file = state.device_dir(adb.serial) / "logcat.json"
    running = state.read_json(proc_file)
    if not running:
        return None
    terminate(running["pid"])
    proc_file.unlink(missing_ok=True)
    return Path(running["file"])


_CRASH_MARKERS = re.compile(r"FATAL EXCEPTION|ANR in |Process: .* PID: |\bSIGSEGV\b|Fatal signal")


def new_lines(seen: int, lines: list[str]) -> tuple[list[str], int]:
    """Lines added to a log since `seen` lines were read. A shorter log means it was cleared."""
    if len(lines) < seen:
        seen = 0
    return lines[seen:], len(lines)


def crash_summary(lines: list[str]) -> str:
    """'com.example.app: java.lang.IllegalStateException: ...' from new crash-buffer lines."""
    process = next((m.group(1) for line in lines if (m := re.search(r"Process: ([\w.:]+)", line))), "")
    cause = next((line.split(": ", 1)[-1].strip() for line in lines
                  if re.search(r"\b\w+(\.\w+)+(Exception|Error)\b", line)), "")
    signal = next((line.split("Fatal signal", 1)[-1].strip() for line in lines if "Fatal signal" in line), "")
    return ": ".join(p for p in (process, cause or (f"Fatal signal {signal}" if signal else "")) if p) or lines[0]


def new_crashes(adb: Adb) -> list[str]:
    """Crash-buffer lines written since the last call (crash watch after every action)."""
    seen_file = state.device_dir(adb.serial) / "crash_seen.json"
    baseline = state.read_json(seen_file)
    text = adb.run("logcat", "-b", "crash", "-d", check=False, timeout=15).decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    if baseline is None:
        # First check on this device: older crashes in the buffer aren't news.
        state.write_json(seen_file, {"lines": len(lines)})
        return []
    fresh, total = new_lines(baseline.get("lines", 0), lines)
    state.write_json(seen_file, {"lines": total})
    return [line for line in fresh if not line.startswith("--------- beginning of")]


def crashes(adb: Adb, package: str | None = None) -> str:
    """Crash buffer plus ANR / fatal lines from the main buffer since the last `logcat -c`."""
    crash_buf = adb.run("logcat", "-d", "-b", "crash", "-v", "threadtime", check=False).decode(errors="replace")
    main = adb.run("logcat", "-d", "-v", "threadtime", check=False).decode(errors="replace")
    anr = [line for line in main.splitlines() if _CRASH_MARKERS.search(line)]
    text = crash_buf.strip()
    if anr:
        text = (text + "\n" if text else "") + "\n".join(anr)
    if package and text:
        # Keep blocks that mention the package; crash blocks are separated by `--------- beginning of` lines.
        relevant = [b for b in re.split(r"(?m)^-{9} beginning of .*$", text) if package in b]
        text = "\n".join(b.strip() for b in relevant)
    return text.strip()


# --- screen recording ------------------------------------------------------------------------

_REMOTE_REC_DIR = "/sdcard/adt_rec"
_CHUNK_SECONDS = 180  # screenrecord's hard limit


def record_start(adb: Adb, out_file: Path) -> int:
    rec_file = state.device_dir(adb.serial) / "record.json"
    if (running := state.read_json(rec_file)) and is_alive(running["pid"]):
        raise AdbError(f"recording already running (pid {running['pid']}); stop it first")
    stop_flag = state.device_dir(adb.serial) / "record.stop"
    stop_flag.unlink(missing_ok=True)
    _chunk_log(adb).unlink(missing_ok=True)
    adb.shell("rm", "-rf", _REMOTE_REC_DIR, check=False)
    adb.shell("mkdir", "-p", _REMOTE_REC_DIR)
    # The worker is this same CLI in a hidden mode, detached so it survives the current command.
    entry = Path(__file__).resolve().parent.parent / "adt.py"
    cmd = [sys.executable, str(entry), "-s", adb.serial, "_record-worker", str(stop_flag)]
    log = (state.device_dir(adb.serial) / "record_worker.log").open("wb")
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, **detached_kwargs())
    state.write_json(rec_file, {
        "pid": proc.pid, "file": str(out_file.resolve()), "stop_flag": str(stop_flag),
        "started": datetime.now().isoformat(timespec="seconds"),
    })
    return proc.pid


def _chunk_log(adb: Adb) -> Path:
    return state.device_dir(adb.serial) / "record_chunks.jsonl"


def record_worker(adb: Adb, stop_flag: Path) -> None:
    chunk = 0
    while not stop_flag.exists():
        remote = f"{_REMOTE_REC_DIR}/chunk_{chunk:03d}.mp4"
        # Wall time of each chunk start: maps action-log times to video positions despite restart gaps.
        with _chunk_log(adb).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"name": f"chunk_{chunk:03d}.mp4", "wall": time.time()}) + "\n")
        # Blocks until the time limit or until record_stop sends SIGINT, which finalizes the mp4.
        adb.shell("screenrecord", "--time-limit", str(_CHUNK_SECONDS), remote,
                  check=False, timeout=_CHUNK_SECONDS + 30)
        chunk += 1


def record_stop(adb: Adb, discard: bool = False) -> Path | None:
    rec_file = state.device_dir(adb.serial) / "record.json"
    running = state.read_json(rec_file)
    if not running:
        return None
    Path(running["stop_flag"]).touch()
    adb.shell("pkill", "-INT", "screenrecord", check=False)
    for _ in range(40):
        if not is_alive(running["pid"]):
            break
        time.sleep(0.25)
    else:
        terminate(running["pid"])
    time.sleep(0.5)  # let the device flush the last mp4 trailer
    rec_file.unlink(missing_ok=True)

    if discard:
        adb.shell("rm", "-rf", _REMOTE_REC_DIR, check=False)
        return None

    out_file = Path(running["file"])
    out_file.parent.mkdir(parents=True, exist_ok=True)
    listing = adb.shell("ls", _REMOTE_REC_DIR, check=False).split()
    chunks = sorted(name for name in listing if name.endswith(".mp4"))
    if not chunks:
        raise AdbError("recording produced no video (secure content or screenrecord unsupported)")
    local_chunks = []
    for name in chunks:
        local = out_file.with_name(f"{out_file.stem}.{name}")
        adb.run("pull", f"{_REMOTE_REC_DIR}/{name}", str(local), timeout=120)
        local_chunks.append(local)
    adb.shell("rm", "-rf", _REMOTE_REC_DIR, check=False)
    timeline = _write_timeline(adb, local_chunks, out_file)
    return _join_chunks(local_chunks, out_file, [c["span"] for c in timeline])


def _duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    proc = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                          capture_output=True, text=True)
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def build_timeline(chunks: list[tuple[float | None, float | None]]) -> list[dict]:
    """(wall start, measured duration) per chunk -> timeline entries.

    screenrecord only writes frames when the screen changes, so a chunk's measured duration ends at its
    last frame: a still screen at the end of a chunk would drop out of the joined video and make it run
    ahead of the clock. Each chunk therefore spans until the next one started (its wall-clock length);
    only the last chunk uses its measured duration.
    """
    timeline, video_pos = [], 0.0
    for i, (wall_start, duration) in enumerate(chunks):
        next_start = chunks[i + 1][0] if i + 1 < len(chunks) else None
        span = next_start - wall_start if wall_start is not None and next_start is not None else duration
        timeline.append({"wall_start": wall_start, "video_start": round(video_pos, 3), "duration": duration,
                         "span": round(span, 3) if span is not None else None})
        video_pos += span or 0.0
    return timeline


def _write_timeline(adb: Adb, chunks: list[Path], out_file: Path) -> list[dict]:
    starts = {}
    log = _chunk_log(adb)
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            starts[entry["name"]] = entry["wall"]
    # "<stem>.chunk_000.mp4" -> "chunk_000.mp4"
    timeline = build_timeline([(starts.get(c.name.split(".", 1)[1]), _duration(c)) for c in chunks])
    state.write_json(out_file.with_suffix(".timeline.json"), {"chunks": timeline})
    return timeline


def video_position(timeline: dict, wall: float) -> float | None:
    """Seconds into the joined video for a wall-clock time, or None if it falls outside the recording."""
    for chunk in timeline["chunks"]:
        start = chunk["wall_start"]
        length = chunk.get("span") or chunk["duration"]  # older timelines have no span
        if start is None or length is None:
            return None
        if start <= wall <= start + length:
            return chunk["video_start"] + (wall - start)
    return None


def cut_clip(video: Path, wall_from: float, wall_to: float, out: Path, pad: float = 3.0) -> tuple[float, float]:
    """Cut [wall_from - pad, wall_to + pad] from a recording made by record_start, re-encoded at 540p."""
    timeline = state.read_json(video.with_suffix(".timeline.json"))
    if not timeline:
        raise AdbError(f"no timeline next to {video}; record it with `adt record`")
    starts = [video_position(timeline, wall_from - pad), video_position(timeline, wall_from)]
    ends = [video_position(timeline, wall_to + pad), video_position(timeline, wall_to)]
    start = next((s for s in starts if s is not None), None)
    end = next((e for e in ends if e is not None), None)
    if start is None or end is None or end <= start:
        raise AdbError("the requested time range is not inside the recording")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AdbError("ffmpeg is required to cut clips")
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
                           "-i", str(video), "-vf", "scale=540:-2", "-c:v", "libx264", "-crf", "26",
                           "-preset", "veryfast", "-an", str(out)], capture_output=True)
    if proc.returncode != 0:
        raise AdbError(f"ffmpeg failed: {proc.stderr.decode(errors='replace')}")
    return start, end


def concat_listing(chunks: list[Path], spans: list[float | None]) -> str:
    """ffmpeg concat list; `duration` makes each chunk last its wall-clock span (the last frame holds)."""
    lines = []
    for chunk, span in zip(chunks, spans, strict=True):
        lines.append(f"file '{chunk.resolve().as_posix()}'")
        if span:
            lines.append(f"duration {span:.3f}")
    return "\n".join(lines) + "\n"


def _join_chunks(chunks: list[Path], out_file: Path, spans: list[float | None]) -> Path:
    if len(chunks) == 1:
        chunks[0].replace(out_file)
        return out_file
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        # Keep the parts; the report can still link them in order.
        return chunks[0]
    listing = out_file.with_suffix(".txt")
    listing.write_text(concat_listing(chunks, spans), encoding="utf-8")
    proc = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
         str(out_file)],
        capture_output=True,
    )
    listing.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise AdbError(f"ffmpeg concat failed: {proc.stderr.decode(errors='replace')}")
    for c in chunks:
        c.unlink(missing_ok=True)
    return out_file
