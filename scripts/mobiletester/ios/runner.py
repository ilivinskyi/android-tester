"""The MTRunner XCUITest runner (runner/ next to this file): building it, starting it, talking to it.

It is built once per Xcode version and source change into ~/Library/Caches/mobile-tester, then run with
`xcodebuild test-without-building` in the background. Its HTTP server listens inside the simulator, which
shares the Mac's network, on a port derived from the simulator's UDID.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..core import state
from ..core.proc import detached_kwargs, is_alive

PROJECT = Path(__file__).resolve().parent / "runner"
SPRINGBOARD = "com.apple.springboard"
# XCUIApplication.State raw values.
APP_STATES = {0: "unknown", 1: "not running", 2: "background (suspended)", 3: "background", 4: "foreground"}
FOREGROUND = 4


class RunnerError(Exception):
    pass


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


def build_dir() -> Path:
    base = Path(os.environ.get("MT_CACHE", Path.home() / "Library" / "Caches" / "mobile-tester"))
    return base / "ios-runner" / _build_key()


def xctestrun(build: bool = True) -> Path:
    """The built runner's .xctestrun file; builds it first when needed (about a minute, once)."""
    directory = build_dir()
    found = sorted((directory / "Build" / "Products").glob("*.xctestrun")) if directory.exists() else []
    if found:
        return found[0]
    if not build:
        raise RunnerError("the runner is not built yet: `idt runner build`")
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / "build.log"
    with log.open("wb") as fh:
        proc = subprocess.run(
            [_xcodebuild(), "build-for-testing", "-project", str(PROJECT / "MTRunner.xcodeproj"), "-scheme",
             "MTRunner", "-destination", "generic/platform=iOS Simulator", "-derivedDataPath", str(directory),
             "CODE_SIGNING_ALLOWED=NO"],
            stdout=fh, stderr=subprocess.STDOUT)
    found = sorted((directory / "Build" / "Products").glob("*.xctestrun"))
    if proc.returncode != 0 or not found:
        tail = "\n".join(log.read_text(errors="replace").splitlines()[-15:])
        raise RunnerError(f"building the runner failed (full log: {log}):\n{tail}")
    return found[0]


class Runner:
    def __init__(self, udid: str, port: int | None = None):
        self.udid = udid
        self.port = port or port_for(udid)
        self.url = f"http://127.0.0.1:{self.port}"

    @property
    def _state_file(self) -> Path:
        return state.device_dir(self.udid) / "runner.json"

    def call(self, method: str, path: str, body: dict | None = None, timeout: float = 60) -> dict | bytes:
        data = json.dumps(body or {}).encode() if method == "POST" else None
        request = urllib.request.Request(self.url + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
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
            raise RunnerError(f"the runner is not reachable on {self.url} ({exc}); start it with "
                              "`idt runner start`") from exc

    def alive(self) -> bool:
        try:
            return bool(self.call("GET", "/status", timeout=2).get("ok"))
        except RunnerError:
            return False

    # --- lifecycle -------------------------------------------------------------------------------

    def start(self, timeout: float = 180) -> str:
        if self.alive():
            return "already running"
        testrun = xctestrun()
        log = state.device_dir(self.udid) / "runner.log"
        env = {**os.environ, "TEST_RUNNER_MT_RUNNER_PORT": str(self.port)}
        with log.open("wb") as fh:
            proc = subprocess.Popen(
                [_xcodebuild(), "test-without-building", "-xctestrun", str(testrun), "-destination",
                 f"id={self.udid}"],
                stdout=fh, stderr=subprocess.STDOUT, env=env, **detached_kwargs())
        state.write_json(self._state_file, {"pid": proc.pid, "port": self.port, "log": str(log)})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.alive():
                return f"started on port {self.port} (xcodebuild pid {proc.pid})"
            if proc.poll() is not None:
                tail = "\n".join(log.read_text(errors="replace").splitlines()[-15:])
                raise RunnerError(f"the runner exited during start (log: {log}):\n{tail}")
            time.sleep(1)
        raise RunnerError(f"the runner did not answer within {timeout:.0f}s (log: {log})")

    def ensure(self) -> None:
        if not self.alive():
            self.start()

    def stop(self) -> str:
        stopped = False
        try:
            self.call("POST", "/shutdown", timeout=5)
            stopped = True
        except RunnerError:
            pass
        running = state.read_json(self._state_file)
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
