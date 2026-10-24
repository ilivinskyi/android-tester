"""Report vocabulary and the plain-text outputs: Markdown drafts, Jira wiki markup, the Jira bulk-import CSV.

Shared by report.py (validation, build) and report_html.py (the pages).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

TYPES = ("bug", "accessibility", "observation")
SEVERITIES = ("Blocker", "Critical", "Major", "Minor", "Trivial")
PRIORITIES = ("P1", "P2", "P3", "P4")
STATUSES = ("Confirmed", "Unconfirmed", "Retracted")
SCOPES = ("in", "outside")
EVIDENCE_TYPES = ("screenshot", "video", "log", "xml", "other")
TEST_RESULTS = ("pass", "fail", "blocked", "skipped")
TYPE_NAMES = {"bug": "Bug", "accessibility": "Accessibility", "observation": "Observation"}
SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITIES)}
RETEST_WORDS = {"pass": "Fixed", "fail": "Still reproduces", "blocked": "Can't verify", "skipped": "Skipped"}
# Jira's default priority scheme, for the bulk-import CSV.
JIRA_PRIORITIES = {"P1": "Highest", "P2": "High", "P3": "Medium", "P4": "Low"}

_KEYBOARDS = {
    "com.google.android.inputmethod.latin": "Gboard",
    "com.samsung.android.honeyboard": "Samsung Keyboard",
    "com.touchtype.swiftkey": "Microsoft SwiftKey",
}


def outside(f: dict) -> bool:
    return f.get("scope") == "outside"


def seen_again(f: dict) -> bool:
    return bool(f.get("known_issue")) and not f.get("new_issue")


def fileable(f: dict) -> bool:
    """Findings someone may file as a ticket: bugs and accessibility issues that weren't retracted."""
    return f["status"] != "Retracted" and f["type"] != "observation"


def keyboard_name(ime: str) -> str:
    package = (ime or "?").split("/", 1)[0]
    return _KEYBOARDS.get(package, package)


def time_range(session: dict) -> str | None:
    """'23 Oct 2026, 14:40-14:52 (12 min, time box 15 min)' from the ISO start/end times."""
    if not session.get("started"):
        return None
    start = datetime.fromisoformat(session["started"])
    text = f"{start:%d %b %Y}, {start:%H:%M}"
    extra = []
    if session.get("ended"):
        end = datetime.fromisoformat(session["ended"])
        text += f"-{end:%H:%M}"
        extra.append(f"{round((end - start).total_seconds() / 60)} min")
    if session.get("time_box_min"):
        extra.append(f"time box {session['time_box_min']} min")
    return text + (f" ({', '.join(extra)})" if extra else "")


def repro(f: dict) -> str:
    r = f.get("reproducibility") or {}
    parts = [f"automated {r['automated']}" if r.get("automated") else "",
             f"manual {r['manual']}" if r.get("manual") else ""]
    return ", ".join(p for p in parts if p)


def summary(f: dict) -> str:
    """One line for the list: the finding's own summary, or the start of what was seen."""
    text = f.get("summary") or f.get("actual") or f.get("notes") or ""
    text = " ".join(str(text).split())
    return text if len(text) <= 200 else text[:199].rstrip() + "…"


def environment(session: dict) -> list[tuple[str, str]]:
    dev, app = session.get("device") or {}, session.get("app") or {}
    ticket = session.get("ticket")
    if isinstance(ticket, dict):
        ticket = " - ".join(str(ticket.get(k)) for k in ("key", "summary") if ticket.get(k))
    rows = [
        ("Charter", session.get("charter")),
        ("Mode", session.get("mode")),
        ("Ticket", ticket),
        ("Tester", session.get("tester")),
        ("Time", time_range(session)),
        ("App", " ".join(str(app.get(k, "")) for k in ("package", "versionName")).strip()
         + (f" ({app['versionCode']})" if app.get("versionCode") else "")),
        ("Install source", app.get("install_source")),
        ("Device", f"{dev.get('manufacturer', '')} {dev.get('model', '')}, Android {dev.get('android', '')} "
                   f"(API {dev.get('sdk', '')}), {dev.get('screen', '')} at {dev.get('density', '')} dpi"
         if dev else None),
        ("Device kind", ("emulator" if dev.get("emulator") else "physical") if dev else None),
        ("Navigation and keyboard",
         f"{dev.get('navigation', '')} navigation, {keyboard_name(dev.get('keyboard', ''))}" if dev else None),
        ("Locale", dev.get("locale")),
        ("Input", session.get("input")),
        ("Setup steps run fast", ", ".join(session.get("setup_steps_fast", [])) or None),
    ]
    return [(k, str(v)) for k, v in rows if v]


