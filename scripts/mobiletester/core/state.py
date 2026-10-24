"""Per-device state on the host: last observation, background process pids."""

from __future__ import annotations

import json
import os
from pathlib import Path


def home() -> Path:
    """State lives in the project the agent is testing from, so evidence stays next to reports.

    Like git, look upwards for the project: the nearest folder holding `.adt/` or `.android-tester/`.
    That way commands run from inside a run folder still find the active session.
    """
    if explicit := os.environ.get("ADT_HOME"):
        return Path(explicit).resolve()
    cwd = Path.cwd().resolve()
    for folder in (cwd, *cwd.parents):
        if (folder / ".adt").is_dir() or (folder / ".android-tester").is_dir():
            return folder / ".adt"
    return cwd / ".adt"


def device_dir(serial: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in serial)
    path = home() / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
