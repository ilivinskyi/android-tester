# mobile-tester: iOS support and a shared core

Written on 2026-10-24, from the iOS handoff written at the end of the Android work and the first Mac session.

## Intent

android-tester lets an agent test an Android app the way a person would and ends with a standard QA report.
The same is now wanted for iOS, starting with simulators.
Everything that isn't about the device (report, finding lifecycle, sessions, guardrails, screen-change detection, the skill content) must be shared, not copied, so both testers produce the same report and follow the same rules.

## Decisions taken with Ihor

- One plugin and one repo for both platforms: `mobile-tester`.
  Nobody else uses `android-tester` yet, so nothing has to stay backwards compatible (configs, command names, install name).
- Per-platform entry skills: `/android-native-tester` and `/ios-native-tester`, sharing their reference files.
- iOS input goes through our own XCUITest runner (Apple tools only), not WebDriverAgent or idb.
- Simulator first; real iPhones later.
- First iOS target app: Loop Habit Tracker iOS (`aint/habits`, Apache-2.0), built for the simulator from `~/Developer/ios-test-apps/habits`, bundle id `com.github.aint.Habits`.
  The Android original exists too, so the same session can be compared across platforms.
- Work happens on the local branch `mobile-tester`, committed step by step, not pushed; the GitHub repo is not renamed yet.

## Goals

- The report reads the same on both platforms; only the environment block differs, and it is driven by data, not by platform checks in the renderer.
- `adt` keeps working exactly as before on Android (all existing tests green).
- `idt` offers the same command names as `adt` where the concept exists (`doctor`, `devices`, `info`, `observe`, `tap`, `type`, `swipe`, `scroll`, `key`, `wait`, `app`, `session`, `record`, `clip`, `report`, `issues`, `hook`, `check`).
- iOS input follows the same human rules: held presses of 60-150 ms at a random uncovered point near the center, think time, wait for the screen to settle, warn when nothing changed, typing key by key on the on-screen keyboard.
- A full session on Loop Habits ends with a valid report.

## Non-goals (for now)

- Real iPhones (needs a signed runner and a tunnel).
  Added afterwards on this branch through devicectl and CoreDevice's tunnel (see the spec's "iOS (real devices)"), not yet tried on hardware.
- iOS performance (`xctrace`, `leaks`), memory mode and the app-log summary on iOS.
- `.ipa` inspection.
- Renaming the GitHub repository and publishing.

## Anti-goals

- iOS behaviour faked with Android assumptions (system back key, navigation modes, IME packages).
- Typing through `typeText` or pasting while calling it human input.
- A second copy of the report or lifecycle code.

## Layout

One Python package, `mobiletester`, in `scripts/`:

| Part | Content |
|---|---|
| `core/` | report (`report`, `report_html`, `report_text`), `lifecycle`, `session`, `state`, `project`, `guard`, `screen` (screenshot source passed in), `ui` (Bounds, Element, Snapshot, hit testing, human tap points, text search), `annotate`, `fingerprint`, `clip` (wall-clock clip cutting) |
| `android/` | `adb`, `device`, `hierarchy` (uiautomator XML to `core.ui`), `human`, `keyboard`, `capture`, `applog`, `perf`, `apkinfo`, `apps`, `cli` (`adt`) |
| `ios/` | `simctl`, `runner` (HTTP client and process control), `hierarchy` (runner JSON to `core.ui`), `device`, `human`, `keyboard`, `capture` (video, unified log, crash reports), `cli` (`idt`) |

Entry points: `scripts/adt.py` and `scripts/idt.py` (PEP 723, for the plugin), and `adt` / `idt` console scripts in `pyproject.toml` (for `uv tool install`).

## Report: platform-neutral environment

- `session.json` gets `platform` (`Android` or `iOS`); the title becomes "<App> Android - <mode>" or "<App> iOS - <mode>".
- Each platform writes the device block with display-ready neutral keys: `model`, `os` ("Android 15 (API 35)", "iOS 27.0"), `kind` (physical, emulator, simulator), `screen`, `navigation`, `keyboard`, `locale`, plus its own raw facts.
- The renderer shows the neutral keys; for older Android run folders it derives them from the Android keys.
- `app` uses `package` (Android package or iOS bundle id), `versionName`/`versionCode` on Android and the same keys filled from `CFBundleShortVersionString`/`CFBundleVersion` on iOS, so the lifecycle code needs no change.
- `report-standard.md` moves to the shared skill folder.

## Project files

- Config: `.mobile-tester/config.yaml`, app profiles in `.mobile-tester/apps/<package or bundle id>/`.
- Device state (last observation, background pids): `.mobile-tester/state/<device>/`, found like git by walking up; `MT_HOME` overrides.

## Skills

| Skill | Content |
|---|---|
| `mobile-tester-shared` | Not used on its own: onboarding, session interview, modes, auto mode, report standard, templates. |
| `android-native-tester`, `ios-native-tester` | Entry skills: the session flow with the platform's commands, pointing to the shared files. |
| `android-human-input`, `ios-human-input` | The human-input rules per platform. |
| `android-device`, `ios-device` | CLI references for `adt` and `idt`. |

Shared files are referenced as `../mobile-tester-shared/...`; both the plugin and the copy-all-folders install keep the skill folders side by side.

## The iOS runner

- An Xcode project in `ios-runner/` with one UI-testing bundle (`MTRunner`); its single test starts an HTTP server inside the simulator on `127.0.0.1:<port>` (default 22087) and serves until stopped.
- Every XCUITest call runs on the main thread: the server thread queues requests and the test loop executes them.
- Endpoints: status, device info, app tree (the target app plus SpringBoard alerts) as JSON, screenshot, press at a point for a duration, drag with a hold and velocity, home button, app activate/terminate/state.
- `idt runner start` builds it once (`build-for-testing`) and runs it with `test-without-building` in the background; `idt` starts it on demand.

## iOS input details

- Coordinates are in points; screenshots are scaled to points for change detection and previews.
- Tap: `XCUICoordinate.press(forDuration:)` with a human duration at a human point.
- Back: there is no system back; `idt key back` is the left-edge swipe (as a person does it) or tapping the app's back button found in the navigation bar.
- Home: the home gesture is not available through XCUITest on a simulator, so `idt key home` uses the home button press and says so in the action log.
- Typing: keys are read from the keyboard in the app tree and pressed one by one, switching layers (`more`, `shift`) when needed; a character that can't be found stops with a decision, like on Android.

## Left to the builder

- Exact JSON shapes between runner and `idt`.
- Port handling for several simulators.
- How much of the Android CLI code is shared between `adt` and `idt` beyond `core`.