def environment_line(session: dict) -> str:
    dev, app = session.get("device") or {}, session.get("app") or {}
    return (f"{dev.get('model', '?')}, Android {dev.get('android', '?')} (API {dev.get('sdk', '?')}), "
            f"{'emulator' if dev.get('emulator') else 'physical device'}, {dev.get('navigation', '?')} navigation, "
            f"keyboard {keyboard_name(dev.get('keyboard', ''))}, locale {dev.get('locale', '?')}; "
            f"app {app.get('package', '?')} {app.get('versionName', '')} ({app.get('versionCode', '')}); "
            f"input: {session.get('input', 'adb')}")


def history_sentence(h: dict) -> str:
    """'Manual check: reproduced 2/2 by Ihor, on Pixel 7a with build 1.0 (10). Status: Unconfirmed to Confirmed.'"""
    what = {"manual-check": f"Manual check: {h.get('result', '').replace('-', ' ')} {h.get('tries', '')}".rstrip(),
            "retest": f"Retest: {h.get('result', '')}"}.get(h["action"], h["action"].replace("-", " ").capitalize())
    parts = [what + (f" by {h['by']}" if h.get("by") else "")]
    where = " with build ".join(v for v in (h.get("device"), h.get("build")) if v)
    if where:
        parts[0] += f", on {where}" if h.get("device") else f", build {where}"
    if h.get("status"):
        parts.append(f"Status: {h['status'].replace('->', 'to')}")
    if h.get("note"):
        parts.append(h["note"].rstrip("."))
    return ". ".join(parts) + "."


def performance_rows(performance: dict) -> list[tuple[str, str]]:
    rows = []
    if s := performance.get("startup"):
        samples = s.get("samples_ms", [])
        rows.append(("Cold start", f"{s['cold_start_ms']} ms (median of {len(samples)} launches: "
                                   f"{', '.join(map(str, samples))} ms)"))
    if fr := performance.get("frames"):
        parts = []
        if "janky_pct" in fr:
            parts.append(f"{fr['janky_pct']}% janky ({fr.get('janky')} of {fr.get('frames')} frames)")
        pcts = [f"p{p} {fr[f'p{p}_ms']} ms" for p in (50, 90, 99) if f"p{p}_ms" in fr]
        if pcts:
            parts.append("frame time " + ", ".join(pcts))
        rows.append(("Rendering", "; ".join(parts)))
    if m := performance.get("memory"):
        mem = f"{round(m['pss_kb'] / 1024)} MB PSS" if "pss_kb" in m else ""
        if "rss_kb" in m:
            mem += f", {round(m['rss_kb'] / 1024)} MB RSS"
        rows.append(("Memory", mem))
    if trend := [s for s in performance.get("memory_trend", []) if "pss_kb" in s]:
        pss = [s["pss_kb"] for s in trend]
        text = (f"{_mb(pss[0])} to {_mb(pss[-1])} PSS over {len(pss)} samples, peak {_mb(max(pss))}")
        if activities := [s["activities"] for s in trend if "activities" in s]:
            text += f"; live Activities {min(activities)} to {max(activities)}"
        rows.append(("Memory during the session", text))
    for flow, leak in (performance.get("leaks") or {}).items():
        growing = "; ".join(f"{_OBJECT_NAMES.get(k, k)} " + " > ".join(_mb(v) if k == "pss_kb" else str(v)
                                                                       for v in values)
                            for k, values in leak.get("growing", {}).items())
        rows.append((f"Leak check: {flow}", f"{leak['verdict'].capitalize()} after {leak['cycles']} cycles"
                                            + (f" ({growing})" if growing else "")))
    return [(k, v) for k, v in rows if v]


_OBJECT_NAMES = {"activities": "Activities", "view_roots": "windows", "app_contexts": "app contexts",
                 "views": "Views", "webviews": "WebViews", "pss_kb": "PSS"}


def _mb(kb: int) -> str:
    return f"{round(kb / 1024)} MB"


def _ticket_key(session: dict) -> str:
    ticket = session.get("ticket")
    return (ticket.get("key") if isinstance(ticket, dict) else ticket) or ""


# --- Markdown --------------------------------------------------------------------------------

