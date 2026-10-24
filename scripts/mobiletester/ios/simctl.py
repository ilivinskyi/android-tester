"""Simulators through `xcrun simctl`: discovery, apps, locale, screenshots."""

from __future__ import annotations

import json
import plistlib
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class SimctlError(Exception):
    pass


class DeviceError(Exception):
    """No simulator, or none that can be chosen without asking."""


def xcrun() -> str:
    path = shutil.which("xcrun")
    if not path:
        raise SimctlError("xcrun not found: install Xcode and its command line tools (xcode-select --install)")
    return path


def run(*args: str, timeout: float = 120, input_: bytes | None = None) -> bytes:
    proc = subprocess.run([xcrun(), "simctl", *args], capture_output=True, timeout=timeout, input=input_)
    if proc.returncode != 0:
        message = proc.stderr.decode(errors="replace").strip() or proc.stdout.decode(errors="replace").strip()
        raise SimctlError(f"simctl {' '.join(args[:2])}: {message}")
    return proc.stdout


@dataclass
class Simulator:
    udid: str
    name: str
    state: str
    runtime: str  # "iOS 27.0"

    @property
    def booted(self) -> bool:
        return self.state == "Booted"

    @property
    def os_version(self) -> str:
        return self.runtime.split(" ", 1)[-1]


def runtime_name(identifier: str) -> str:
    """'com.apple.CoreSimulator.SimRuntime.iOS-27-0' -> 'iOS 27.0'."""
    match = re.search(r"SimRuntime\.(\w+?)-(\d+(?:-\d+)*)$", identifier)
    if not match:
        return identifier
    return f"{match.group(1)} {match.group(2).replace('-', '.')}"


def parse_devices(listing: dict) -> list[Simulator]:
    sims = []
    for runtime, devices in listing.get("devices", {}).items():
        name = runtime_name(runtime)
        if not name.startswith(("iOS", "iPadOS")):
            continue
        for d in devices:
            if d.get("isAvailable", True):
                sims.append(Simulator(udid=d["udid"], name=d["name"], state=d["state"], runtime=name))
    return sims


def list_devices() -> list[Simulator]:
    return parse_devices(json.loads(run("list", "devices", "--json")))


def pick(simulators: list[Simulator], wanted: str | None) -> Simulator:
    """By UDID or name; without one, the only booted simulator."""
    if wanted:
        for sim in simulators:
            if wanted in (sim.udid, sim.name):
                if not sim.booted:
                    raise DeviceError(f"{sim.name} ({sim.udid}) is not booted: `xcrun simctl boot {sim.udid}`")
                return sim
        raise DeviceError(f"no simulator named or with UDID '{wanted}' (see `idt devices`)")
    booted = [s for s in simulators if s.booted]
    if not booted:
        raise DeviceError("no booted simulator: boot one with `xcrun simctl boot \"iPhone 17\"` "
                          "(names in `idt devices`), then open Simulator.app to watch it")
    if len(booted) > 1:
        names = ", ".join(f"{s.name} ({s.udid})" for s in booted)
        raise DeviceError(f"several simulators are booted ({names}): pass -s UDID")
    return booted[0]


def find(wanted: str | None) -> Simulator:
    return pick(list_devices(), wanted)


# --- apps ------------------------------------------------------------------------------------

def parse_app_list(raw: bytes) -> dict[str, dict]:
    """`simctl listapps` prints an old-style plist; plutil turns it into JSON."""
    proc = subprocess.run(["plutil", "-convert", "json", "-o", "-", "-"], input=raw, capture_output=True)
    if proc.returncode != 0:
        raise SimctlError(f"cannot read the app list: {proc.stderr.decode(errors='replace')}")
    return json.loads(proc.stdout)


def apps(udid: str) -> dict[str, dict]:
    return parse_app_list(run("listapps", udid))


def app_path(udid: str, bundle_id: str) -> Path:
    try:
        return Path(run("get_app_container", udid, bundle_id, "app").decode().strip())
    except SimctlError as exc:
        raise SimctlError(f"{bundle_id} is not installed on this simulator") from exc


def info_plist(app: Path) -> dict:
    with (app / "Info.plist").open("rb") as fh:
        return plistlib.load(fh)


def app_info(udid: str, bundle_id: str) -> dict:
    """Version facts in the report's keys: versionName is the marketing version, versionCode the build."""
    plist = info_plist(app_path(udid, bundle_id))
    return {
        "package": bundle_id,
        "name": plist.get("CFBundleDisplayName") or plist.get("CFBundleName", ""),
        "versionName": plist.get("CFBundleShortVersionString", ""),
        "versionCode": plist.get("CFBundleVersion", ""),
        "executable": plist.get("CFBundleExecutable", ""),
        "minimum_os": plist.get("MinimumOSVersion", ""),
    }


def bundle_of(app: Path) -> dict:
    """Facts of an .app folder before installing it."""
    plist = info_plist(app)
    return {"package": plist.get("CFBundleIdentifier", ""), "versionName": plist.get("CFBundleShortVersionString", ""),
            "versionCode": plist.get("CFBundleVersion", ""), "executable": plist.get("CFBundleExecutable", "")}


def install(udid: str, app: Path) -> None:
    run("install", udid, str(app), timeout=300)


def uninstall(udid: str, bundle_id: str) -> None:
    run("uninstall", udid, bundle_id)


def launch(udid: str, bundle_id: str) -> int | None:
    """Launch and return the pid ('com.example: 1234')."""
    out = run("launch", udid, bundle_id).decode()
    match = re.search(r":\s*(\d+)", out)
    return int(match.group(1)) if match else None


def terminate(udid: str, bundle_id: str) -> bool:
    """False when the app wasn't running."""
    try:
        run("terminate", udid, bundle_id)
        return True
    except SimctlError:
        return False


def screenshot(udid: str) -> bytes:
    """Through simctl; slower than the runner's, but works without it."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "screen.png"
        run("io", udid, "screenshot", "--type=png", str(target), timeout=30)
        return target.read_bytes()


def spawn(udid: str, *args: str) -> str:
    return run("spawn", udid, *args).decode(errors="replace").strip()


def locale(udid: str) -> str:
    try:
        return spawn(udid, "defaults", "read", "-g", "AppleLocale")
    except SimctlError:
        return ""


def languages(udid: str) -> list[str]:
    """Preferred languages in order, e.g. ['en-US', 'uk-NL']; the first decides the keyboard's language."""
    try:
        return re.findall(r'"?([A-Za-z]{2,3}(?:-[A-Za-z0-9]+)*)"?,?\s*$', spawn(udid, "defaults", "read", "-g",
                                                                              "AppleLanguages"), flags=re.M)
    except SimctlError:
        return []
