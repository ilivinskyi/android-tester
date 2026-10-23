# Memory mode: look for memory leaks

Goal: for each chosen flow, a clear answer to "does repeating it keep memory growing?", with numbers.

A leak in an Android app usually means screens stay alive after they close.
Without the source code, the clearest signal is the app's own count of live objects in `dumpsys meminfo`: Activities, windows (ViewRootImpl), app contexts, Views and WebViews.
If the user leaves a screen and comes back five times and the Activity count goes 1, 2, 3, 4, 5, something keeps the old screens.
PSS (the app's share of memory) grows too, but it also grows for harmless caches, so it only counts when it grows steadily.

## Choose the flows

1. Default: the profile's `about.main_flows`, plus any screen the ticket mentions. Prefer flows that open and close something: a detail screen and back, a dialog, a tab switch, a search, a login and logout (logout is a guardrail: ask).
2. Write each flow as a short cycle that ends where it started, e.g. "Open the first note, scroll it, go back".

## Run each flow

1. Reset to the start state as in [Start state](../SKILL.md#start-state) and open the screen where the cycle starts.
2. Baseline: `adt perf memory PKG --flow "<flow name>"` (it waits 5 s so the app can go idle first).
3. Repeat the cycle in human mode at least 5 times. After each repetition, back at the start screen: `adt perf memory PKG --flow "<flow name>"`.
4. `adt perf leak PKG --flow "<flow name>"`: "suspected leak" lists what kept growing, "no leak seen" means nothing grew steadily.
5. A suspected leak: repeat the check once more from a fresh reset before reporting it. Leaks reproduce; a one-off growth is usually a cache filling up.

The session memory trend runs in every mode anyway: every 10 actions `adt` samples memory into `performance.memory_trend` (`ADT_MEMORY_EVERY` changes the interval, 0 turns it off).
Watch for the "app log:" lines after actions too: `OutOfMemoryError` is always worth a finding.

## Report

- A confirmed leak is a bug: title names the flow and what grows ("Each visit to a note keeps its screen in memory"), steps are the cycle with the number of repetitions, actual quotes the growing counts, evidence is the `adt perf leak` output saved as a `log` file.
- Severity: Major when a main flow leaks Activities (long sessions end in a crash or a slow app), Minor for slow PSS growth without object growth.
- Flows with "no leak seen" go into `worked_well` with their cycle count; flows not checked go into `not_covered`.
- The Performance table shows each flow's verdict and the session's memory trend.
