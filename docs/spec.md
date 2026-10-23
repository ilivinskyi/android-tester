# Android Tester Skills - Spec

Decisions from the initial interview (2026-10-23), revised after the Jumbo session and the B8 investigation the same day.

## Scope

- Target: any APK / store app, black-box (no source access assumed).
- Devices: physical phones over USB and emulators.
- Packaging: Claude Code plugin `android-tester` (this repo).

## Skills

| Skill | Invoked | Purpose |
|---|---|---|
| `android-native-tester` | `/android-native-tester`, or any request to test an app | Onboarding (first launch), per-session interview, runs a session in one of six modes, writes the standard report. Other skills hand test requests to it, so the project config always applies. |
| `android-human-input` | Automatically whenever a device is driven | Rules for acting like a person: pacing, press duration, tap position, navigation, typing, evidence hygiene. Also the default instruction inside `android-native-tester`. |
| `android-device` | Automatically | Reference for the `adt` CLI. |

Modes of `android-native-tester` (guides in its folder, not separate skills): explore, test case, bug repro, UI review, retest, memory.

## Human-like input (default)

- `adt` acts like a person unless `--fast` is passed.
- `--fast` is allowed only for setup and reset steps (install, clear data, reaching the start state); the action log marks every fast step.
- Taps are presses of 60-150 ms at a random uncovered point inside the element, biased to its center.
- Think time of 0.4-1.4 s before each action; after an action, wait until the screen is stable instead of a fixed sleep.
- After each tap, compare the screen with the one before it and warn when nothing visibly changed.
- Back and Home follow the device's navigation mode: edge swipe / swipe up in gesture mode, the navigation-bar keys in 3-button mode.
- Typing goes through the on-screen keyboard: keys are located in the keyboard window (`uiautomator dump --windows`), including layer switches for digits and symbols.
  When a character can't be located, the CLI stops and the skill asks the user (or applies the auto-mode default: per-character key events, noted in the report).
- Every action is appended to the run's `logs/actions.jsonl` with wall time and mode.
- Screen recordings store the wall-clock start of every 3-minute chunk, so bug clips are cut at exact times.

## Reproduction discipline

- A bug reproduced only through automation is **Unconfirmed** until a person reproduces it by hand.
  The skill then offers a manual attempt: it sets up the start state, records, and compares the person's run with the automated one.
