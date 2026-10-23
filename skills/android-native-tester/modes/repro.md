# Repro mode: reproduce a reported bug

Goal: a reliable answer to "does this bug happen, under which exact conditions, and can a person hit it?"

## 1. Understand the report

1. Read the ticket: steps, expected, actual, build, device, attachments.
2. Write down the preconditions it implies (account state, data, settings, app version) and what it leaves open.
3. Ask the user about gaps that change the setup (logged in or not, which build); guess nothing that matters.

## 2. Set up a known state

1. Run the profile's reset hook, or get to the start state with `--fast` setup steps, and record those in `setup_steps_fast`.
2. Check the state you depend on (data present or absent, logged in or not, a setting or feature flag) with a screenshot before the first step.
   Leftover state from earlier runs sends you, and later the person, down different paths.

## 3. Reproduce in human mode

1. Perform the reported steps with `adt` in human mode. Repro steps never use `--fast`.
2. Observe with `adt observe --image-only` between steps; use full observes only when you need element indices.
   Full observes turn on the accessibility layer, which can change app behaviour.
3. Note the action log `t` of the first and last step of each attempt.
4. Repeat until you can state N of M (at least 3 attempts when it reproduces, 5 when it doesn't).

## 4. Narrow the trigger

When it reproduces, find what's necessary:
- Change one variable per experiment (how a step is done, timing, the path to a screen, the data, fresh vs existing state).
- Keep a variant table in `logs/variants.md`: variant, what changed, N of M.
- Stop when the shortest reliable path is known and every remaining step is necessary.

## 5. Confirm with a person

A bug reproduced only by automation is **Unconfirmed**.
Manual-repro protocol (offer it; in auto mode `unconfirmed_repro` decides when):
1. Set up the start state and tell the user exactly what is on screen.
2. `adt record start --out RUN/videos/<id>-manual.mp4`.
3. Give the user the steps and ask them to perform them by hand (AskUserQuestion with outcomes: reproduced / not reproduced / something else).
4. `adt record stop`; compare their run with the automated one frame by frame (`ffmpeg` frames at the step times).
5. If they didn't reproduce it, list every difference between their run and the automated runs, and test each one as a variant.
   If the only difference left is the input source, keep it Unconfirmed and say so in `notes`.
   Offer a hybrid run (some steps automated, some by hand) to find the step where injected input matters.

## 6. Report

- Status: Confirmed (a person reproduced it), Unconfirmed (only automation), or a finding of type observation "Not reproduced" with what was tried.
- `reproducibility`: automated and manual N of M.
- Steps: the shortest reliable path, preconditions included.
- Evidence: clip of the automated repro, the manual recording when there is one, and the variant table as a `log` evidence file.
