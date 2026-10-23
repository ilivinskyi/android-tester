import json

import pytest

from adtlib import device, session, state
from adtlib.adb import AdbError

PKG = "com.example.notes"


class FakeAdb:
    """Answers the shell commands a reset uses; `foregrounds` are returned one per poll, the last one repeats."""

    serial = "fake-serial"

    def __init__(self, foregrounds: list[str], installed: bool = True):
        self.calls: list[str] = []
        self.foregrounds = list(foregrounds)
        self.installed = installed

    def shell(self, *args, check: bool = True, timeout=None) -> str:
        cmd = " ".join(args)
        self.calls.append(cmd)
        if cmd.startswith("dumpsys package"):
            return "    versionCode=10 minSdk=26 targetSdk=35\n    versionName=1.0" if self.installed else ""
        if cmd.startswith("pm clear"):
            return "Success"
        if "topResumedActivity" in cmd:
            package = self.foregrounds.pop(0) if len(self.foregrounds) > 1 else self.foregrounds[0]
            return f"  topResumedActivity=ActivityRecord{{a1b2 u0 {package}/.MainActivity t42}}"
        return ""


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(device.time, "sleep", lambda _s: None)


def _commands(adb: FakeAdb) -> list[str]:
    return [c.split()[0] + " " + c.split()[1] for c in adb.calls
            if c.startswith(("am force-stop", "pm clear", "monkey"))]


def test_restart_keeps_data():
    adb = FakeAdb([PKG])
    steps, foreground = device.app_reset(adb, PKG, "restart")
    assert steps == ["force-stop", "launch"] and foreground == PKG
    assert _commands(adb) == ["am force-stop", "monkey -p"]


def test_clear_data_clears_between_stop_and_launch():
    adb = FakeAdb([PKG])
    steps, _ = device.app_reset(adb, PKG, "clear-data")
    assert steps == ["force-stop", "clear data", "launch"]
    assert _commands(adb) == ["am force-stop", "pm clear", "monkey -p"]


def test_waits_until_the_app_is_in_front():
    adb = FakeAdb(["com.google.android.apps.nexuslauncher", "com.google.android.apps.nexuslauncher", PKG])
    _, foreground = device.app_reset(adb, PKG, "restart")
    assert foreground == PKG and sum("topResumedActivity" in c for c in adb.calls) == 3


def test_gives_up_when_the_app_never_comes_up():
    adb = FakeAdb(["com.google.android.apps.nexuslauncher"])
    with pytest.raises(AdbError, match="did not come to the foreground.*nexuslauncher"):
        device.app_reset(adb, PKG, "restart", timeout=0.05)


def test_not_installed_fails_before_touching_the_app():
    adb = FakeAdb([PKG], installed=False)
    with pytest.raises(AdbError, match="not installed"):
        device.app_reset(adb, PKG, "clear-data")
    assert _commands(adb) == []


def test_unknown_level_is_rejected():
    with pytest.raises(ValueError):
        device.app_reset(FakeAdb([PKG]), PKG, "factory")


def test_reset_is_listed_once_in_the_sessions_fast_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("ADT_HOME", str(tmp_path / ".adt"))
    run = tmp_path / "run"
    session.start("fake-serial", run, {"mode": "repro"})
    for _ in range(2):
        session.note_fast_step("fake-serial", "reset (clear-data)")
    data = json.loads((run / "session.json").read_text(encoding="utf-8"))
    assert data["setup_steps_fast"] == ["reset (clear-data)"]
    assert state.device_dir("fake-serial").is_relative_to(tmp_path)
