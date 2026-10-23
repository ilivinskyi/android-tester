# Onboarding

Runs once per project, on the first `/android-native-tester` when `.android-tester/config.yaml` is missing, or when the user asks to redo it.
Ask with the AskUserQuestion tool, at most four questions per call, recommended option first.
Write the answers into the files below as you go, so an interrupted onboarding keeps what it has.

## 1. Tester and team defaults

Ask:
- Tester name for reports (default: the user's name if known).
- Reports folder (default `reports/`) and report language (default English).
- Default time box for sessions (15, 30, 60 minutes).
- Jira: project key and site URL, or "no Jira".
  Tell the user that drafts are written as Markdown and issues are only created with explicit approval each time.
- Team-specific severity rules, if any, on top of the standard scale in [report-standard.md](report-standard.md).

## 2. Device inventory

1. Run `adt devices`, and `adt -s SERIAL info` for each ready device.
2. For each device ask: a short name, and whether it is a **personal** device.
   Personal devices get stricter guardrails: no system-setting changes, no clearing app data, no installing builds without asking.
3. Record serial, name, kind (physical or emulator), personal, navigation mode and keyboard.
   If the keyboard isn't Gboard, warn that on-screen typing may need the fallback (see `keyboard_fallback` in auto mode).

## 3. App profiles

Ask whether to set up an app profile now (it can also be created at the first session for that app).
For each app, create `.android-tester/apps/<package>/` from the templates:
- `profile.yaml`: name, package, store URL, expected signer, login method, reset strategy (see "Start state" below), which hooks run when, risky areas,
  and the `about` block (see "Describe the app" below).
- `notes.md`: what testers learn over time (screen map, quirks, known issues, test accounts by name only). The app's purpose and rules belong in `about`, not here.
- `hooks/` and `checks/` with the example scripts, only when the user wants scripts.
- `secrets.local.yaml` only when the login method is `secrets`; the user fills it in themselves. Never ask for passwords in chat.

To fill `expected_signer_sha256`, install the app from the store on a trusted device and inspect it later, or take the signer from a build the team trusts (`adt apk inspect`).

### Describe the app

This is the most important part of the profile: without it the model can only guess what correct behaviour is.
1. Ask an open question, not a multiple choice: "Describe the app and how it works: what it is for, who uses it, the main things people do in it, and the rules it must follow. Paste docs or links if you have them."
2. Put the answer in `about.description` in the user's own words; don't summarise it away.
3. Ask follow-ups only for what the answer leaves open, and fill the structured fields from it: `users`, `main_flows`, `rules`, `roles`, `integrations`, `not_in_scope`, `glossary`.
   Use the app's own terms; don't add flows or rules the user didn't mention.
4. Read back the main flows and rules in one short list and ask whether they're right.
5. If the user prefers not to describe it now, leave `about` empty. The first session then asks for it (see the session interview).

### Start state

Reruns are only comparable when each one starts from the same state.
Ask: "How should I bring the app back to a known start state before each run?" and save the answer as `reset.strategy`:
- **Clear data** (recommended when the login can be redone without the user: guest, secrets or a login hook): like a fresh install every time. On a personal device it still asks first, once per session.
- **Restart**: force-stop and relaunch. Keeps data and login; choose it when the user logs in by hand or the data is slow to set up.
- **Script**: an app-specific reset hook that removes only what tests leave behind (e.g. items added to a list) and keeps the login. Copy `templates/hooks/reset.py` and set `hooks.reset`.
- **Never**: the user prepares the state by hand.

Then ask what a fresh start looks like (intro screens, region or language choice) and how to get past it, and save the steps in plain words as `reset.after`.
Anything that accepts terms or consent stays a guardrail: it is asked each time, never written into `reset.after`.

### Problems outside the session's scope

Sessions have a charter, but testers notice things elsewhere too. Ask two questions for each app:
1. "When I notice a problem outside the session's scope (another screen, an unrelated feature), should I report it?"
   Yes (recommended): it goes into a separate "Outside scope" section of the report, not counted as a bug, for the team to triage.
   No: such problems are not mentioned at all.
   Save as `outside_scope.report`.
2. "Are there screens or features that are still being built, which should never be reported even when they look broken?"
   Save the list in the user's own words as `outside_scope.not_ready`.

## 4. Auto mode

Ask: "Would you like auto mode? Then I won't stop at routine decisions and use the defaults you approve now."
- No: write `auto_mode.enabled: false`. The skill asks at each decision point.
- Yes: show the whole catalog from [auto-mode.md](auto-mode.md) as one list (decision, default, options) and let the user change any default.
  Also show the "never automatic" list so it's clear what will still stop the session.
  Write `auto_mode.enabled: true` and every decision with its chosen value.

## 5. Files and ignores

1. Write `.android-tester/config.yaml` from `templates/config.yaml`.
2. Offer to add these lines to the project's `.gitignore` (ask before editing it):
   ```
   .adt/
   .android-tester/**/secrets.local.yaml
   ```
   Reports may contain screenshots of personal data; ask whether `reports/` should be ignored too.
3. Summarise what was set up and continue with the session interview.
