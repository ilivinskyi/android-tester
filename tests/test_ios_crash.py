import os
import shutil
from pathlib import Path

from mobiletester.ios import crash

FIXTURE = Path(__file__).parent / "fixtures" / "Habits-2026-10-24-091201.ips"


def test_summary_names_the_exception_and_the_top_frames():
    text = crash.summary(FIXTURE, frames=3)
    assert text == ("EXC_BREAKPOINT (SIGTRAP), Trace/BPT trap: 5; in Habits: "
                    "Swift._assertionFailure(_:_:file:line:flags:) < HabitStore.delete(at:) < HabitListView.body.getter")


def test_find_only_new_reports_of_this_app(tmp_path):
    old = tmp_path / "Habits-2026-10-24-080000.ips"
    shutil.copy(FIXTURE, old)
    os.utime(old, (1000, 1000))
    new = tmp_path / FIXTURE.name
    shutil.copy(FIXTURE, new)
    other = tmp_path / "Habits Helper-2026-10-24-091201.ips"
    shutil.copy(FIXTURE, other)
    mac = tmp_path / "Habits-2026-10-24-091202.ips"
    mac.write_text('{"app_name":"Habits","bundleID":"com.example.mac.habits"}\n{}', encoding="utf-8")
    assert crash.find("Habits", "com.github.aint.Habits", since=2000, directory=tmp_path) == [new]