- Reproducibility is reported as N of M, separately for automated and manual runs.
- Change one variable at a time when narrowing a trigger.
- Preconditions and test-data state are part of every bug.
- Every compared run starts from the same state: the session, each reproduction attempt, each test case and each retested issue begin with a reset (`adt app reset --level restart|clear-data`, or the app's reset hook), as the profile's `reset.strategy` says.
  Clearing data on a personal device needs the user's yes, once per session.
- Repro runs keep UI-hierarchy dumps to a minimum (they turn on the accessibility layer) and verify with plain screenshots.
- Before reporting a finding, check the raw source (hierarchy XML, logcat) that proves it.

## Onboarding and configuration

- Onboarding runs on the first `/android-native-tester` in a project, and again when asked.
- Covers: tester and team defaults, device inventory, app profiles, auto mode.
- Each app profile has an `about` block written from the user's own description: purpose, users, main flows, rules, roles, integrations, out-of-scope areas, glossary.
  Expected behaviour, test ideas and severity come from it and the ticket; the skills carry no assumptions about any app domain.
- Auto mode: one list of every decision the skill would otherwise ask about, each with a default the user confirms or changes.
  Guardrails (payments, messages, account changes, accepting terms, system settings on a personal phone) are never automatic.
- Per-session interview at every run: ticket and context, mode, device, build installed or to install, start state, focus, time budget.
  In auto mode it only asks what has no default.
- Files: `.android-tester/config.yaml` (team defaults, devices, auto mode), `.android-tester/apps/<package>/profile.yaml`, `notes.md`, `hooks/`, `checks/`, and gitignored `secrets.local.yaml`.
- App scripts: lifecycle hooks (setup, reset, teardown), login helper, custom checks, app knowledge notes.

## Jira

- Tickets can be pasted (key, URL, description) or read through the Atlassian connector when it is authorized.
- Findings are drafted as Jira-ready Markdown; nothing is created in Jira without the user's explicit approval.

## Report standard

- Every session writes one run folder: `session.json`, `findings.json`, `index.html`, `bugs/<id>.html`, `bugs/<id>.md`, `findings.csv`, `screenshots/`, `videos/`, `logs/`.
- `adt report build` renders the finding list (findings grouped by severity in compact rows with priority, status and a two-line summary; search with `/`, filters by type, severity and status kept in the URL, `j`/`k` keyboard navigation), one page per finding (Copy for Jira, Copy title and Copy wiki markup at the top; phone-framed evidence; a viewer for screenshots and videos with close button, Esc, click outside, arrows, swipe, zoom, caption and original; Previous/Next following the filtered list), per-bug Markdown and a CSV for Jira's bulk import; `adt report check` validates required fields and file links.
- Problems noticed outside the charter are findings with `scope: outside`: their own section, not counted. Per app, `outside_scope.report` switches them off and `outside_scope.not_ready` lists unfinished areas that are never reported.
- Bug lifecycle: found, confirmed by a person (`adt report confirm`, kept in the finding's `history`), registered as a known issue per app with a regression test case draft (`adt issues sync`), retested on new builds (`retest` mode), marked fixed (`adt issues set`), reopened automatically when seen again.
- Crash watch: the crash buffer is read after every action; a crash is reported at the step that caused it.
- App log watch: after every action the new lines of the session's logcat stream are read and the app's own errors, caught exceptions, network failures, StrictMode violations, long frame drops and out-of-memory lines are shown and logged; `adt logcat summary` groups them for the report. They aren't findings automatically: many apps log harmless errors.
- Memory: a sample every 10 actions (trend in the report), and a memory mode that repeats flows and compares live Activities, Views and PSS per cycle to find leaks.
- Performance per session: median cold start, janky frames and frame-time percentiles, memory (PSS/RSS), shown in the report.
- Apps are chosen by name or package: `adt app find` reads launcher labels from each APK on the device (manifest and resources.arsc only) and lists candidates when several match.
- Finding fields: id, title, type (bug, accessibility, observation), severity (Blocker, Critical, Major, Minor, Trivial), suggested priority (P1-P4), status (Confirmed, Unconfirmed, Retracted), environment, preconditions, steps, expected, actual, reproducibility (automated and manual N of M), evidence, notes.
- Session fields: charter, mode, ticket, tester, device and app facts (including navigation mode, keyboard, install source, input method), time box, coverage, not covered, setup steps run with `--fast`.

## Evidence

- Screen recording during the session; a clip per bug cut from the action log times.
- Logcat, screenshots and hierarchy dumps per run.
- "Show taps" (touch markers in videos) is a system setting: the skill always asks before turning it on, and turns it off afterwards.

## Exploratory testing

- Bounded by a charter and a time box.
- Screen fingerprints (`fp=` in `observe`) give every screen a stable id that ignores content (list rows, typed text, counts).
- Planned: a coverage map built from them, preferring unvisited screens.
- Optional monkey/stress mode with crash/ANR detection.

## Scripted test cases

- Markdown, plain English (numbered steps + expected results).
- First passing run caches the resolved selector per step; reruns try the cache first.

## UI / accessibility review

- Android accessibility guidelines: 48 dp touch targets, labels, contrast 4.5:1, screen-reader-only text.
- Material 3 visual rules.
- Config stress (font scale, dark mode, RTL, landscape) only on emulators, or on a phone with explicit approval.
- TalkBack flow: focus order and spoken labels.

## Guardrails

- Hard stop before purchases/payments, outgoing messages/posts/reviews, account destruction (delete, logout, password change), and accepting terms.
- The agent asks the user, who may approve case by case.
- No system-setting changes on a personal phone without approval.

## Test data

- Per-app gitignored secrets file when present; otherwise the user logs in on the device.
- Credentials never appear in reports or logs.
