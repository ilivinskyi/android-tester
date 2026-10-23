"""Test sessions: the standard run folder and the action log every command writes to."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import state

RUN_SUBDIRS = ("screenshots", "videos", "logs", "bugs")


def _active_file(serial: str) -> Path:
    return state.device_dir(serial) / "session.json"


def active(serial: str) -> dict | None:
    return state.read_json(_active_file(serial))


def run_dir(serial: str) -> Path | None:
    data = active(serial)
    return Path(data["run_dir"]) if data else None


def start(serial: str, directory: Path, meta: dict) -> Path:
    """Create the run folder and mark it active for this device. Existing files are kept."""
    directory = directory.resolve()
    for sub in RUN_SUBDIRS:
        (directory / sub).mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    session_file = directory / "session.json"
    session = state.read_json(session_file) or {}
    session.update({k: v for k, v in meta.items() if v is not None})
    session.setdefault("started", now)
    state.write_json(session_file, session)
    findings = directory / "findings.json"
    if not findings.exists():
        state.write_json(findings, {"findings": []})
    state.write_json(_active_file(serial), {"run_dir": str(directory), "started": now})
    return directory


def end(serial: str) -> Path | None:
    data = active(serial)
    if not data:
        return None
    directory = Path(data["run_dir"])
    session_file = directory / "session.json"
    session = state.read_json(session_file) or {}
    session["ended"] = datetime.now().astimezone().isoformat(timespec="seconds")
    state.write_json(session_file, session)
    _active_file(serial).unlink(missing_ok=True)
    return directory


def log_action(serial: str, entry: dict, started: datetime | None = None) -> None:
    """Append one action. `t` is when it started (wall time, ms) so clips can be cut from the session video."""
    directory = run_dir(serial)
    path = (directory / "logs" if directory else state.device_dir(serial)) / "actions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    record = {"t": (started or now).isoformat(timespec="milliseconds"), **entry}
    if started:
        record["duration_s"] = round((now - started).total_seconds(), 2)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