def render_markdown(session: dict, f: dict, with_title: bool = True) -> str:
    """The bug as Markdown. With with_title=False it's the Jira description: the title goes into Summary."""
    lines = [f"# [{f['id']}] {f['title']}", ""] if with_title else []
    head = [f"**Type:** {f['type']}", f"**Status:** {f['status']}"]
    if f.get("severity"):
        head.append(f"**Severity:** {f['severity']}")
    if f.get("priority"):
        head.append(f"**Priority (suggested):** {f['priority']}")
    lines += [" | ".join(head), "", f"**Environment:** {environment_line(session)}", ""]
    if f.get("area"):
        lines += [f"**Area:** {f['area']}", ""]
    if f.get("preconditions"):
        lines += ["**Preconditions:**", *[f"- {p}" for p in f["preconditions"]], ""]
    if f.get("steps"):
        lines += ["**Steps to reproduce:**", *[f"{i}. {s}" for i, s in enumerate(f["steps"], 1)], ""]
    if f.get("expected"):
        lines += [f"**Expected result:** {f['expected']}", ""]
    if f.get("actual"):
        lines += [f"**Actual result:** {f['actual']}", ""]
    if repro(f):
        lines += [f"**Reproducibility:** {repro(f)}", ""]
    if f.get("evidence"):
        lines += ["**Evidence (attach these files):**",
                  *[f"- {ev.get('caption') or ev['type']}: `{ev['path']}`" for ev in f["evidence"]], ""]
    if f.get("notes"):
        lines += [f"**Notes:** {f['notes']}", ""]
    if f.get("history"):
        lines += ["**History:**", *[f"- {h['time'][:16].replace('T', ' ')} {history_sentence(h)}"
                                     for h in f["history"]], ""]
    if f.get("known_issue"):
        lines += [f"**Known issue:** {f['known_issue']}" + ("" if f.get("new_issue") else " (seen again)"), ""]
    if key := _ticket_key(session):
        lines += [f"**Found while testing:** {key}", ""]
    return "\n".join(lines).rstrip() + "\n"


# --- Jira wiki markup (Jira Server / Data Center editors, and the CSV import) ----------------

def _wiki_escape(text: str) -> str:
    # Characters that start wiki markup when they open a line or wrap a word.
    return str(text).replace("{", "\\{").replace("}", "\\}").replace("[", "\\[").replace("]", "\\]")


def render_jira_wiki(session: dict, f: dict) -> str:
    """The Jira description in wiki markup (no title: that's the Summary field)."""
    e = _wiki_escape
    meta = [f"*Type:* {f['type']}", f"*Status:* {f['status']}"]
    if f.get("severity"):
        meta.append(f"*Severity:* {f['severity']}")
    if f.get("priority"):
        meta.append(f"*Priority (suggested):* {f['priority']}")
    lines = [" | ".join(meta), "", f"*Environment:* {e(environment_line(session))}", ""]
    if f.get("area"):
        lines += [f"*Area:* {e(f['area'])}", ""]
    if f.get("preconditions"):
        lines += ["*Preconditions:*", *[f"* {e(p)}" for p in f["preconditions"]], ""]
    if f.get("steps"):
        lines += ["*Steps to reproduce:*", *[f"# {e(s)}" for s in f["steps"]], ""]
    if f.get("expected"):
        lines += [f"*Expected result:* {e(f['expected'])}", ""]
    if f.get("actual"):
        lines += [f"*Actual result:* {e(f['actual'])}", ""]
    if repro(f):
        lines += [f"*Reproducibility:* {repro(f)}", ""]
    if f.get("evidence"):
        lines += ["*Evidence (attach these files):*",
                  *[f"* {e(ev.get('caption') or ev['type'])}: {{{{{ev['path']}}}}}" for ev in f["evidence"]], ""]
    if f.get("notes"):
        lines += [f"*Notes:* {e(f['notes'])}", ""]
    if f.get("history"):
        lines += ["*History:*", *[f"* {h['time'][:16].replace('T', ' ')} {e(history_sentence(h))}"
                                   for h in f["history"]], ""]
    if f.get("known_issue"):
        lines += [f"*Known issue:* {f['known_issue']}" + ("" if f.get("new_issue") else " (seen again)"), ""]
    if key := _ticket_key(session):
        lines += [f"*Found while testing:* {key}", ""]
    return "\n".join(lines).rstrip() + "\n"


# --- CSV for Jira's bulk import --------------------------------------------------------------

def render_jira_csv(session: dict, findings: list[dict]) -> str:
    """One row per fileable finding, with columns Jira's CSV importer maps directly.

    Several 'Labels' columns are Jira's way of importing multiple labels.
    """
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["Summary", "Description", "Issue Type", "Priority", "Labels", "Labels", "Labels"])
    for f in findings:
        if not fileable(f):
            continue
        labels = ["android-tester", f"severity-{(f.get('severity') or 'none').lower()}", f"type-{f['type']}"]
        if outside(f):
            labels[2] += "-outside-scope"
        writer.writerow([f"[{f['id']}] {f['title']}", render_jira_wiki(session, f), "Bug",
                         JIRA_PRIORITIES.get(f.get("priority", ""), ""), *labels])
    return out.getvalue()
