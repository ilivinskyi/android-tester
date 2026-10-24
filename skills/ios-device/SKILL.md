---
name: ios-device
description: Use when a task needs to look at or operate an iOS simulator - listing simulators, reading the screen, tapping or typing, launching or installing apps, the app's log, crash reports, screenshots or screen recordings, cutting video clips, or running app setup scripts.
---

# iOS device

All simulator work goes through one CLI, `idt`, run in the shell.
- Installed as a command (`uv tool install`, any agent): `idt <command> [options]`.
- In the Claude Code plugin without that install: `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/idt.py" <command> [options]` (Claude Code fills in the path).

Try `idt doctor` first; if the command isn't found, use the plugin form. Below, `idt` stands for whichever works.
Full options for every command: [reference.md](reference.md).
**REQUIRED:** follow the `ios-human-input` skill for every UI action.

**Testing an app is not this skill's job.** When the user wants an app tested (exploring it, test cases, reproducing a bug, a UI review, a retest, or anything that should end in a report), load the `ios-native-tester` skill first and follow it.
It reads the project config (auto mode, reports folder, tester, guardrails) and runs the interview, the session and the report; this skill is the command reference it uses.
Use this skill on its own only for one-off tasks: a screenshot, checking what's installed, a crash report, a quick tap.

## How it works

`idt` drives the simulator through MTRunner, a small XCUITest runner that ships with it.
`idt` builds it once per Xcode version (`idt runner build`, about a minute) and starts it when a command needs it (about 15 s); it then keeps running until the simulator shuts down or `idt runner stop`.
Coordinates are screen points (402x874 on an iPhone 17), not pixels.

## Before anything else

1. Run `idt doctor`. It must show Xcode and a booted simulator.
   - No booted simulator: `idt devices` lists them; boot one with `xcrun simctl boot "iPhone 17"` and `open -a Simulator` to watch it.
   - Xcode missing: ask the user to install it; never install it yourself.
2. With several simulators booted, pass `-s UDID` (or the simulator's name) on every command.
3. Run `idt info` once; it reports model, iOS version, screen, keyboard language and locale for the report.

## The loop: observe, look, act, check

1. `idt observe` reads the app's element tree and takes a screenshot, and prints the screen identity and a numbered element list.
   It reads the session's app, or the app `idt` last launched, or `--app BUNDLE`; when that app isn't in front it shows SpringBoard (home screen, system alerts) and says so.
2. Look at the `preview:` image (open it with your file or image viewing tool). Its numbered boxes match the `[index]` in the list.
3. Act on one element: `idt tap --index N`, `idt type "text" --index N`, `idt scroll down`, `idt key back`.
   Human mode is the default: pacing, press duration, finger position and the back swipe are handled for you.
4. Read the action's output. "no visible change" means it may not have landed: observe before continuing.

Choosing a target, in order of preference:
- `--index N` from the latest observation.
- `--text "Label"` (label, placeholder or value) or `--id identifier` (fresh lookup); add `--scroll` when it may be below the fold.
- `--preview-xy X Y` read off the preview image, only when the element is absent from the tree.

When the keyboard is up, `observe` says so; taps below its top edge would hit keys, so targets behind it are refused (exit 4).
Exit codes: 4 not found or covered, 5 guardrail block, 6 decision needed (e.g. a character no key types).

## Guardrails - never bypass

- Elements marked `RISK:payment`, `RISK:message` or `RISK:account` are refused (exit 5, `BLOCKED`).
- On `BLOCKED`, or whenever you judge a screen to be a purchase, outgoing message/post/review, account deletion/logout/password change, or accepting terms: stop and ask the user.
- Only after explicit approval of that one action, rerun with `--allow-risk "<quote of the user's approval>"`.
- The classifier knows English labels only; judge other languages and unlabelled icons yourself.
- Signing in to an Apple ID on the simulator uses the user's real account: ask first.

## Sessions and evidence

- `idt session start --package BUNDLE --mode MODE --record --log` creates the standard run folder, records the screen, streams the app's log, and logs every action to `RUN/logs/actions.jsonl`.
- `idt observe --name step-03` saves the screenshot, preview and tree JSON into the session; `idt observe --image-only` takes a screenshot without reading the tree.
- `idt clip --from T1 --to T2 --out RUN/videos/bug-1.mp4` cuts a clip using the `t` values from the action log.
- `idt crashes` lists the app's crash reports since the session started; every action also checks for new ones.
- `idt session end` stops the recording and the log, and builds the report.
- `idt report check RUN` and `idt report build RUN` validate and render the standard report.

## Known limits

- Simulators only; real iPhones are not supported yet.
- Each key press takes about half a second (XCUITest waits for the app to go idle), so long texts type slowly.
- Typing knows the keys on the letter, number and symbol layers; accented letters (long press) and other keyboard languages stop with a decision.
- No performance, memory or leak measurements on iOS yet.
- `app launch` starts the app through `simctl`, not by tapping its icon. To reproduce launch-related bugs, tap the icon on the home screen instead.
