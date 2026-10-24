"""The MTRunner XCUITest runner (runner/ next to this file): building it, starting it, talking to it.

It is built once per Xcode version and source change into ~/Library/Caches/mobile-tester, then run with
`xcodebuild test-without-building` in the background. Its HTTP server listens on a port derived from the
UDID: on a simulator, which shares the Mac's network, at 127.0.0.1; on a real device at the device's end of
CoreDevice's tunnel (see devicectl.py), and only there, so nobody else on the Wi-Fi can drive the device.
Each start gets a random token that every request carries, so nothing else that reaches the port can use it.
A device build is signed by the user's team (signing.py) and made for that device, so its provisioning
profile includes it. That profile expires (after 7 days with a free personal team); `runner start` rebuilds
the runner with the saved team when less than REBUILD_MARGIN is left. Xcode reuses its cached profile until
that one has expired, so the rebuild first removes the cached profile of this runner's app id (and no other).
"""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import secrets
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..core import state
from ..core.proc import detached_kwargs, is_alive
from . import devicectl, signing

PROJECT = Path(__file__).resolve().parent / "runner"
SPRINGBOARD = "com.apple.springboard"
# XCUIApplication.State raw values.
APP_STATES = {0: "unknown", 1: "not running", 2: "background (suspended)", 3: "background", 4: "foreground"}
FOREGROUND = 4
# Rebuild a device runner whose profile expires within this time, so it can't run out during a session.
REBUILD_MARGIN = timedelta(days=1)


class RunnerError(Exception):
    pass


def start_hint(log: str) -> str:
    """The usual reasons a device refuses to run the runner, as what the person has to do."""
    if "Locked" in log or ("locked" in log and "passcode" in log):
        return ": the device is locked; unlock it and keep it unlocked while testing"
    if "UI Automation" in log or "Enable UI Automation" in log:
        return ": UI Automation is off; on the device, Settings > Developer > Enable UI Automation"
    if "untrusted" in log.lower() or "not trusted" in log.lower() or "invalid code signature" in log.lower():
        return (": the device doesn't trust the developer yet; on the device, Settings > General > VPN & Device "
                "Management, tap the developer app entry and Trust (the person holding the device does this)")
    if "Developer Mode" in log:
        return ": Developer Mode is off on the device (Settings > Privacy & Security > Developer Mode)"
    return ""


def port_for(udid: str) -> int:
    """A stable port per simulator, so several can run side by side."""
    return 22087 + int(hashlib.sha1(udid.encode()).hexdigest()[:4], 16) % 800


def _xcodebuild() -> str:
    path = shutil.which("xcodebuild")
    if not path:
        raise RunnerError("xcodebuild not found: install Xcode")
    return path


def _build_key() -> str:
    """Changes when the runner's sources or Xcode change, so a stale build is never used."""
    digest = hashlib.sha1()
    for path in sorted(PROJECT.rglob("*")):
        if path.is_file() and "xcuserdata" not in path.parts and path.name != ".gitignore":
            digest.update(path.relative_to(PROJECT).as_posix().encode())
            digest.update(path.read_bytes())
    version = subprocess.run([_xcodebuild(), "-version"], capture_output=True, text=True).stdout
    digest.update(version.encode())
    return digest.hexdigest()[:12]


def build_dir(device: str | None = None, team: str | None = None) -> Path:
    base = Path(os.environ.get("MT_CACHE", Path.home() / "Library" / "Caches" / "mobile-tester"))
    flavour = f"device-{team}-{device}" if device else "simulator"
    return base / "ios-runner" / _build_key() / flavour


def bundle_id(team: str) -> str:
    """App ids are unique across all teams, so the device build gets the team in its bundle id."""
    return f"dev.mobiletester.MTRunner.{team.lower()}"


