# adt command reference

`adt` = `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/adt.py"`.

Global options (before or after the command):

| Option | Meaning |
|---|---|
| `-s SERIAL` | device (otherwise `ANDROID_SERIAL`, otherwise the only ready device) |
| `--fast` | instant adb input without pacing or checks. Setup and reset steps only |
| `--pace human\|slow` | human (default) or slow pacing; also `ADT_PACE` |
| `--no-verify` | skip the did-the-screen-change check |

## Setup

| Command | Purpose |
|---|---|
| `doctor` | adb location and version, other tools, device states |
| `devices [--json]` | serial, state, physical/emulator, model |
| `info [--json]` | model, Android version, screen, density, navigation mode, keyboard, locale, show taps, accessibility services |

## Observing

`observe [--name STEM] [--save-dir DIR] [--no-image] [--no-marks] [--image-only] [--json]`

- `--name` saves screenshot, preview and XML into the active session's `screenshots/`.
- `--image-only` takes only a screenshot: no hierarchy dump, so the accessibility layer stays off (use in repro runs).

Element line format:

```
[7] LinearLayout "Storage | 16% used" #storage_row @(540,1396) 1080x195 [click RISK:payment]
```

- `"..."` label: own text or content description; clickable containers show their non-interactive children's texts joined by ` | `.
- `#id` short resource id, `@(x,y)` center in device pixels, `WxH` size in device pixels.
- Flags: `click long checked/unchecked scroll edit password focused selected disabled sr-only RISK:<category>`.
- `sr-only`: text too small to see, there for screen readers only (e.g. a value whose visible version is drawn as an image). Read it, don't tap it.
- `RISK:` is set for action-like wording (short labels, not questions or sentences) and resource ids.

State files per device under `ADT_HOME` (default `./.adt/<serial>/`): `latest.json`, `latest.xml`, `latest.png`, `latest_preview.jpg`, `device.json` (cached facts).

## Acting (human mode by default)

Every action: think pause (0.4-1.4 s), the action, then wait until the screen is stable and compare it with the screen before.
"no visible change" in the output means the action may not have landed.
Taps on an element go to a random point near its center that no other control covers; a fully covered element is refused (exit 4).

| Command | Notes |
|---|---|
| `tap --index N` | element from the last observe |
| `tap --text "Label" [--scroll [MAX]]` | ranking: exact own text > exact part of a merged label > label starts with it > word start > substring; clickable elements win ties |
| `tap --id ID [--scroll [MAX]]` | full `pkg:id/name` or short `name` |
| `tap --xy X Y` / `tap --preview-xy X Y` | device / preview pixels; the guard checks the topmost element under the point |
| `tap ... --long` | long press, 0.7-1.0 s |
| `tap ... --allow-risk "APPROVAL"` | only after explicit user approval; logged to `guard_log.jsonl` |
| `type "TEXT" [--index N] [--submit] [--fallback ask\|keyevents\|bulk]` | types on the on-screen keyboard (letters, shift, symbol layers); `--submit` taps the keyboard's action key; exit 6 when a character can't be typed and `--fallback ask`; warns when the field shows something else (autocorrect) |
| `key back` / `key home` | edge swipe / swipe up in gesture navigation, nav-bar key in 3-button navigation |
| `key NAME [--repeat N]` | `enter tab delete recents menu search escape power wakeup volume_up volume_down` or any `KEYCODE_*` |
| `scroll up/down/left/right [--index N]` | direction the content moves into view; default area is the largest scrollable |
| `swipe X1 Y1 X2 Y2 [--ms N]` | endpoints wobble slightly in human mode |
| `wait --text T / --id ID [--gone] [--timeout 10]` | polls the hierarchy |

## Apps (setup operations)

| Command | Notes |
|---|---|
| `app list [FILTER] [--all]` | third-party packages unless `--all` |
| `app current` | foreground package and activity |
| `app info PKG` | versionName, versionCode, targetSdk |
| `app launch PKG` | launcher intent (not an icon tap) |
| `app stop PKG` | force-stop |
| `app clear PKG` | wipes app data: ask first on physical devices |
| `app install FILE` | `.apk`, or `.xapk` / `.apks` bundles (split APKs) |
| `apk inspect FILE` | package, version, signing certificates per APK, permissions of note: run before installing a build from outside a store |

## Sessions and evidence

| Command | Notes |
|---|---|
| `session start --dir RUN [--package P] [--mode explore\|test-case\|repro\|ui-review] [--charter C] [--ticket T] [--record] [--logcat]` | creates `screenshots/ videos/ logs/ bugs/`, `session.json`, `findings.json`; actions log to `logs/actions.jsonl` |
| `session end [--discard-video]` | stops recording and logcat started by the session |
| `session status` | active run folder |
| `record start --out FILE.mp4` / `record stop [--discard]` | 3-minute chunks joined with ffmpeg; writes `FILE.timeline.json` |
| `clip --from T --to T --out FILE [--video V] [--pad 3]` | T = `t` from actions.jsonl, `HH:MM:SS` today, or epoch; default video is the session's |
| `logcat start --out FILE [--keep]` / `logcat stop` | background stream |
| `logcat crashes [--package PKG]` | crash buffer + FATAL/ANR lines since the last clear |
| `touches on --approval "..."` / `touches off` | "Show taps" markers in recordings; a system setting, needs approval on phones |
| `hook NAME --package P [-- ARGS]` | runs `.android-tester/apps/P/hooks/NAME.(py\|sh\|ps1)` |
| `check NAME --package P [-- ARGS]` | runs `.android-tester/apps/P/checks/NAME.(py\|sh\|ps1)` |
| `report check RUN` / `report build RUN` | validate / render `index.html` and `bugs/<id>.md` |

Hook and check scripts receive `ANDROID_SERIAL`, `ADB`, `ADT` (command line for adt), `ADT_PACKAGE`, `ADT_APP_DIR`, `ADT_RUN_DIR`, and `ADT_SECRETS` when `secrets.local.yaml` exists.
Python scripts run with `uv run --script`, so they may declare their own dependencies (PEP 723).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 2 | bad input or report problems |
| 3 | device or adb problem |
| 4 | element not found, ambiguous, covered, or wait timed out |
| 5 | blocked by a guardrail: ask the user |
| 6 | decision needed: ask the user or apply the auto-mode default |
