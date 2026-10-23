# Report standard

Every session produces one run folder.
`adt report check RUN` enforces the rules marked *(checked)*; `adt report build RUN` renders `index.html` and `bugs/<id>.md`.
The renderer lives in `scripts/adtlib/report.py`; keep this file and it in sync.

```
RUN/
  session.json      session facts (adt session start writes the device and app parts)
  findings.json     {"findings": [...]}
  index.html        rendered report
  bugs/<id>.md      one Jira-ready file per bug and accessibility finding
  screenshots/  videos/  logs/ (actions.jsonl, logcat.txt, decisions.md)
```

## session.json

| Field | Content |
|---|---|
| `title` *(checked)* | "<App name> Android - <mode>", e.g. "<App name> Android - exploratory test" |
| `subtitle` | version, device, date and duration in one line |
| `mode` *(checked)*, `charter` *(checked)* | from the interview |
| `ticket` | `{"key", "url", "summary"}` or a string |
| `tester` | from the config |
| `started`, `ended`, `time_box_min` | `adt session start/end` write the times |
| `device` *(checked)* | written by `adt session start` (model, Android, navigation, keyboard, locale, ...) |
| `app` *(checked)* | `package`, `versionName`, `versionCode`, plus `install_source` ("Play Store", "file Foo.xapk, signer verified") |
| `input` | how input was driven; `adt session start` writes "adt human mode" |
| `setup_steps_fast` | steps run with `--fast`, e.g. `["install", "clear data"]` |
| `summary` | 3-5 sentences: overall state, the most serious problems, what needs attention |
| `test_results` | test-case mode: `[{"case", "step", "result": pass/fail/blocked/skipped, "finding", "note"}]`; fail/blocked need a finding or note *(checked)* |
| `worked_well`, `coverage`, `not_covered` | lists of short sentences; `not_covered` is required reading for the reader, always fill it |
| `evidence` | `{"session_video": "videos/session.mp4", "logcat": "logs/logcat.txt", "action_log": "logs/actions.jsonl"}` |

## findings.json

```json
{"findings": [{
  "id": "B1",
  "title": "<Screen> stays blank after closing the sign-in page",
  "type": "bug",
  "status": "Confirmed",
  "severity": "Major",
  "priority": "P2",
  "area": "<Screen> / sign-in",
  "preconditions": ["Not signed in", "Chrome installed and set up"],
  "steps": ["Open \"<screen>\"", "Tap \"<control that needs sign-in>\"", "Close the sign-in page with X",
            "Go back to \"<screen>\""],
  "expected": "<Screen> shows its content again.",
  "actual": "Only the header and tab bar are shown; switching tabs doesn't help; restarting the app does.",
  "reproducibility": {"automated": "2/2", "manual": "1/1"},
  "evidence": [
    {"type": "screenshot", "path": "screenshots/b1-blank.png", "caption": "Blank Start tab"},
    {"type": "video", "path": "videos/b1.mp4", "caption": "Reproduction"}
  ],
  "notes": "",
  "jira": {"key": "", "url": ""}
}]}
```

| Field | Rule |
|---|---|
| `id` *(checked, unique)* | B1.. bugs, A1.. accessibility, O1.. observations, in the order found |
| `type` *(checked)* | `bug`, `accessibility`, `observation` |
| `status` *(checked)* | `Confirmed`, `Unconfirmed` (reproduced only by automation, or not reproducible on demand), `Retracted` (turned out wrong; `notes` says why *(checked)*) |
| `severity` *(checked for bug and accessibility)* | scale below |
| `priority` *(checked for bug)* | suggestion only, P1-P4; the team decides |
| `steps`, `expected`, `actual` *(checked for bug)* | `expected` and `actual` also for accessibility; observations need `actual` |
| `reproducibility` *(checked for bug)* | `automated` and/or `manual` as "N/M" or "not tried"; Unconfirmed must state `manual` *(checked)*; a Blocker/Critical/Major confirmed only by automation is rejected *(checked)* |
| `evidence` *(checked: files exist)* | `screenshot`, `video`, `log`, `xml`, `other`, paths relative to RUN |

## Severity

| Severity | Use when |
|---|---|
| Blocker | The app or a core journey can't be used at all: crash on launch, data loss, payment or privacy breach, testing can't continue. |
| Critical | One of the app's main flows (from the app profile's `about.main_flows`) is broken with no workaround, data is wrong in a way users rely on, or the app crashes in a main flow. |
| Major | An important function is broken or misleading but has a workaround (restart, other path); a screen reader user can't complete a flow. |
| Minor | Limited impact or easy workaround: layout overlaps, localisation errors, small accessibility issues such as undersized targets. |
| Trivial | Cosmetic: typos, alignment, colour nits. |

Priority suggestion: P1 fix before release, P2 next release, P3 planned, P4 backlog.
Base it on severity and how many users hit it (main journey vs. rare edge case).

## Writing findings

- Title: what goes wrong, where, and when, in one sentence. Not "X doesn't work". Example: "Entering 999 in a number field leaves it stuck at 0 with no message".
- Steps start from the preconditions, one action per step, exact labels in quotes, test data spelled out.
- Expected and actual are observable facts, not opinions.
- Reproducibility always says how it was driven: automated (adt human mode) and/or manual (a person).
- Evidence: the screenshot at the moment it goes wrong, the clip from the action log, and the log lines for crashes.
- Retract instead of deleting: a reader should see what was checked and why it was dropped.
- Never put credentials, personal data or tokens into findings; crop or mention it instead.
