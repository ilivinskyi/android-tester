import json

import pytest

from adtlib import report

SESSION = {
    "title": "Shop app - exploratory test", "mode": "explore", "charter": "Guest basket journey",
    "tester": "Test Er", "ticket": {"key": "SHOP-1", "summary": "Basket"},
    "device": {"model": "Pixel 7a", "android": "17", "sdk": "37", "emulator": False, "navigation": "gesture",
               "keyboard": "com.google.android.inputmethod.latin/x", "locale": "en-US"},
    "app": {"package": "com.example.shop", "versionName": "1.0", "versionCode": "10"},
    "input": "adt human mode", "not_covered": ["Checkout"],
}


def _bug(**over):
    bug = {
        "id": "B1", "title": "Quantity sticks at 0", "type": "bug", "status": "Confirmed", "severity": "Medium",
        "priority": "P2", "steps": ["Add milk", "Type 999"], "expected": "Capped", "actual": "Shows 0",
        "reproducibility": {"automated": "2/2", "manual": "1/1"},
        "evidence": [{"type": "screenshot", "path": "screenshots/b1.png", "caption": "stuck"}],
    }
    bug.update(over)
    return bug


@pytest.fixture
def run(tmp_path):
    (tmp_path / "screenshots").mkdir()
    (tmp_path / "screenshots" / "b1.png").write_bytes(b"\x89PNG")
    (tmp_path / "session.json").write_text(json.dumps(SESSION), encoding="utf-8")

    def write(findings):
        (tmp_path / "findings.json").write_text(json.dumps({"findings": findings}), encoding="utf-8")
        return tmp_path

    return write


def test_valid_run_passes_and_builds(run):
    findings = [
        _bug(severity="Major"),
        _bug(id="B2", status="Unconfirmed", severity="Major", reproducibility={"automated": "17/18", "manual": "0/2"}),
        {"id": "A1", "title": "Label read twice", "type": "accessibility", "status": "Confirmed",
         "severity": "Minor", "expected": "Read once", "actual": "Read twice"},
        {"id": "O1", "title": "Odd copy", "type": "observation", "status": "Confirmed", "actual": "Mixed u/je"},
        {"id": "R1", "title": "Prices missing", "type": "accessibility", "status": "Retracted",
         "notes": "Parser dropped them"},
    ]
    directory = run(findings)
    assert report.check(directory) == []
    written = report.build(directory)
    page = (directory / "index.html").read_text(encoding="utf-8")
    for fid in ("B1", "B2", "A1", "O1", "R1"):
        assert f'id="{fid}"' in page
    assert "Unconfirmed: needs manual reproduction" in page and "Retracted during the session" in page
    assert {p.name for p in written} == {"index.html", "B1.md", "B2.md", "A1.md"}
    md = (directory / "bugs" / "B1.md").read_text(encoding="utf-8")
    assert "**Steps to reproduce:**" in md and "1. Add milk" in md and "gesture navigation" in md
    assert "SHOP-1" in md


def test_problems_are_reported(run):
    directory = run([
        _bug(severity="Medium"),                                               # invalid severity
        _bug(id="B2", steps=[], evidence=[{"type": "video", "path": "videos/missing.mp4"}]),
        _bug(id="B3", status="Unconfirmed", reproducibility={"automated": "3/3"}),
        _bug(id="B4", severity="Major", reproducibility={"automated": "3/3"}),  # Major, automation only
        {"id": "R1", "title": "x", "type": "bug", "status": "Retracted"},       # no reason
    ])
    problems = "\n".join(report.check(directory))
    assert "finding B1: severity must be one of" in problems
    assert "finding B2: 'steps' is required" in problems
    assert "evidence file not found: videos/missing.mp4" in problems
    assert "finding B3: an Unconfirmed finding must state the manual result" in problems
    assert "finding B4: a Major bug confirmed only by automation should be Unconfirmed" in problems
    assert "finding R1: a retracted finding must say why" in problems


def test_test_results_rendered_and_validated(run, tmp_path):
    session = dict(SESSION, mode="test-case", test_results=[
        {"case": "TC-1 Add to basket", "step": 2, "result": "fail", "finding": "B1"},
        {"case": "TC-2 Search", "result": "pass"},
    ])
    (tmp_path / "session.json").write_text(json.dumps(session), encoding="utf-8")
    directory = run([_bug(severity="Minor")])
    assert report.check(directory) == []
    report.build(directory)
    page = (directory / "index.html").read_text(encoding="utf-8")
    assert "Test results" in page and 'href="#B1"' in page and "PASS" in page

    session["test_results"].append({"case": "TC-3", "result": "blocked"})
    (tmp_path / "session.json").write_text(json.dumps(session), encoding="utf-8")
    assert any("needs 'finding' or 'note'" in p for p in report.check(directory))


def test_html_escapes_content(run):
    directory = run([_bug(severity="Minor", title="<script>alert(1)</script>")])
    report.build(directory)
    page = (directory / "index.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
