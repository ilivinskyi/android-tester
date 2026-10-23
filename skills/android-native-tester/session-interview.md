# Session interview

Asked at the start of every session, after onboarding.
Use the AskUserQuestion tool, at most four questions per call, recommended option first.
Skip a question when the command arguments, the config, or the app profile already answer it.
In auto mode, ask only the questions marked **always**; the rest take the defaults shown.

## Questions

1. **What are we testing?** (always, unless given as an argument)
   The app by name or package, or a build file (APK, XAPK, APKS).
   Match it to an app profile; offer to create one if missing.
   **If the profile has no `about.description`** (always, even in auto mode): ask the user to describe the app and how it works, as in "Describe the app" in [onboarding.md](onboarding.md), and save it to the profile.
   If they decline, write in `session.json` `not_covered` that expected behaviour was inferred without an app description.
2. **Ticket and context.** (always)
   A Jira key or URL, or "no ticket".
   - If Atlassian (Jira) tools are available in this session, read the ticket: summary, description, acceptance criteria, attachments list.
   - If the connector exists but isn't authorized, tell the user to authorize it via `/mcp`, and meanwhile ask them to paste the description.
   - Otherwise ask the user to paste the description.
   Also ask for any extra context: what changed in this build, known risks, what the developer is worried about.
3. **Mode.** Default: explore, or repro when the ticket is a bug report, or test-case when a test-case file was given.
4. **Charter and focus.** What to cover and what is out of scope. Default: derived from the ticket; for explore without a ticket, the first entries of `about.main_flows`. `about.not_in_scope` is always out of scope.
5. **Device.** Default: the only ready device, or the inventory's non-personal one.
   Mention when the chosen device is personal (stricter guardrails) and when an emulator would be better (config stress, data clearing).
6. **Build.** Is the build to test already installed (default when a matching version is installed) or should it be installed from a file?
7. **Login state.** Default from the profile: secrets file, guest, or the user logs in on the device before the session.
8. **Time box.** Default from the config.
9. **Evidence.** Screen recording and logcat are on by default. "Show taps" is asked separately in preparation.
10. **App scripts.** Run the profile's setup/reset hooks (default yes when they exist). Offer to add scripts when the user describes a repeatable setup they do by hand.

## Session plan

Summarise in one paragraph, then wait for a go (in auto mode, continue right away):
charter, mode, app and build, device, login state, time box, evidence, hooks, ticket.
Write the same values into `session.json` after `adt session start`.
