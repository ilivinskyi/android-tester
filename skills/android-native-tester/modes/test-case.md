# Test-case mode: run written test cases

Goal: execute given test cases step by step and report pass/fail per step, with findings for every failure.

## Input

Markdown test cases, one or more per file (format: `templates/test-case.md`):
a title and ID, preconditions, numbered steps, and an expected result per step or per case.
When a case is ambiguous (which button, which data), look for the answer in the app profile's `about` (rules, glossary) first.
If it's still unclear, ask before running it, or in auto mode choose the most plausible reading and write it in the result's `note`.

## Run each case

1. Establish the preconditions (reset hook, `--fast` setup), and verify them with a screenshot.
2. For each step:
   - Perform it in human mode.
   - Check its expected result: screenshot plus the hierarchy when text or state matters. Never assume a step passed because the command succeeded.
   - Record the result in `session.json` `test_results`: `pass`, `fail` (with a finding id), `blocked` (with a note on why), or `skipped`.
3. On a failure: capture evidence, write the finding (steps from the case, expected from the case, actual as observed), then decide with the user (or auto mode) whether to continue the case, skip to the next one, or stop.
4. A failure seen only once: rerun the case from its preconditions before reporting it as a bug; record N of M.

## Report extras

- `test_results` drives the "Test results" table.
- `summary` states passed / failed / blocked counts and the cases that matter most.
