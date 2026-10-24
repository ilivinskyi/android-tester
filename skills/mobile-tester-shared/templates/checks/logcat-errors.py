# /// script
# requires-python = ">=3.11"
# ///
"""Example check (Android): list app-specific error lines from the session's logcat.

Copy to <project>/.mobile-tester/apps/<package>/checks/logcat-errors.py and adapt PATTERNS.
Runs via `adt check logcat-errors --package <package>`; exit code 1 means "something to look at".
On iOS the same idea works on the session's logs/app.log (`idt session start --log`).
"""

import os
import re
import sys
from pathlib import Path

PATTERNS = [r" E [\w.]+: ", r"Exception", r"HTTP [45]\d\d"]

log = Path(os.environ.get("MT_RUN_DIR", ".")) / "logs" / "logcat.txt"
if not log.is_file():
    sys.exit("no logcat.txt in the active session")

matches = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
           if any(re.search(p, line) for p in PATTERNS)]
for line in matches[-50:]:
    print(line)
print(f"{len(matches)} matching lines")
sys.exit(1 if matches else 0)
