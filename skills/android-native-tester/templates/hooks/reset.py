# /// script
# requires-python = ">=3.11"
# ///
"""Example reset hook: bring the app to a known start state before a reproduction attempt.

Copy to <project>/.android-tester/apps/<package>/hooks/reset.py and adapt.
Runs via `adt hook reset --package <package>` with these environment variables:
ANDROID_SERIAL, ADB, ADT_PYTHON + ADT_SCRIPT (to call adt), ADT_PACKAGE, ADT_APP_DIR, ADT_RUN_DIR, ADT_SECRETS.
Reset steps are setup: they use --fast and are logged as such.
"""

import os
import subprocess
import sys


def adt(*args: str) -> None:
    cmd = [os.environ["ADT_PYTHON"], os.environ["ADT_SCRIPT"], "--fast", *args]
    if subprocess.run(cmd).returncode != 0:
        sys.exit(f"reset failed at: adt {' '.join(args)}")


package = os.environ["ADT_PACKAGE"]
adt("app", "stop", package)
adt("app", "launch", package)
# App-specific: remove what earlier attempts left behind, so the next attempt starts from the same state.
# adt("tap", "--text", "<screen with the leftover data>")
# adt("tap", "--text", "<control that removes it>")
