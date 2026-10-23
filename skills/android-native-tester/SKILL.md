---
name: android-native-tester
description: Use when the user runs /android-native-tester to test an Android app on a phone or emulator - exploratory testing, running test cases, reproducing a bug, or reviewing UI and accessibility, with onboarding on first use and a standard QA report.
disable-model-invocation: true
argument-hint: "[explore|test-case|repro|ui-review] [ticket, app, APK or test-case file]"
---

# Android native tester

Runs one test session on an Android device and ends with the standard report.
Arguments, when given: $ARGUMENTS

**REQUIRED:** follow the `android-human-input` skill for every UI action, and use the `android-device` skill for `adt` commands.
`adt` below means `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/adt.py"`.
Templates referenced below live in `${CLAUDE_PLUGIN_ROOT}/skills/android-native-tester/templates/`.

## Session flow

Work through these phases in order and keep the user's task list in step with them.

### 1. Project setup

1. Run `adt doctor`. Stop and help the user if no device is ready.
2. Read `.android-tester/config.yaml` in the project.
   If it doesn't exist, run onboarding first: [onboarding.md](onboarding.md).
3. Note whether auto mode is on. In auto mode, apply the defaults from [auto-mode.md](auto-mode.md) instead of asking at the decision points listed there.
   Guardrails are never automatic.

### 2. Session interview

Ask the questions in [session-interview.md](session-interview.md), skipping what the arguments or the config already answer.
End with a one-paragraph session plan (charter, mode, device, build, time box, evidence) and wait for the user's go, unless auto mode is on.

### 3. Preparation

1. Device: `adt -s SERIAL info`. Check it matches the device inventory; note `personal: true` devices.
2. App profile: read `.android-tester/apps/<package>/profile.yaml` (above all its `about` block) and `notes.md`. Known issues and quirks in the notes save time.
3. Build:
   - Installed: compare `adt app info PKG` with the version the user expects.
   - From a file: `adt apk inspect FILE`. Do not install when the signers differ between splits, the signer differs from `expected_signer_sha256` in the profile, the package name doesn't match, or notable permissions don't fit the app. Report what you found and ask.
   - Install with `adt --fast app install FILE` (setup step).
4. Hooks: run `adt hook setup --package PKG` and the login hook when the profile defines them.
5. Start the session: `adt session start --dir <reports dir>/<YYYY-MM-DD>-<app>-<mode>[-<ticket>] --package PKG --mode MODE --charter "..." [--ticket KEY] --record --logcat`.
   Then fill `session.json` with title, tester, ticket details, time box and app install source (see [report-standard.md](report-standard.md)).
6. Ask whether to turn on "Show taps" for this recording (always ask; on a phone pass the approval to `adt touches on --approval`).

### 4. Testing

Follow the mode guide:

| Mode | Guide |
|---|---|
| explore | [modes/explore.md](modes/explore.md) |
| test-case | [modes/test-case.md](modes/test-case.md) |
| repro | [modes/repro.md](modes/repro.md) |
| ui-review | [modes/ui-review.md](modes/ui-review.md) |

Judging behaviour:
- Expected behaviour comes from the app profile's `about` (description, main flows, rules, glossary), the ticket, and what the app itself says on screen. Nothing else defines "correct".
- Don't bring in checks that belong to a different kind of app. Test ideas follow this app's flows and rules, plus the universal ones (crashes, data loss, wrong or misleading messages, state that doesn't persist, accessibility, layout).
- When you can't tell whether something is a bug because the expected behaviour isn't described, ask the user (or, in auto mode, report it as an observation and write the open question in `notes`). Record any assumption you make in the finding.

While testing:
- Write each finding into `findings.json` as soon as it's verified, not at the end. Fields and severity scale: [report-standard.md](report-standard.md).
- Before writing a finding, read the raw source that proves it (hierarchy XML, logcat, screenshot). If a finding turns out wrong, set it to Retracted with the reason; never delete it.
- Save evidence with `adt observe --name <id>-<what>` and note the action log time for video clips.
- Watch the time box. Tell the user at the halfway point and when it runs out.

### 5. Wrap-up

1. `adt session end`. Run the teardown hook if the profile has one, and `adt touches off` if you turned it on.
2. Cut one clip per bug: `adt clip --from <t of first repro step> --to <t of last> --out videos/<id>.mp4`, and add it to the finding's evidence.
3. `adt report check RUN`, fix every problem, then `adt report build RUN`. Open `index.html` in the browser pane and look at it.
4. For each Unconfirmed finding, offer the manual reproduction in [modes/repro.md](modes/repro.md).
5. Offer Jira: the `bugs/<id>.md` files are paste-ready. Create issues through the Atlassian connector only when the user explicitly approves each one.
6. Append what you learned about the app (screen map, quirks, known issues) to the app's `notes.md`, after telling the user.
7. Answer with: where the report is, the findings by severity, unconfirmed items, and what was not covered.

## Never automatic, never skipped

- Payments, outgoing messages/posts/reviews, account deletion/logout/password changes, accepting terms or consent: stop and ask.
- System-setting changes and clearing app data on a personal phone: ask.
- Installing a build that fails the checks in step 3.
- Creating Jira issues.
