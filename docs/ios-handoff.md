# iOS version: handoff

A brief for starting the iOS version of android-tester on a Mac.
Written on 2026-10-24 at the end of the Android work on Windows; read it first, then `README.md`, `docs/spec.md` and the skills.

**Status, 2026-10-24 (first Mac session):** done on branch `mobile-tester`.
The open decisions below were taken: one plugin `mobile-tester`, a shared `core` package, our own XCUITest runner, simulators first.
See [the design](superpowers/specs/2026-10-24-mobile-tester-design.md) and the iOS section of [spec.md](spec.md); file paths in the tables below are from before the split (now `scripts/mobiletester/core/`, `android/`, `ios/`, and `skills/mobile-tester-shared/`).

## Goal

The same thing android-tester does for Android, for iOS apps on simulators and real iPhones:
an agent tests an app like a person (human-like input, checks after every step), records evidence, and ends with the standard report and Jira-ready drafts.
Everything stays app-independent: what an app is supposed to do comes from the profile's `about` block and the ticket, never from assumptions in the skills.

## What exists (Android, all on `main`)

- Three skills in the open Agent Skills format, usable in Claude Code (plugin) and in Codex, OpenCode, pi and others (`~/.agents/skills/`):
  - `android-native-tester`: onboarding, session interview, six modes (explore, test-case, repro, ui-review, retest, memory), start-state reset, wrap-up, standard report.
  - `android-human-input`: the rules for acting like a person and for honest reproduction.
  - `android-device`: the `adt` command reference.
- `adt`, a Python CLI in `scripts/adtlib/`, run by the plugin through `uv run --script scripts/adt.py` or installed with `uv tool install`.
- 140 tests: `uv run --group dev pytest -q`; lint: `uvx ruff check scripts tests`.

## What carries over unchanged

These modules and files know nothing about Android and should be shared, not copied:

| Part | Files |
|---|---|
| Report: validation, HTML pages, Markdown, Jira wiki, CSV | `report.py`, `report_html.py`, `report_text.py`, `skills/android-native-tester/report-standard.md` |
| Finding lifecycle: manual confirmation, known-issues registry, regression test drafts | `lifecycle.py` |
| Sessions, action log, project config, run folders | `session.py`, `project.py`, `state.py` |
| Guardrails on risky controls (payments, messages, account changes) | `guard.py` (works on element text) |
| Screen change detection from screenshots | `screen.py` (only the screenshot source is platform-specific) |
| Skill content: onboarding, interview, modes, auto mode, profile and config templates | most of `skills/android-native-tester/`, reworded where it names Android tools |

## What has to be rebuilt for iOS

Each of these needs a check of current tools on the Mac before choosing; nothing here was tried on iOS yet.

| Android today | iOS candidates to evaluate |
|---|---|
| `adb.py`: device discovery and commands | `xcrun simctl` (simulators), `xcrun devicectl` (real devices) |
| `hierarchy.py`: uiautomator XML dump | XCUITest accessibility tree, e.g. through WebDriverAgent or an XCUITest runner |
| `device.py` + `human.py`: taps as held presses, swipes, edge-swipe back, home | XCUITest gestures with press duration; iOS has no system back: back is the app's own button or the left-edge swipe |
| `keyboard.py`: typing on Gboard key by key | the iOS keyboard via XCUITest key taps; check how the keyboard is exposed |
| `capture.py`: logcat stream, chunked screenrecord | `log stream` / `xcrun simctl spawn <device> log stream`, `simctl io recordVideo`; for devices check what `devicectl` offers |
| crash watch (logcat crash buffer) | crash reports (`.ips`) from the simulator or the device |
| `applog.py`: the app's own log lines | unified logging filtered by the app's process or subsystem |
| `perf.py`: cold start, frames, `dumpsys meminfo` objects | launch timing via `simctl launch`, `xcrun xctrace` (Time Profiler, Allocations, Leaks), the `leaks` tool on simulators |
| `apkinfo.py`, `apps.py`: APK inspection, app lookup by name | `.ipa`/`.app` inspection (Info.plist, entitlements, code signature), installed apps via `simctl listapps` |
| `adt app reset`: force-stop, `pm clear` | `simctl terminate`, uninstall and reinstall or erase the simulator; on devices check what is possible |
| "Show taps" setting | the simulator has no tap markers by default; check options |

## Open decisions (for the first Mac session)

1. One plugin with a per-platform device tool, or a separate `ios-tester` plugin that reuses the shared report and lifecycle.
   Leaning: one plugin (`android-tester` renamed to something like `mobile-tester`), a shared core package, and `adt` plus an iOS tool (e.g. `idt`) with the same command names.
2. How to share the core: a common Python package used by both tools, or moving the platform-neutral modules into `core/`.
3. Simulator first, real devices second: simulators cover most of it without signing; real devices need a signed test runner.
4. How human-like input is achieved on iOS: what press durations and finger positions XCUITest allows, and how a swallowed tap is detected.

## Rules learned on Android (keep them)

- Input must look like a person's: held presses at a random uncovered point near the center, think time, waiting for the screen to settle, checking that something changed.
- A bug reproduced only by automation is Unconfirmed until a person reproduces it; Major and up can't be Confirmed by automation alone.
- Reading the accessibility tree can change app behaviour; repro runs verify with plain screenshots.
- Check the raw source (hierarchy, log) before reporting a finding; retract instead of deleting.
- Reset to a known start state before every compared run (`reset.strategy` in the app profile).
- Guardrails are never automatic: payments, messages, account changes, accepting terms, system settings on a personal device.
- Settings, reports folder and tester come from `.android-tester/config.yaml`; a test request loads the tester skill, whichever skill or wording started it.

## Still open from the Android work

- Not yet verified on a device: the report redesign, `adt app reset`, session-start defaults, and the log and memory checks.
- Test-case documentation of the plugin's own steps in `docs/testcases/`, grouped by functionality.
- Planned in `docs/spec.md`: an exploration coverage map from screen fingerprints, a selector cache for test cases, a monkey/stress mode.

## Setting up the Mac

1. Clone the repo; install uv; run the tests.
2. Copy the global instructions (`~/.claude/CLAUDE.md` from the Windows machine) so the same working rules apply.
3. Install Xcode and its command line tools; boot a simulator (`xcrun simctl list devices`).
4. Start a session in the repo and point it at this file.
