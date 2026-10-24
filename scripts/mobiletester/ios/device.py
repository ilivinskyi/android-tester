"""One simulator as idt sees it: facts for reports, observations of the screen, the app under test.

Which app to observe: the given one, else the session's app, else the app idt last launched; when it is not
in the foreground, SpringBoard (home screen, system alerts). XCUITest only sees an app it is asked about by
bundle id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..core import annotate, session, state
from ..core.fingerprint import screen_fingerprint
from ..core.ui import Bounds, Element, Snapshot
from . import hierarchy, simctl
from .hierarchy import Key, Keyboard
from .runner import APP_STATES, FOREGROUND, SPRINGBOARD, Runner

NAVIGATION = "edge swipe or the app's back button"


@dataclass
class Device:
    sim: simctl.Simulator
    runner: Runner

    @property
    def udid(self) -> str:
        return self.sim.udid

    def facts(self, refresh: bool = False) -> dict:
        """Screen size in points and scale, cached per simulator (they don't change while it runs)."""
        path = state.device_dir(self.udid) / "facts.json"
        cached = None if refresh else state.read_json(path)
        if cached is None:
            info = self.runner.info()
            cached = {"screen": info["screen"], "scale": info["scale"], "os": info["os_version"],
                      "language": info.get("language", "")}
            state.write_json(path, cached)
        return cached

    def last_app(self) -> str | None:
        """The app idt last launched here, so commands outside a session know which app is meant."""
        return (state.read_json(state.device_dir(self.udid) / "app.json") or {}).get("bundle_id")

    def remember_app(self, bundle_id: str) -> None:
        state.write_json(state.device_dir(self.udid) / "app.json", {"bundle_id": bundle_id})

    def target(self, bundle_id: str | None = None) -> tuple[str, int | None]:
        """(bundle id to observe and act in, the app's state or None for SpringBoard)."""
        wanted = bundle_id or session.package(self.udid) or self.last_app()
        if wanted:
            app_state = self.runner.app(wanted, "state")
            if app_state == FOREGROUND:
                return wanted, app_state
            return SPRINGBOARD, app_state
        return SPRINGBOARD, None


def device_props(dev: Device) -> dict:
    """The device block of session.json, in the report's neutral keys."""
    facts = dev.facts(refresh=True)
    languages = simctl.languages(dev.udid)
    w, h = facts["screen"]
    return {
        "platform": "iOS",
        "udid": dev.udid,
        "model": dev.sim.name,
        "os": f"iOS {facts['os']}",
        "kind": "simulator",
        "screen": f"{round(w)}x{round(h)} pt @{round(facts['scale'])}x",
        "navigation": NAVIGATION,
        "keyboard": f"iOS keyboard ({languages[0] if languages else facts.get('language', '?')})",
        "locale": simctl.locale(dev.udid),
        "languages": languages,
    }


@dataclass
class Observation:
    snapshot: Snapshot
    bundle_id: str
    app_state: int | None
    title: str
    fingerprint: str
    keyboard: Keyboard | None
    scale: float
    preview: Path | None
    screenshot: Path | None
    timestamp: str

    def to_dict(self) -> dict:
        s = self.snapshot
        kb = self.keyboard
        return {
            "timestamp": self.timestamp,
            "package": self.bundle_id,
            "app_state": self.app_state,
            "title": self.title,
            "fingerprint": self.fingerprint,
            "screen": [s.screen.right, s.screen.bottom],
            "preview_scale": self.scale,
            "preview": str(self.preview) if self.preview else None,
            "screenshot": str(self.screenshot) if self.screenshot else None,
            "keyboard": {"area": _box(kb.area), "keys": [{"label": k.label, "identifier": k.identifier,
                                                           "bounds": _box(k.bounds)} for k in kb.keys]}
            if kb else None,
            "elements": [e.to_dict() for e in s.elements],
        }


def _box(b: Bounds) -> list[int]:
    return [b.left, b.top, b.right, b.bottom]


def read_screen(dev: Device, bundle_id: str | None = None) -> tuple[Snapshot, Keyboard | None, str, int | None, dict]:
    target, app_state = dev.target(bundle_id)
    raw = dev.runner.tree(target)
    snap, keyboard = hierarchy.parse(raw, target)
    return snap, keyboard, target, app_state, raw


def observe(dev: Device, bundle_id: str | None = None, save_dir: Path | None = None, name: str | None = None,
            with_image: bool = True, marks: bool = True) -> Observation:
    ddir = state.device_dir(dev.udid)
    snap, keyboard, target, app_state, raw = read_screen(dev, bundle_id)
    title = hierarchy.screen_title(snap)
    fp = screen_fingerprint(target, title, snap.elements)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    tree_json = json.dumps(raw, ensure_ascii=False)
    (ddir / "latest_tree.json").write_text(tree_json, encoding="utf-8")
    preview = shot = None
    scale = 1.0
    if with_image:
        png = dev.runner.screenshot()
        shot = ddir / "latest.png"
        shot.write_bytes(png)
        preview = ddir / "latest_preview.jpg"
        scale = annotate.make_preview(png, snap.elements, preview, marks=marks, unit=dev.facts()["scale"])
    obs = Observation(snap, target, app_state, title, fp, keyboard, scale, preview, shot, stamp)
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
        stem = name or stamp
        (save_dir / f"{stem}.json").write_text(tree_json, encoding="utf-8")
        for attr, suffix in (("screenshot", ".png"), ("preview", "_preview.jpg")):
            source = getattr(obs, attr)
            if source:
                copy = save_dir / f"{stem}{suffix}"
                copy.write_bytes(source.read_bytes())
                setattr(obs, attr, copy)
    state.write_json(ddir / "latest.json", obs.to_dict())
    return obs


def last_observation(udid: str) -> dict | None:
    return state.read_json(state.device_dir(udid) / "latest.json")


def last_snapshot(udid: str) -> tuple[Snapshot, Keyboard | None, dict]:
    data = last_observation(udid)
    if not data:
        raise LookupError("no observation yet: run `idt observe` first")
    w, h = data["screen"]
    snap = Snapshot(Bounds(0, 0, w, h), 0, data["package"], [Element.from_dict(e) for e in data["elements"]])
    kb = data.get("keyboard")
    keyboard = Keyboard(Bounds(*kb["area"]), [Key(k["label"], k["identifier"], Bounds(*k["bounds"]))
                                              for k in kb["keys"]]) if kb else None
    return snap, keyboard, data


def state_name(app_state: int | None) -> str:
    return APP_STATES.get(app_state, "?") if app_state is not None else "-"
