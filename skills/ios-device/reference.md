# idt command reference

`idt` is the mobile-tester iOS command line: the `idt` command when it is installed (`uv tool install`, see the README), otherwise, in the Claude Code plugin, `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/idt.py"`.

Global options (before or after the command):

| Option | Meaning |
|---|---|
| `-s UDID` | simulator UDID or name (otherwise `IDT_UDID`, otherwise the only booted simulator) |
| `--fast` | no pacing or checks (presses still last 50 ms). Setup and reset steps only |
| `--pace human\|slow` | human (default) or slow pacing; also `MT_PACE` |
| `--no-verify` | skip the did-the-screen-change check (also skips waiting for the screen to settle) |

## Setup

| Command | Purpose |
|---|---|
| `doctor` | Xcode, ffmpeg, uv, whether the runner is built, booted simulators and their runner |
| `devices [--json]` | UDID, state, name, iOS version of every available simulator |
| `info [--json]` | model, iOS version, screen in points and scale, navigation, keyboard language, locale, languages |
| `runner build` / `start` / `stop` / `status` | the XCUITest runner: built once per Xcode version into `~/Library/Caches/mobile-tester`, started on demand by any UI command, one port per simulator |

## Observing

`observe [--app BUNDLE] [--name STEM] [--save-dir DIR] [--no-image] [--no-marks] [--image-only] [--json]`

- Which app: `--app`, else the session's app, else the app `idt app launch`/`reset` last started. When it isn't in the foreground, the list is SpringBoard's (home screen, system alerts), with a note.
- `--name` saves screenshot, preview and the raw tree (`STEM.json`) into the active session's `screenshots/`.
- `--image-only` takes only a screenshot, without reading the tree (use in repro runs).

Element line format:

```
[1] Button "Add" #plus @(374,79) 23x22 [click]
```

- Type: the XCUITest element type (`Button`, `Cell`, `TextField`, `StaticText`, `Image`, `Switch`, `CollectionView`, ...).
- `"..."` label: the accessibility label; text fields show their placeholder (never what was typed); cells and buttons without a label show their texts joined by ` | `.
- `#id` accessibility identifier, `@(x,y)` center in points, `WxH` size in points.
- Flags: `click checked/unchecked scroll edit password selected disabled RISK:<category>`.
- Navigation bars, tab bars and toolbars count as drawn above the content scrolling under them.
- System alerts (SpringBoard) are listed after the app's elements and are on top.
- The keyboard is not in the list: `observe` prints its area, and taps on elements behind it are refused.

State files per simulator under `MT_HOME` (default `.mobile-tester/state/<udid>/` in the project): `latest.json`, `latest_tree.json`, `latest.png`, `latest_preview.jpg`, `facts.json`, `runner.json`, `runner.log`.

## Acting (human mode by default)

Every action: think pause (0.4-1.4 s), the action, a 0.3 s reaction pause, then wait until the screen is stable and compare it with the screen before.
"no visible change" in the output means the action may not have landed.
During a session, every action also looks for a new crash report of the app; "CRASH right after this action" summarises it.
Taps on an element go to a random point near its center that no other control covers; a fully covered element is refused (exit 4).

| Command | Notes |
|---|---|
| `tap --index N` | element from the last observe |
| `tap --text "Label" [--scroll [MAX]]` | ranking as in adt: exact own text > exact part of a merged label > starts with it > word start > substring; controls win ties |
| `tap --id ID [--scroll [MAX]]` | accessibility identifier |
| `tap --xy X Y` / `tap --preview-xy X Y` | screen points / preview pixels; the guard checks the topmost element under the point |
| `tap ... --long` | long press, 0.7-1.0 s |
| `tap ... --allow-risk "APPROVAL"` | only after explicit user approval; logged to `guard_log.jsonl` |
| `type "TEXT" [--index N] [--submit]` | taps the field first with `--index`, then presses each key on the on-screen keyboard, switching shift and the number and symbol layers; `--submit` presses return; exit 6 when a character is on no key, or no keyboard is shown |
| `key back` | left-edge swipe to 75-88% of the width; prints a note when the screen didn't change |
| `key home` | the home button |
| `key enter\|delete\|space [--repeat N]` | the keyboard's return, delete or space key |
| `scroll up/down/left/right [--index N]` | direction the content moves into view; default area is the largest scrollable |
| `swipe X1 Y1 X2 Y2 [--ms N]` | screen points; endpoints wobble slightly in human mode |
| `wait --text T / --id ID [--gone] [--timeout 10]` | polls the tree |

