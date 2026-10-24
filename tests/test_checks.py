"""Per-action app log checks, memory object counts and the leak verdict."""

from mobiletester.android import applog, perf
from mobiletester.core import report_text

PKG = "com.example.notes"

# `logcat -v threadtime`, shaped like a Pixel 7a on Android 17.
LOG = """--------- beginning of main
10-23 15:04:30.001  1500  1600 I ActivityManager: Start proc 4321:com.example.notes/u0a321 for top-activity
10-23 15:04:31.120  4321  4321 E SyncWorker: Upload failed for note 1234: HTTP 500
10-23 15:04:31.121  4321  4330 W System.err: java.net.SocketTimeoutException: timeout after 10000ms
10-23 15:04:31.122  4321  4330 W System.err: \tat okhttp3.internal.Foo.read(Foo.java:12)
10-23 15:04:31.200  4321  4330 W System.err: java.lang.IllegalStateException: cursor closed
10-23 15:04:32.000  4321  4321 I Choreographer: Skipped 12 frames!  The application may be doing too much work.
10-23 15:04:32.500  4321  4321 I Choreographer: Skipped 48 frames!  The application may be doing too much work.
10-23 15:04:33.000  4321  4321 D StrictMode: StrictMode policy violation; ~duration=42 ms: DiskReadViolation
10-23 15:04:33.100  9999  9999 E OtherApp: not ours
10-23 15:04:34.000  4321  4321 E SyncWorker: Upload failed for note 5678: HTTP 500
10-23 15:04:35.000  1500  1600 I ActivityManager: Start proc 4400:com.example.notes:sync/u0a321 for service
10-23 15:04:35.500  4400  4400 E art: Throwing OutOfMemoryError "Failed to allocate a 1048588 byte allocation"
"""

MEMINFO_OBJECTS = """ Objects
               Views:     1532         ViewRootImpl:        2
         AppContexts:        6           Activities:        3
              Assets:       22        AssetManagers:        0
       Local Binders:       61        Proxy Binders:       48
    Death Recipients:        3             WebViews:        1
"""


def test_only_the_apps_processes_and_lines_that_matter():
    issues, pids = applog.parse(LOG.splitlines(), set(), PKG)
    assert pids == {4321, 4400}  # both picked up from "Start proc", including the :sync process
    assert [(i.kind, i.tag) for i in issues] == [
        ("error", "SyncWorker"), ("network", "System.err"), ("exception", "System.err"),
        ("skipped frames", "Choreographer"), ("strict mode", "StrictMode"), ("error", "SyncWorker"),
        ("out of memory", "art")]  # not the stack frame, not 12 skipped frames, not another app


def test_summary_groups_the_same_problem_and_puts_the_worst_first():
    groups = applog.summarize(applog.parse(LOG.splitlines(), set(), PKG)[0])
    assert groups[0]["kind"] == "out of memory"
    upload = next(g for g in groups if g["tag"] == "SyncWorker")
    assert upload["count"] == 2 and upload["first"] == "10-23 15:04:31.120"  # note ids differ, same problem


def test_app_pids_from_ps():
    ps = "  PID NAME\n 4321 com.example.notes\n 4400 com.example.notes:sync\n 4500 com.example.notesplus\n"
    assert applog.app_pids(ps, PKG) == {4321, 4400}


class _Adb:
    serial = "log-serial"

    def shell(self, *args, check=True, timeout=None):
        return "  PID NAME\n 4321 com.example.notes\n"


def test_each_check_reads_only_new_complete_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("MT_HOME", str(tmp_path / ".adt"))
    log = tmp_path / "run" / "logs" / "logcat.txt"
    log.parent.mkdir(parents=True)
    lines = LOG.splitlines(keepends=True)
    log.write_text("".join(lines[:4]) + lines[4][:20], encoding="utf-8")  # last line still being written
    first = applog.new_issues(_Adb(), tmp_path / "run", PKG)
    assert [i.kind for i in first] == ["error", "network"]
    log.write_text("".join(lines), encoding="utf-8")
    second = applog.new_issues(_Adb(), tmp_path / "run", PKG)
    assert [i.kind for i in second][:2] == ["exception", "skipped frames"] and len(first) + len(second) == 7
    assert applog.new_issues(_Adb(), tmp_path / "run", PKG) == []


def test_meminfo_object_counts():
    assert perf.parse_objects(MEMINFO_OBJECTS) == {"activities": 3, "view_roots": 2, "app_contexts": 6,
                                                   "views": 1532, "webviews": 1}


def _sample(activities, views, pss_mb):
    return {"activities": activities, "view_roots": 1, "app_contexts": 4, "views": views, "webviews": 0,
            "pss_kb": pss_mb * 1024}


def test_leak_verdict_flags_steady_growth_only():
    leaking = [_sample(1, 400, 200), _sample(2, 520, 214), _sample(3, 640, 226), _sample(4, 760, 240)]
    verdict = perf.leak_verdict(leaking)
    assert verdict["verdict"] == "suspected leak" and verdict["cycles"] == 3
    assert set(verdict["growing"]) == {"activities", "views", "pss_kb"}
    # Memory that goes up and comes back down is the app caching, not leaking.
    healthy = [_sample(1, 400, 200), _sample(1, 420, 230), _sample(1, 410, 205), _sample(1, 415, 212)]
    assert perf.leak_verdict(healthy)["verdict"] == "no leak seen"
    assert perf.leak_verdict(leaking[:3])["verdict"] == "not enough cycles"


def test_report_rows_for_memory_trend_and_leaks():
    rows = dict(report_text.performance_rows({
        "memory_trend": [{"pss_kb": 200 * 1024, "activities": 1}, {"pss_kb": 260 * 1024, "activities": 3}],
        "leaks": {"Open a note and go back": perf.leak_verdict(
            [_sample(1, 400, 200), _sample(2, 520, 214), _sample(3, 640, 226), _sample(4, 760, 240)])}}))
    assert rows["Memory during the session"] == ("200 MB to 260 MB PSS over 2 samples, peak 260 MB; "
                                                 "live Activities 1 to 3")
    assert rows["Leak check: Open a note and go back"].startswith(
        "Suspected leak after 3 cycles (Activities 1 > 2 > 3 > 4; Views 400 > 520 > 640 > 760; PSS 200 MB > ")
