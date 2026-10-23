"""What happens to a finding after the session: confirmation by a person, the per-app known-issues registry,
regression test cases, and retest results.

A finding's `history` records every step (who, when, what, on which build and device), so a report shows
not only what was found but also how it was confirmed or verified.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import state

CONFIRM_RESULTS = ("reproduced", "not-reproduced")
ISSUE_STATUSES = ("open", "fixed", "wont-fix", "duplicate")
_TRIES_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_tries(text: str | None) -> tuple[int, int] | None:
    """'2/3' -> (2, 3); anything else ('not tried', None) -> None."""
    m = _TRIES_RE.match(text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _session_context(session: dict) -> tuple[str, str]:
    app, dev = session.get("app") or {}, session.get("device") or {}
    build = " ".join(str(app.get(k, "")) for k in ("versionName",)).strip()
    if app.get("versionCode"):
        build += f" ({app['versionCode']})"
    return build, str(dev.get("model", ""))


# --- manual confirmation ---------------------------------------------------------------------

def confirm(finding: dict, session: dict, result: str, by: str, tries: str | None = None,
            note: str = "", device: str | None = None, build: str | None = None) -> dict:
    """Record a person's reproduction attempt on a finding and update its manual count and status.

    `tries` like '2/2' (succeeded/attempted); defaults to 1/1 for reproduced and 0/1 for not reproduced.
    """
    if result not in CONFIRM_RESULTS:
        raise ValueError(f"result must be one of {CONFIRM_RESULTS}")
    parsed = parse_tries(tries) if tries else ((1, 1) if result == "reproduced" else (0, 1))
    if parsed is None:
        raise ValueError("tries must look like '2/3' (reproduced/attempted)")
    if result == "reproduced" and parsed[0] == 0:
        raise ValueError("'reproduced' needs at least one successful try")
    if result == "not-reproduced" and parsed[0] != 0:
        raise ValueError("'not-reproduced' means 0 successful tries")
    default_build, default_device = _session_context(session)
    repro = finding.setdefault("reproducibility", {})
    before = parse_tries(repro.get("manual")) or (0, 0)
    repro["manual"] = f"{before[0] + parsed[0]}/{before[1] + parsed[1]}"
    old_status = finding.get("status")
    if result == "reproduced" and old_status == "Unconfirmed":
        finding["status"] = "Confirmed"
    entry = {"time": _now(), "action": "manual-check", "result": result, "tries": f"{parsed[0]}/{parsed[1]}",
             "by": by, "build": build or default_build, "device": device or default_device}
    if note:
        entry["note"] = note
    if finding.get("status") != old_status:
        entry["status"] = f"{old_status} -> {finding['status']}"
    finding.setdefault("history", []).append(entry)
    return entry


def confirm_in_run(run: Path, finding_id: str, **kwargs) -> dict:
    session = json.loads((run / "session.json").read_text(encoding="utf-8"))
    path = run / "findings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    finding = next((f for f in data.get("findings", []) if f.get("id") == finding_id), None)
    if finding is None:
        raise LookupError(f"no finding {finding_id} in {path}")
    entry = confirm(finding, session, **kwargs)
    state.write_json(path, data)
    return {"finding": finding, "entry": entry}


# --- known-issues registry -------------------------------------------------------------------

def registry_path(config_dir: Path, package: str) -> Path:
    return config_dir / "apps" / package / "known-issues.json"


def load_registry(config_dir: Path, package: str) -> dict:
    return state.read_json(registry_path(config_dir, package)) or {"issues": []}


def _next_key(registry: dict) -> str:
    numbers = [int(i["key"].split("-", 1)[1]) for i in registry["issues"] if i.get("key", "").startswith("K-")]
    return f"K-{max(numbers, default=0) + 1}"


def _sighting(run: Path, session: dict, finding: dict) -> dict:
    build, device = _session_context(session)
    return {"run": run.name, "date": (session.get("started") or _now())[:10], "build": build, "device": device,
            "finding": finding["id"], "status": finding["status"]}


def sync_registry(run: Path, config_dir: Path, package: str) -> dict:
    """After a session: add its new in-scope bugs and accessibility findings to the app's registry, and
    record a sighting for findings the tester linked to a known issue (`known_issue: "K-3"`).

    Returns {"added": [...], "seen_again": [...]} with registry keys. Also writes a regression test case
    draft for every new issue that has steps, and links it from the issue.
    """
    session = json.loads((run / "session.json").read_text(encoding="utf-8"))
    findings_path = run / "findings.json"
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    registry = load_registry(config_dir, package)
    by_key = {i["key"]: i for i in registry["issues"]}
    added, seen = [], []
    for f in data.get("findings", []):
        if f.get("status") == "Retracted" or f.get("scope") == "outside" or f.get("type") == "observation":
            continue
        sighting = _sighting(run, session, f)
        key = f.get("known_issue")
        if key and key in by_key:
            issue = by_key[key]
            if not any(s["run"] == sighting["run"] and s["finding"] == f["id"] for s in issue["seen"]):
                issue["seen"].append(sighting)
                seen.append(key)
            if issue["status"] == "fixed":
                # Fixed earlier, found again: it's back.
                issue["status"] = "open"
                issue.setdefault("history", []).append({"time": _now(), "action": "reopened", "run": run.name})
            continue
        if key:
            continue  # linked to a key that doesn't exist; report check flags it
        key = _next_key(registry)
        issue = {
            "key": key, "title": f["title"], "type": f["type"], "severity": f.get("severity"),
            "priority": f.get("priority"), "area": f.get("area", ""), "status": "open",
            "confirmed": f["status"] == "Confirmed", "seen": [sighting], "jira": f.get("jira") or {},
        }
        if f.get("steps"):
            issue["test_case"] = f"tests/{key}.md"
            case = config_dir / "apps" / package / issue["test_case"]
            if not case.exists():
                case.parent.mkdir(parents=True, exist_ok=True)
                case.write_text(test_case_draft(key, f), encoding="utf-8")
        registry["issues"].append(issue)
        by_key[key] = issue
        f["known_issue"] = key
        f["new_issue"] = True  # first found in this session (vs. a known issue seen again)
        added.append(key)
    state.write_json(registry_path(config_dir, package), registry)
    state.write_json(findings_path, data)
    return {"added": added, "seen_again": seen}


def set_issue(config_dir: Path, package: str, key: str, status: str, note: str = "", run: str = "",
              build: str = "") -> dict:
    if status not in ISSUE_STATUSES:
        raise ValueError(f"status must be one of {ISSUE_STATUSES}")
    registry = load_registry(config_dir, package)
    issue = next((i for i in registry["issues"] if i["key"] == key), None)
    if issue is None:
        raise LookupError(f"no known issue {key} for {package}")
    entry = {"time": _now(), "action": "status", "status": f"{issue['status']} -> {status}"}
    entry.update({k: v for k, v in (("note", note), ("run", run), ("build", build)) if v})
    issue["status"] = status
    issue.setdefault("history", []).append(entry)
    state.write_json(registry_path(config_dir, package), registry)
    return issue


# --- regression test cases -------------------------------------------------------------------

def test_case_draft(key: str, finding: dict) -> str:
    """A regression test case in the test-case format: the bug's steps, with the expected result as the check.

    A draft: the tester reviews it (exact labels, data, a reset of the state) before relying on it.
    """
    lines = [f"# {key} Regression: {finding['title']}", "",
             f"<!-- Generated from finding {finding['id']}. Passes when the bug is fixed. Review before use. -->", "",
             "**Preconditions**"]
    lines += [f"- {p}" for p in finding.get("preconditions") or ["<state before step 1>"]]
    lines += ["", "**Steps**", ""]
    steps = finding.get("steps") or []
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step}")
        if i == len(steps):
            lines.append(f"   - Expected: {finding.get('expected') or '<expected result>'}")
    lines += ["", f"**Bug behaviour (fails the case):** {finding.get('actual', '')}", ""]
    return "\n".join(lines)
