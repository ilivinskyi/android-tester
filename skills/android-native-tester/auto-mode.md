# Auto mode

With `auto_mode.enabled: true` in `.android-tester/config.yaml`, the skill applies the defaults below instead of stopping to ask.
Every decision taken automatically is written to the session's `logs/decisions.md` (time, decision, value, why it came up), so the report can show what was decided without the user.
With auto mode off, the skill asks at each of these points.

## Decision catalog

| Key | Comes up when | Default | Options |
|---|---|---|---|
| `keyboard_fallback` | `adt type` can't find a key (other keyboard, language, emoji) | `keyevents` | `ask`, `keyevents` (one key event per character, noted in the finding), `bulk` |
| `app_permission_prompts` | The app under test asks for notifications, location, camera... | `deny` | `deny`, `allow`, `ask`. Testing the denied path is the stricter test |
| `consent_banners` | Cookie or tracking consent in the app | `reject_non_essential` | `reject_non_essential`, `ask`. Accepting consent is never automatic |
| `login` | The app offers login | `secrets_then_guest` | `secrets_then_guest`, `guest`, `ask` |
| `install_build` | A build file has to be installed | `install_if_verified` | `install_if_verified`, `ask`. A failed check always stops |
| `unconfirmed_repro` | A bug reproduces only through automation | `queue_manual_request` | `queue_manual_request` (ask at wrap-up), `ask_now`, `mark_only` |
| `crash_found` | The app crashes or shows an ANR | `capture_restart_continue` | `capture_restart_continue`, `ask` |
| `ambiguous_target` | Several elements match the step's target | `pick_and_log` | `pick_and_log` (most plausible visible one, logged), `ask` |
| `state_reset` | A rerun needs a clean state | `run_reset_hook` | `run_reset_hook`, `ask`. Clearing app data on a personal phone still asks |
| `time_box_end` | The time box runs out | `wrap_up` | `wrap_up`, `ask` (offer to extend) |
| `show_taps_emulator` | Recording on an emulator | `ask` | `ask`, `on`. On physical devices "Show taps" always asks |
| `report_build` | End of session | `build_and_open` | `build_and_open`, `ask` |

## Never automatic

These always stop the session and wait for the user, whatever the config says:
- Purchases, payments, subscriptions.
- Sending messages, posts, reviews, invites, feedback.
- Account deletion, logout, password or email changes.
- Accepting terms, consent, or permissions on behalf of the user's accounts (OAuth, SSO).
- System-setting changes and clearing app data on a personal device.
- Installing a build that fails the authenticity checks.
- Creating or changing Jira issues.
- Deleting evidence or earlier reports.

## Config shape

```yaml
auto_mode:
  enabled: true
  decisions:
    keyboard_fallback: keyevents
    app_permission_prompts: deny
    consent_banners: reject_non_essential
    login: secrets_then_guest
    install_build: install_if_verified
    unconfirmed_repro: queue_manual_request
    crash_found: capture_restart_continue
    ambiguous_target: pick_and_log
    state_reset: run_reset_hook
    time_box_end: wrap_up
    show_taps_emulator: ask
    report_build: build_and_open
```

A key missing from the config falls back to `ask`.