def _build_command(directory: Path, device: str | None, team: str | None) -> list[str]:
    cmd = [_xcodebuild(), "build-for-testing", "-project", str(PROJECT / "MTRunner.xcodeproj"), "-scheme",
           "MTRunner", "-derivedDataPath", str(directory)]
    if not device:
        return [*cmd, "-destination", "generic/platform=iOS Simulator", "CODE_SIGNING_ALLOWED=NO"]
    # Automatic signing with the user's team; Xcode creates the App ID and a development profile and, for a
    # device it hasn't seen, registers it with the team.
    return [*cmd, "-destination", f"id={device}", "-allowProvisioningUpdates", "-allowProvisioningDeviceRegistration",
            f"DEVELOPMENT_TEAM={team}", "CODE_SIGN_STYLE=Automatic", f"PRODUCT_BUNDLE_IDENTIFIER={bundle_id(team)}"]


def xctestrun(build: bool = True, device: str | None = None, team: str | None = None) -> Path:
    """The built runner's .xctestrun file; builds it first when needed (about a minute, once).

    Without `device` it is the simulator build; with it, the build signed by `team` for that device.
    """
    if device and not team:
        raise signing.MissingTeam(signing.missing_team_message())
    directory = build_dir(device, team)
    found = sorted((directory / "Build" / "Products").glob("*.xctestrun")) if directory.exists() else []
    if found:
        return found[0]
    if not build:
        raise RunnerError("the runner is not built yet: `idt runner build`" + (" --team ID" if device else ""))
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / "build.log"
    with log.open("wb") as fh:
        proc = subprocess.run(_build_command(directory, device, team), stdout=fh, stderr=subprocess.STDOUT)
    found = sorted((directory / "Build" / "Products").glob("*.xctestrun"))
    if proc.returncode != 0 or not found:
        text = log.read_text(errors="replace")
        tail = "\n".join(text.splitlines()[-15:])
        hint = signing_hint(text) if device else ""
        raise RunnerError(f"building the runner failed{hint} (full log: {log}):\n{tail}")
    return found[0]


def parse_profile(decoded: bytes) -> datetime | None:
    """The expiry of a provisioning profile, from its decoded plist (`security cms -D`)."""
    try:
        expiry = plistlib.loads(decoded).get("ExpirationDate")
    except plistlib.InvalidFileException:
        return None
    if not isinstance(expiry, datetime):
        return None
    return expiry if expiry.tzinfo else expiry.replace(tzinfo=UTC)


def profile_expiry(testrun: Path) -> datetime | None:
    """When the device runner next to this .xctestrun stops launching: its embedded profile's expiry."""
    profiles = sorted(testrun.parent.glob("*/MTRunner-Runner.app/embedded.mobileprovision"))
    if not profiles:
        return None
    proc = subprocess.run(["security", "cms", "-D", "-i", str(profiles[0])], capture_output=True)
    return parse_profile(proc.stdout) if proc.returncode == 0 else None


def profiles_dir() -> Path:
    return Path(os.environ.get("MT_PROFILES_DIR",
                               Path.home() / "Library" / "Developer" / "Xcode" / "UserData" / "Provisioning Profiles"))


def app_id(team: str) -> str:
    """The application identifier in the runner's profile: team prefix, bundle id, XCUITest's suffix."""
    return f"{team}.{bundle_id(team)}.xctrunner"


def profile_app_id(decoded: bytes) -> str:
    try:
        return str((plistlib.loads(decoded).get("Entitlements") or {}).get("application-identifier", ""))
    except plistlib.InvalidFileException:
        return ""


def forget_cached_profiles(team: str) -> list[Path]:
    """Remove Xcode's cached profiles for this runner, so the next build fetches a new one. Others stay."""
    removed = []
    for path in sorted(profiles_dir().glob("*.mobileprovision")):
        proc = subprocess.run(["security", "cms", "-D", "-i", str(path)], capture_output=True)
        if proc.returncode == 0 and profile_app_id(proc.stdout) == app_id(team):
            path.unlink()
            removed.append(path)
    return removed


def needs_rebuild(expiry: datetime | None, now: datetime | None = None) -> bool:
    """An unknown expiry counts as fine: a runner that can't launch says so itself (start_hint)."""
    return expiry is not None and expiry - (now or datetime.now(UTC)) < REBUILD_MARGIN


