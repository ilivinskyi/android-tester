"""The standard session report: validate session.json + findings.json, render index.html and bugs/<id>.md.

The field definitions live in skills/android-native-tester/report-standard.md; keep both in sync.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

TYPES = ("bug", "accessibility", "observation")
SEVERITIES = ("Blocker", "Critical", "Major", "Minor", "Trivial")
PRIORITIES = ("P1", "P2", "P3", "P4")
STATUSES = ("Confirmed", "Unconfirmed", "Retracted")
EVIDENCE_TYPES = ("screenshot", "video", "log", "xml", "other")
TEST_RESULTS = ("pass", "fail", "blocked", "skipped")
_REQUIRED = {
    "bug": ("severity", "priority", "steps", "expected", "actual", "reproducibility"),
    "accessibility": ("severity", "expected", "actual"),
    "observation": ("actual",),
}


def _load(run: Path) -> tuple[dict, list[dict]]:
    session = json.loads((run / "session.json").read_text(encoding="utf-8"))
    findings = json.loads((run / "findings.json").read_text(encoding="utf-8")).get("findings", [])
    return session, findings


def check(run: Path) -> list[str]:
    """Problems that would make the report incomplete or misleading. Empty list = ok."""
    problems: list[str] = []
    for name in ("session.json", "findings.json"):
        if not (run / name).is_file():
            problems.append(f"{name} is missing in {run}")
    if problems:
        return problems
    session, findings = _load(run)
    for field_name in ("title", "mode", "charter", "device", "app"):
        if not session.get(field_name):
            problems.append(f"session.json: '{field_name}' is empty")
    for i, r in enumerate(session.get("test_results", []), 1):
        if not r.get("case") or r.get("result") not in TEST_RESULTS:
            problems.append(f"session.json test_results[{i}]: needs 'case' and 'result' in {TEST_RESULTS}")
        if r.get("result") in ("fail", "blocked") and not (r.get("finding") or r.get("note")):
            problems.append(f"session.json test_results[{i}]: a {r['result']} step needs 'finding' or 'note'")
    seen: set[str] = set()
    for f in findings:
        fid = f.get("id") or "?"
        where = f"finding {fid}"
        if fid in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(fid)
        for key in ("id", "title", "type", "status"):
            if not f.get(key):
                problems.append(f"{where}: '{key}' is required")
        if f.get("type") not in TYPES:
            problems.append(f"{where}: type must be one of {TYPES}")
            continue
        if f.get("status") not in STATUSES:
            problems.append(f"{where}: status must be one of {STATUSES}")
        if f["status"] == "Retracted":
            if not f.get("notes"):
                problems.append(f"{where}: a retracted finding must say why in 'notes'")
            continue
        for key in _REQUIRED[f["type"]]:
            if not f.get(key):
                problems.append(f"{where}: '{key}' is required for type {f['type']}")
        if f.get("severity") and f["severity"] not in SEVERITIES:
            problems.append(f"{where}: severity must be one of {SEVERITIES}")
        if f.get("priority") and f["priority"] not in PRIORITIES:
            problems.append(f"{where}: priority must be one of {PRIORITIES}")
        repro = f.get("reproducibility") or {}
        if f["type"] == "bug" and not (repro.get("automated") or repro.get("manual")):
            problems.append(f"{where}: reproducibility needs 'automated' and/or 'manual' (e.g. '3/3')")
        if f["status"] == "Unconfirmed" and not repro.get("manual"):
            problems.append(f"{where}: an Unconfirmed finding must state the manual result "
                            "(e.g. '0/2' or 'not tried')")
        if f["type"] == "bug" and f["status"] == "Confirmed" and not repro.get("manual") \
                and f.get("severity") in ("Blocker", "Critical", "Major"):
            problems.append(f"{where}: a {f['severity']} bug confirmed only by automation should be Unconfirmed "
                            "until a person reproduces it")
        for ev in f.get("evidence", []):
            if ev.get("type") not in EVIDENCE_TYPES:
                problems.append(f"{where}: evidence type must be one of {EVIDENCE_TYPES}")
            if not (run / ev.get("path", "")).is_file():
                problems.append(f"{where}: evidence file not found: {ev.get('path')}")
    return problems


# --- rendering -------------------------------------------------------------------------------

_CSS = """
:root{--bg:#f6f6f4;--surface:#fff;--text:#1b1b1b;--muted:#5d5d5d;--border:#e2e2dc;--accent:#2e7d32;
--blocker:#6a1b9a;--critical:#b71c1c;--major:#c62828;--minor:#8d6e00;--trivial:#607d8b;--a11y:#4527a0;
--obs:#455a64;--unconf:#ef6c00;--retr:#757575;--code:#f0efe9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141413;--surface:#1e1e1c;
--text:#ececea;--muted:#a5a5a0;--border:#33332f;--code:#2a2a27;--minor:#c0a000}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1080px;margin:0 auto;padding:32px 16px 64px}h1{margin:0 0 4px;font-size:28px}
h2{margin:40px 0 12px;font-size:20px}.sub{color:var(--muted);margin:0}
.bar{height:6px;width:72px;background:var(--accent);border-radius:3px;margin:0 0 16px}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.stat b{display:block;font-size:26px}.stat span{color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--border);border-radius:10px}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--border);vertical-align:top;
overflow-wrap:anywhere}
th{width:200px;color:var(--muted);font-weight:500}tr:last-child th,tr:last-child td{border-bottom:0}
code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:13px;overflow-wrap:anywhere}
.f{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px 20px;margin:14px 0}
.f h3{margin:0 0 6px;font-size:17px;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.id{color:var(--muted);font-weight:500;font-size:14px}.meta{color:var(--muted);font-size:13px;margin:0 0 10px}
.b{font-size:12px;font-weight:600;padding:2px 8px;border-radius:999px;color:#fff}
.Blocker{background:var(--blocker)}.Critical{background:var(--critical)}.Major{background:var(--major)}
.Minor{background:var(--minor)}.Trivial{background:var(--trivial)}.accessibility{background:var(--a11y)}
.observation{background:var(--obs)}.Unconfirmed{background:var(--unconf)}.Retracted{background:var(--retr)}
.P{background:var(--muted)}.ev{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;align-items:flex-start}
.ev figure{margin:0;width:200px}.ev figure.wide{width:360px;max-width:100%}
.ev img,.ev video{width:100%;border:1px solid var(--border);border-radius:8px;display:block;background:#000}
.ev figcaption{font-size:12px;color:var(--muted);margin-top:4px}.ev a{color:inherit}
footer{margin-top:48px;color:var(--muted);font-size:13px}
@media (max-width:520px){th{width:110px}.ev figure{width:calc(50% - 6px)}}
"""

_ORDER = {s: i for i, s in enumerate(SEVERITIES)}


def _e(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _repro(f: dict) -> str:
    r = f.get("reproducibility") or {}
    parts = [f"automated {r['automated']}" if r.get("automated") else "",
             f"manual {r['manual']}" if r.get("manual") else ""]
    return ", ".join(p for p in parts if p)


def _evidence_html(f: dict) -> str:
    items = []
    for ev in f.get("evidence", []):
        path, cap = _e(ev["path"]), _e(ev.get("caption", ""))
        if ev["type"] == "screenshot":
            items.append(f'<figure><a href="{path}"><img src="{path}" alt="{cap}"></a>'
                         f'<figcaption>{cap}</figcaption></figure>')
        elif ev["type"] == "video":
            items.append(f'<figure class="wide"><video controls preload="metadata" src="{path}"></video>'
                         f'<figcaption><a href="{path}">{cap or "video"}</a></figcaption></figure>')
        else:
            items.append(f'<figure><figcaption><a href="{path}">{cap or path}</a> '
                         f'({_e(ev["type"])})</figcaption></figure>')
    return f'<div class="ev">{"".join(items)}</div>' if items else ""


def _list(items, ordered: bool = False) -> str:
    if not items:
        return ""
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{_e(i)}</li>" for i in items) + f"</{tag}>"


def _finding_html(f: dict) -> str:
    badges = []
    if f.get("severity"):
        badges.append(f'<span class="b {_e(f["severity"])}">{_e(f["severity"])}</span>')
    if f.get("priority"):
        badges.append(f'<span class="b P">{_e(f["priority"])}</span>')
    if f["type"] != "bug":
        badges.append(f'<span class="b {f["type"]}">{_e(f["type"].capitalize())}</span>')
    if f["status"] != "Confirmed":
        badges.append(f'<span class="b {f["status"]}">{_e(f["status"])}</span>')
    meta = [m for m in (_e(f.get("area", "")), f"Reproducibility: {_e(_repro(f))}" if _repro(f) else "") if m]
    jira = f.get("jira") or {}
    if jira.get("key"):
        link = f'<a href="{_e(jira.get("url", ""))}">{_e(jira["key"])}</a>' if jira.get("url") else _e(jira["key"])
        meta.append(f"Jira: {link}")
    body = [f'<p class="meta">{" - ".join(meta)}</p>' if meta else ""]
    if f.get("preconditions"):
        body.append("<p><b>Preconditions</b></p>" + _list(f["preconditions"]))
    if f.get("steps"):
        body.append("<p><b>Steps</b></p>" + _list(f["steps"], ordered=True))
    if f.get("expected"):
        body.append(f"<p><b>Expected:</b> {_e(f['expected'])}</p>")
    if f.get("actual"):
        label = "Actual" if f["type"] != "observation" else "Observation"
        body.append(f"<p><b>{label}:</b> {_e(f['actual'])}</p>")
    if f.get("notes"):
        body.append(f"<p><b>Notes:</b> {_e(f['notes'])}</p>")
    return (f'<section class="f" id="{_e(f["id"])}"><h3><span class="id">{_e(f["id"])}</span> {_e(f["title"])} '
            f'{" ".join(badges)}</h3>{"".join(body)}{_evidence_html(f)}</section>')


_KEYBOARDS = {
    "com.google.android.inputmethod.latin": "Gboard",
    "com.samsung.android.honeyboard": "Samsung Keyboard",
    "com.touchtype.swiftkey": "Microsoft SwiftKey",
}


def _keyboard(ime: str) -> str:
    package = (ime or "?").split("/", 1)[0]
    return _KEYBOARDS.get(package, package)


def _time_range(session: dict) -> str | None:
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


def _session_rows(session: dict) -> str:
    dev, app = session.get("device") or {}, session.get("app") or {}
    ticket = session.get("ticket")
    if isinstance(ticket, dict):
        ticket = " - ".join(str(ticket.get(k)) for k in ("key", "summary") if ticket.get(k))
    rows = [
        ("Charter", session.get("charter")),
        ("Mode", session.get("mode")),
        ("Ticket", ticket),
        ("Tester", session.get("tester")),
        ("Time", _time_range(session)),
        ("App", " ".join(str(app.get(k, "")) for k in ("package", "versionName"))
         + (f" ({app['versionCode']})" if app.get("versionCode") else "")),
        ("Install source", app.get("install_source")),
        ("Device", f"{dev.get('manufacturer', '')} {dev.get('model', '')}, Android {dev.get('android', '')} "
                   f"(API {dev.get('sdk', '')}), {dev.get('screen', '')} at {dev.get('density', '')} dpi"
         if dev else None),
        ("Device kind", "emulator" if dev.get("emulator") else "physical" if dev else None),
        ("Navigation / keyboard",
         f"{dev.get('navigation', '')} / {_keyboard(dev.get('keyboard', ''))}" if dev else None),
        ("Locale", dev.get("locale")),
        ("Input", session.get("input")),
        ("Setup steps run fast", ", ".join(session.get("setup_steps_fast", [])) or None),
    ]
    return "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in rows if v)


def _test_result_row(r: dict) -> str:
    case = _e(r["case"]) + (f" / step {_e(r['step'])}" if r.get("step") else "")
    cell = f"<b>{_e(r['result'].upper())}</b>"
    if r.get("finding"):
        fid = _e(r["finding"])
        cell += f' - <a href="#{fid}">{fid}</a>'
    if r.get("note"):
        cell += f" - {_e(r['note'])}"
    return f"<tr><th>{case}</th><td>{cell}</td></tr>"


def render_html(session: dict, findings: list[dict]) -> str:
    live = [f for f in findings if f["status"] != "Retracted"]
    bugs = sorted((f for f in live if f["type"] == "bug" and f["status"] == "Confirmed"),
                  key=lambda f: _ORDER.get(f.get("severity"), 9))
    unconfirmed = [f for f in live if f["status"] == "Unconfirmed"]
    a11y = [f for f in live if f["type"] == "accessibility" and f["status"] == "Confirmed"]
    obs = [f for f in live if f["type"] == "observation" and f["status"] == "Confirmed"]
    retracted = [f for f in findings if f["status"] == "Retracted"]
    by_sev = ", ".join(f"{sum(1 for b in bugs if b.get('severity') == s)} {s.lower()}"
                       for s in SEVERITIES if any(b.get("severity") == s for b in bugs))
    stats = [(len(bugs), f"confirmed bugs{f' ({by_sev})' if by_sev else ''}"),
             (len(unconfirmed), "unconfirmed (need manual repro)"), (len(a11y), "accessibility issues"),
             (len(obs), "observations")]
    sections = [("Bugs", bugs), ("Unconfirmed: needs manual reproduction", unconfirmed),
                ("Accessibility", a11y), ("Observations", obs), ("Retracted during the session", retracted)]
    parts = [f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
             f'<meta name="viewport" content="width=device-width, initial-scale=1">'
             f'<title>{_e(session.get("title"))}</title><style>{_CSS}</style></head><body><main>',
             f'<header><div class="bar"></div><h1>{_e(session.get("title"))}</h1>'
             f'<p class="sub">{_e(session.get("subtitle", ""))}</p></header>',
             "<h2>Summary</h2><div class=\"grid\">"
             + "".join(f'<div class="stat"><b>{n}</b><span>{_e(label)}</span></div>' for n, label in stats) + "</div>"]
    if session.get("summary"):
        parts.append(f"<p>{_e(session['summary'])}</p>")
    parts.append(f"<h2>Session</h2><table>{_session_rows(session)}</table>")
    if session.get("test_results"):
        rows = "".join(_test_result_row(r) for r in session["test_results"])
        parts.append(f"<h2>Test results</h2><table>{rows}</table>")
    for heading, items in sections:
        if items:
            parts.append(f"<h2>{_e(heading)}</h2>" + "".join(_finding_html(f) for f in items))
    for key, heading in (("worked_well", "Worked well"), ("coverage", "Covered"), ("not_covered", "Not covered")):
        if session.get(key):
            parts.append(f"<h2>{heading}</h2>{_list(session[key])}")
    evidence = session.get("evidence") or {}
    if evidence:
        links = " - ".join(f'<a href="{_e(p)}">{_e(k.replace("_", " "))}</a>' for k, p in evidence.items())
        parts.append(f"<h2>Session evidence</h2><p>{links}</p>")
    parts.append("<footer>Generated by the android-tester plugin from session.json and findings.json. "
                 "Input was driven over adb in human mode unless a step says otherwise.</footer></main></body></html>")
    return "".join(parts)


def render_markdown(session: dict, f: dict) -> str:
    dev, app = session.get("device") or {}, session.get("app") or {}
    env = (f"{dev.get('model', '?')}, Android {dev.get('android', '?')} (API {dev.get('sdk', '?')}), "
           f"{'emulator' if dev.get('emulator') else 'physical device'}, {dev.get('navigation', '?')} navigation, "
           f"keyboard {_keyboard(dev.get('keyboard', ''))}, locale {dev.get('locale', '?')}; "
           f"app {app.get('package', '?')} {app.get('versionName', '')} ({app.get('versionCode', '')}); "
           f"input: {session.get('input', 'adb')}")
    lines = [f"# [{f['id']}] {f['title']}", ""]
    head = [f"**Type:** {f['type']}", f"**Status:** {f['status']}"]
    if f.get("severity"):
        head.append(f"**Severity:** {f['severity']}")
    if f.get("priority"):
        head.append(f"**Priority (suggested):** {f['priority']}")
    lines += [" | ".join(head), "", f"**Environment:** {env}", ""]
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
    if _repro(f):
        lines += [f"**Reproducibility:** {_repro(f)}", ""]
    if f.get("evidence"):
        lines += ["**Evidence (attach these files):**",
                  *[f"- {ev.get('caption') or ev['type']}: `{ev['path']}`" for ev in f["evidence"]], ""]
    if f.get("notes"):
        lines += [f"**Notes:** {f['notes']}", ""]
    ticket = session.get("ticket")
    if ticket:
        key = ticket.get("key") if isinstance(ticket, dict) else ticket
        lines += [f"**Found while testing:** {key}", ""]
    return "\n".join(lines)


def build(run: Path) -> list[Path]:
    session, findings = _load(run)
    written = [run / "index.html"]
    written[0].write_text(render_html(session, findings), encoding="utf-8")
    (run / "bugs").mkdir(exist_ok=True)
    for f in findings:
        if f["status"] == "Retracted" or f["type"] == "observation":
            continue
        path = run / "bugs" / f"{f['id']}.md"
        path.write_text(render_markdown(session, f), encoding="utf-8")
        written.append(path)
    return written
