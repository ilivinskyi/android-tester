# /// script
# requires-python = ">=3.11"
# ///
"""Example reset hook, for `reset.strategy: hook`: an app-specific way back to the start state.

Use a hook when neither built-in level fits: `restart` keeps what earlier runs left behind,
`clear-data` also loses the login. A hook can restart the app and then remove only the leftovers.

Copy to <project>/.mobile-tester/apps/<package>/hooks/reset.py, adapt, and set `hooks.reset: reset`.
Runs via `adt hook reset --package <package>` (Android) or `idt hook reset --package <bundle id>` (iOS) with:
MT_PLATFORM, MT_PYTHON + MT_SCRIPT (to call the same tool back), MT_PACKAGE, MT_APP_DIR, MT_RUN_DIR, MT_SECRETS,
plus ANDROID_SERIAL and ADB on Android, IDT_UDID on iOS.
Reset steps are setup: they use --fast and are logged as such.
"""

import os
import subprocess
import sys


def dt(*args: str) -> None:
    """adt or idt, whichever ran this hook."""
    cmd = [os.environ["MT_PYTHON"], os.environ["MT_SCRIPT"], "--fast", *args]
    if subprocess.run(cmd).returncode != 0:
        sys.exit(f"reset failed at: {' '.join(args)}")


package = os.environ["MT_PACKAGE"]
dt("app", "reset", package, "--level", "restart")
# App-specific: remove what earlier runs left behind, so the next run starts from the same state.
# dt("tap", "--text", "<screen with the leftover data>")
# dt("tap", "--text", "<control that removes it>")
# dt("wait", "--text", "<what the screen shows when it's empty>")