def fresh_device_build(device: str, team: str) -> tuple[Path, str | None]:
    """The device runner, rebuilt first when its profile is about to expire; (xctestrun, note or None)."""
    testrun = xctestrun(device=device, team=team)
    expiry = profile_expiry(testrun)
    kept = build_dir(device, team) / "kept-profile.txt"
    already_tried = kept.is_file() and kept.read_text() == expiry.isoformat() and expiry > datetime.now(UTC)
    if not needs_rebuild(expiry) or already_tried:
        return testrun, None
    forget_cached_profiles(team)
    shutil.rmtree(build_dir(device, team))
    testrun = xctestrun(device=device, team=team)
    renewed = profile_expiry(testrun)
    when = "expired" if expiry < datetime.now(UTC) else "expires"
    note = f"the runner's signing {when} {local_time(expiry)}; rebuilt it with team {team}"
    if renewed == expiry:
        # Apple handed back the same profile; it makes a new one once this one has expired. Don't rebuild until then.
        kept.write_text(expiry.isoformat())
        return testrun, note + ", but got the same profile back; it renews once it has expired"
    return testrun, note + (f", valid until {local_time(renewed)}" if renewed else "")


def local_time(moment: datetime) -> str:
    return f"{moment.astimezone():%Y-%m-%d %H:%M}"


def signing_hint(build_log: str) -> str:
    """What the user has to do about the usual signing failures, in front of the raw log."""
    if "No Accounts" in build_log or "No account for team" in build_log:
        return ": the team's Apple ID is not signed in to Xcode (Xcode > Settings > Accounts; the user does this)"
    if "No signing certificate" in build_log or "No profiles for" in build_log:
        return (": Xcode could not create a development certificate or profile for this team; open Xcode > "
                "Settings > Accounts, select the team and Manage Certificates (the user does this)")
    if "Developer Mode" in build_log:
        return ": Developer Mode is off on the device"
    return ""


