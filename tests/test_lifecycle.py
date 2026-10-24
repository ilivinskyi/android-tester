import json

import pytest

from mobiletester.core import lifecycle

SESSION = {"started": "2026-10-23T13:02:00+02:00", "app": {"versionName": "1.0", "versionCode": "10"},
           "device": {"model": "Pixel 7a"}}


def _finding(**over):
    f = {"id": "B3", "title": "Field resets after rotation", "type": "bug", "status": "Unconfirmed",
         "severity": "Major", "priority": "P2", "area": "Editor", "preconditions": ["A note is open"],
         "steps": ["Type 'abc'", "Rotate the phone"], "expected": "The text stays.", "actual": "The field is empty.",
         "reproducibility": {"automated": "3/3", "manual": "not tried"}}
    f.update(over)
    return f


def test_manual_reproduction_confirms_and_counts():
    f = _finding()
    entry = lifecycle.confirm(f, SESSION, "reproduced", by="Ihor", tries="2/2", note="Same on emulator")
    assert f["status"] == "Confirmed" and f["reproducibility"]["manual"] == "2/2"
    assert entry["status"] == "Unconfirmed -> Confirmed" and entry["build"] == "1.0 (10)"
    assert entry["device"] == "Pixel 7a" and entry["note"] == "Same on emulator"


def test_failed_manual_attempts_add_up_and_keep_status():
    f = _finding(reproducibility={"automated": "17/18", "manual": "0/2"})
    lifecycle.confirm(f, SESSION, "not-reproduced", by="Ihor")
    assert f["status"] == "Unconfirmed" and f["reproducibility"]["manual"] == "0/3"
    assert len(f["history"]) == 1 and "status" not in f["history"][0]


def test_inconsistent_confirmation_is_rejected():
    with pytest.raises(ValueError):
        lifecycle.confirm(_finding(), SESSION, "reproduced", by="x", tries="0/2")
    with pytest.raises(ValueError):
        lifecycle.confirm(_finding(), SESSION, "not-reproduced", by="x", tries="1/2")
    with pytest.raises(ValueError):
        lifecycle.confirm(_finding(), SESSION, "maybe", by="x")


def _run(tmp_path, findings, name="2026-10-23-notes-explore"):
    run = tmp_path / "reports" / name
    run.mkdir(parents=True)
    (run / "session.json").write_text(json.dumps(SESSION), encoding="utf-8")
    (run / "findings.json").write_text(json.dumps({"findings": findings}), encoding="utf-8")
    return run


def test_registry_adds_new_issues_with_test_case_drafts(tmp_path):
    config = tmp_path / ".android-tester"
    run = _run(tmp_path, [
        _finding(),
        _finding(id="O1", type="observation", title="Odd tone"),
        _finding(id="B4", scope="outside", title="Elsewhere"),
        _finding(id="R1", status="Retracted", notes="wrong"),
    ])
    result = lifecycle.sync_registry(run, config, "com.example.notes")
    assert result == {"added": ["K-1"], "seen_again": []}
    issue = lifecycle.load_registry(config, "com.example.notes")["issues"][0]
    assert issue["key"] == "K-1" and issue["status"] == "open" and issue["confirmed"] is False
    assert issue["seen"][0]["finding"] == "B3" and issue["seen"][0]["build"] == "1.0 (10)"
    case = (config / "apps" / "com.example.notes" / "tests" / "K-1.md").read_text(encoding="utf-8")
    assert "1. Type 'abc'" in case and "Expected: The text stays." in case
    findings = json.loads((run / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings[0]["known_issue"] == "K-1" and findings[0]["new_issue"] is True


def test_known_issue_seen_again_is_not_added_twice_and_reopens_fixed(tmp_path):
    config = tmp_path / ".android-tester"
    lifecycle.sync_registry(_run(tmp_path, [_finding()]), config, "com.example.notes")
    lifecycle.set_issue(config, "com.example.notes", "K-1", "fixed", note="retest passed", build="1.1 (11)")
    second = _run(tmp_path, [_finding(id="B1", known_issue="K-1")], name="2026-10-30-notes-explore")
    result = lifecycle.sync_registry(second, config, "com.example.notes")
    assert result == {"added": [], "seen_again": ["K-1"]}
    issue = lifecycle.load_registry(config, "com.example.notes")["issues"][0]
    assert issue["status"] == "open" and len(issue["seen"]) == 2
    assert [h["action"] for h in issue["history"]] == ["status", "reopened"]
    # Running sync again on the same run doesn't double-count.
    assert lifecycle.sync_registry(second, config, "com.example.notes")["seen_again"] == []


def test_set_issue_validates(tmp_path):
    config = tmp_path / ".android-tester"
    with pytest.raises(LookupError):
        lifecycle.set_issue(config, "com.example.notes", "K-9", "fixed")
    lifecycle.sync_registry(_run(tmp_path, [_finding()]), config, "com.example.notes")
    with pytest.raises(ValueError):
        lifecycle.set_issue(config, "com.example.notes", "K-1", "gone")
