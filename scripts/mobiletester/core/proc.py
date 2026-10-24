"""Background processes that outlive the CLI call that started them (log streams, recordings, the iOS runner)."""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys


def detached_kwargs() -> dict:
    """Popen kwargs so a background process outlives the CLI invocation that started it."""
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        return {"creationflags": flags, "stdin": subprocess.DEVNULL}
    return {"start_new_session": True, "stdin": subprocess.DEVNULL}


def terminate(pid: int) -> None:
    """Kill a process started with detached_kwargs, including its children."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return
    import signal

    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGTERM)


def is_alive(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in out.stdout
    # A child of this very process that exited stays a zombie until it is reaped, and looks alive.
    with contextlib.suppress(ChildProcessError):
        if os.waitpid(pid, os.WNOHANG)[0] == pid:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