class Runner:
    def __init__(self, udid: str, port: int | None = None, physical: bool = False):
        self.udid = udid
        self.port = port or port_for(udid)
        self.physical = physical
        self._host = None if physical else "127.0.0.1"

    @property
    def _state_file(self) -> Path:
        return state.device_dir(self.udid) / "runner.json"

    @property
    def host(self) -> str:
        """127.0.0.1 for a simulator; for a device the tunnel address the runner was started with."""
        if self._host is None:
            self._host = (state.read_json(self._state_file) or {}).get("host") or devicectl.tunnel_address(self.udid)
        return self._host

    @property
    def url(self) -> str:
        return f"http://[{self.host}]:{self.port}" if ":" in self.host else f"http://{self.host}:{self.port}"

    def call(self, method: str, path: str, body: dict | None = None, timeout: float = 60) -> dict | bytes:
        try:
            return self._call(method, path, body, timeout)
        except RunnerError as exc:
            if not (self.physical and isinstance(exc.__cause__, OSError) and self._retunnel()):
                raise
            return self._call(method, path, body, timeout)

    def _retunnel(self) -> bool:
        """The tunnel came back with a new address (cable replugged, Wi-Fi changed): follow it."""
        try:
            address = devicectl.tunnel_address(self.udid)
        except devicectl.DevicectlError:
            return False
        if address == self._host:
            return False
        self._host = address
        if running := state.read_json(self._state_file):
            state.write_json(self._state_file, {**running, "host": address})
        return True

    def _call(self, method: str, path: str, body: dict | None, timeout: float) -> dict | bytes:
        data = json.dumps(body or {}).encode() if method == "POST" else None
        headers = {"Content-Type": "application/json", "X-MT-Token": self._token()}
        request = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
                if response.headers.get_content_type() == "image/png":
                    return payload
                return json.loads(payload or b"{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RunnerError(f"runner {path}: {detail}") from exc
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            cause = exc.reason if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, OSError) else exc
            raise RunnerError(f"the runner is not reachable on {self.url} ({exc}); start it with "
                              "`idt runner start`") from cause

    def _token(self) -> str:
        return (state.read_json(self._state_file) or {}).get("token", "")

    def alive(self) -> bool:
        if self.physical:
            # On a device the runner lives only as long as the xcodebuild that started it; checking that first
            # saves bringing up a tunnel just to find nothing there.
            running = state.read_json(self._state_file)
            if not running or not is_alive(running["pid"]):
                return False
        try:
            return bool(self.call("GET", "/status", timeout=2 if not self.physical else 5).get("ok"))
        except RunnerError:
            return False

    # --- lifecycle -------------------------------------------------------------------------------

    def start(self, timeout: float | None = None) -> str:
        if self.alive():
            return "already running"
        note = None
        if self.physical:
            team = signing.team()
            if not team:
                raise signing.MissingTeam(signing.missing_team_message())
            testrun, note = fresh_device_build(self.udid, team)
        else:
            testrun = xctestrun()
        log = state.device_dir(self.udid) / "runner.log"
        token = secrets.token_urlsafe(24)
        env = {**os.environ, "TEST_RUNNER_MT_RUNNER_PORT": str(self.port), "TEST_RUNNER_MT_RUNNER_TOKEN": token}
        if self.physical:
            env["TEST_RUNNER_MT_RUNNER_BIND"] = "tunnel"
        with log.open("wb") as fh:
            proc = subprocess.Popen(
                [_xcodebuild(), "test-without-building", "-xctestrun", str(testrun), "-destination",
                 f"id={self.udid}"],
                stdout=fh, stderr=subprocess.STDOUT, env=env, **detached_kwargs())
        running = {"pid": proc.pid, "port": self.port, "log": str(log), "token": token}
        state.write_json(self._state_file, running)
        # A device installs the runner over the cable or Wi-Fi first, and may wait for its screen to unlock.
        deadline = time.monotonic() + (timeout or (300 if self.physical else 180))
        while time.monotonic() < deadline:
            if self.physical and self._host is None:
                # xcodebuild holds the tunnel while it runs the test, so its address is stable from here on.
                try:
                    self._host = devicectl.tunnel_address(self.udid)
                    state.write_json(self._state_file, {**running, "host": self._host})
                except devicectl.DevicectlError:
                    pass
            if self._host is not None and self.alive():
                return (f"{note}\n" if note else "") + f"started on {self.url} (xcodebuild pid {proc.pid})"
            if proc.poll() is not None:
                text = log.read_text(errors="replace")
                tail = "\n".join(text.splitlines()[-15:])
                raise RunnerError(f"the runner exited during start{start_hint(text)} (log: {log}):\n{tail}")
            time.sleep(1)
        raise RunnerError(f"the runner did not answer within {timeout or (300 if self.physical else 180):.0f}s "
                          f"(log: {log})")

    def ensure(self) -> None:
        if not self.alive():
            self.start()

    def stop(self) -> str:
        stopped = False
        running = state.read_json(self._state_file)
        if running or not self.physical:
            try:
                self.call("POST", "/shutdown", timeout=5)
                stopped = True
            except (RunnerError, devicectl.DevicectlError):
                pass
        if running and is_alive(running["pid"]):
            deadline = time.monotonic() + 15
            while is_alive(running["pid"]) and time.monotonic() < deadline:
                time.sleep(0.5)
            if is_alive(running["pid"]):
                os.killpg(running["pid"], signal.SIGTERM)
            stopped = True
        self._state_file.unlink(missing_ok=True)
        return "stopped" if stopped else "was not running"

    # --- UI --------------------------------------------------------------------------------------

    def info(self) -> dict:
        return self.call("GET", "/info")

    def tree(self, bundle_id: str) -> dict:
        return self.call("POST", "/tree", {"bundle_id": bundle_id})

    def screenshot(self) -> bytes:
        return self.call("GET", "/screenshot", timeout=30)

    def press(self, x: float, y: float, seconds: float, bundle_id: str = SPRINGBOARD) -> None:
        self.call("POST", "/press", {"bundle_id": bundle_id, "x": x, "y": y, "duration": seconds})

    def drag(self, x1: float, y1: float, x2: float, y2: float, hold: float, velocity: float,
             bundle_id: str = SPRINGBOARD) -> None:
        self.call("POST", "/drag", {"bundle_id": bundle_id, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                                    "hold": hold, "velocity": velocity})

    def home(self) -> None:
        self.call("POST", "/home")

    def app(self, bundle_id: str, action: str) -> int:
        return int(self.call("POST", "/app", {"bundle_id": bundle_id, "action": action})["state"])