## Apps (setup operations)

| Command | Notes |
|---|---|
| `app find QUERY [--limit 8] [--json]` | by name ("Reminders") or bundle id, built-in apps included; `match:` for one sure hit, otherwise numbered candidates |
| `app list [FILTER] [--all]` | installed apps; built-in ones only with `--all` |
| `app current` | the app idt works with and its state (foreground, background, not running) |
| `app info BUNDLE` | name, versionName (marketing version), versionCode (build), executable, minimum iOS |
| `app launch BUNDLE` | through simctl (not an icon tap); remembered as the app to observe |
| `app stop BUNDLE` | terminate |
| `app reset BUNDLE [--level restart\|clear-data]` | known start state: terminate, reinstall (`clear-data`: the `.app` idt installed last), launch, wait until the screen settles; adds itself to the session's `setup_steps_fast`. Says so when the app isn't in front afterwards (a system alert) |
| `app install PATH.app` | a simulator build; `.ipa` files are refused (device builds) |
| `app uninstall BUNDLE` | |

## Sessions and evidence

| Command | Notes |
|---|---|
| `session start [--dir RUN] [--package BUNDLE] [--mode explore\|test-case\|repro\|ui-review\|retest] [--charter C] [--ticket T] [--record] [--log]` | creates `screenshots/ videos/ logs/ bugs/`, `session.json` (platform, device, app), `findings.json`; actions log to `logs/actions.jsonl`. Without `--dir`: `<reports dir from .mobile-tester/config.yaml>/<date>-<app>-<mode>[-<ticket>]` |
| `session end [--discard-video] [--no-report]` | stops the recording and the app log, then builds the report when `report check` passes |
| `session status` | active run folder |
| `record start --out FILE.mp4` / `record stop [--discard]` | `simctl io recordVideo`; writes `FILE.timeline.json` with the wall-clock start |
| `clip --from T --to T --out FILE [--video V] [--pad 3]` | T = `t` from actions.jsonl, `HH:MM:SS` today, or epoch; default video is the session's |
| `log start --out FILE (--package BUNDLE \| --process NAME)` / `log stop` | the app's unified log, streamed in the background |
| `crashes [--package BUNDLE] [--since EPOCH]` | the app's crash reports (`~/Library/Logs/DiagnosticReports/<executable>-*.ips`) since the session started, with exception and top frames |
| `hook NAME --package P [-- ARGS]` | runs `.mobile-tester/apps/P/hooks/NAME.(py\|sh)` |
| `check NAME --package P [-- ARGS]` | runs `.mobile-tester/apps/P/checks/NAME.(py\|sh)` |
| `report check RUN` / `report build RUN` / `report confirm ...` | as in adt: the same report on both platforms |
| `issues list\|sync\|set ...` | as in adt: the app's known issues in `.mobile-tester/apps/P/known-issues.json` |

Hook and check scripts receive `IDT_UDID`, `IDT` (command line for idt), `MT_PLATFORM` (`iOS`), `MT_PYTHON` and `MT_SCRIPT` (to call idt from Python), `MT_PACKAGE`, `MT_APP_DIR`, `MT_RUN_DIR`, and `MT_SECRETS` when `secrets.local.yaml` exists.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 2 | bad input or report problems |
| 3 | simulator, Xcode or runner problem |
| 4 | element not found, ambiguous, covered, or wait timed out |
| 5 | blocked by a guardrail: ask the user |
| 6 | decision needed: ask the user |
