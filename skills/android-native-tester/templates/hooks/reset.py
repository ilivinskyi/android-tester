# /// script
# requires-python = ">=3.11"
# ///
"""Example reset hook, for `reset.strategy: hook`: an app-specific way back to the start state.

Use a hook when neither built-in level fits: `restart` keeps what earlier runs left behind,
`clear-data` also loses the login. A hook can restart the app and then remove only the leftovers.

Copy to <project>/.android-tester/apps/<package>/hooks/reset.py, adapt, and set `hooks.reset: reset`.
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
adt("app", "reset", package, "--level", "restart")
# App-specific: remove what earlier runs left behind, so the next run starts from the same state.
# adt("tap", "--text", "<screen with the leftover data>")
# adt("tap", "--text", "<control that removes it>")
# adt("wait", "--text", "<what the screen shows when it's empty>")
