"""Real iPhones and iPads through `xcrun devicectl` (CoreDevice): discovery, apps, crash logs, tunnel address.

devicectl's stdout is for people; its `--json-output` file is the stable interface, so every call writes one
and reads `result` from it. Most device services need Developer Mode on the device and the developer disk
image (DDI), which devicectl mounts on its own once Developer Mode is on.

While anything uses the device (xcodebuild running the runner, a devicectl command), CoreDevice keeps an IPv6
tunnel to it; the device's end has a fresh address per tunnel (`tunnelIPAddress`, e.g. fd9a:19f3:9cf6::1)
that the Mac can connect to. That is how idt reaches the runner's HTTP server on a device.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from .simctl import DeviceError, SimctlError, xcrun


class DevicectlError(SimctlError):
    """A devicectl command failed; callers treat it like a failed simctl command."""


def run(*args: str, timeout: float = 120) -> dict:
    """Run `devicectl ARGS` and return the `result` of its JSON output."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "result.json"
        cmd = [xcrun(), "devicectl", "--quiet", "--timeout", str(round(timeout)), "--json-output", str(out), *args]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout + 15)
        except subprocess.TimeoutExpired as exc:
            raise DevicectlError(f"devicectl {' '.join(args[:3])}: no answer within {timeout:.0f}s") from exc
        data = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
    if proc.returncode != 0 or data.get("info", {}).get("outcome", "success") != "success":
        raise DevicectlError(f"devicectl {' '.join(args[:3])}: {error_message(data, proc.stderr)}")
    return data.get("result") or {}


def error_message(data: dict, stderr: bytes = b"") -> str:
    """The first line people need: CoreDevice's own description, else devicectl's stderr."""
    user_info = (data.get("error") or {}).get("userInfo") or {}
    description = (user_info.get("NSLocalizedDescription") or {}).get("string")
    if description:
        return description
    lines = [line.strip() for line in stderr.decode(errors="replace").splitlines() if line.strip()]
    return lines[0].removeprefix("ERROR: ") if lines else "failed"


# --- devices ---------------------------------------------------------------------------------

@dataclass
class PhysicalDevice:
    udid: str            # the hardware UDID, as Xcode and `-destination id=` know it
    identifier: str      # CoreDevice's own id
    name: str            # the name the owner gave it
    model: str           # "iPhone 17 Pro"
    os_version: str      # "27.0.1"
    transport: str       # "wired" (USB) or "localNetwork" (Wi-Fi)
    connection: str      # "connected" while a tunnel is up, "disconnected" when idle, "unavailable" when out of reach
    paired: bool
    developer_mode: bool | None  # None: the device didn't say
    ddi: bool | None             # developer disk image services mounted

    kind = "physical"

    @property
    def reachable(self) -> bool:
        return self.paired and self.connection != "unavailable"

    @property
    def ready(self) -> bool:
        """Paired, in reach and in Developer Mode: what the runner and devicectl's app commands need."""
        return self.reachable and self.developer_mode is True

    @property
    def runtime(self) -> str:
        return f"iOS {self.os_version}"

    @property
    def state(self) -> str:
        if not self.paired:
            return "not paired"
        if not self.reachable:
            return "unavailable"
        if self.developer_mode is False:
            return "developer mode off"
        return "ready"

    def problem(self) -> str | None:
        """What stops idt from using it, phrased as what the person has to do; None when nothing does."""
        if not self.paired:
            return (f"{self.name} is not paired with this Mac: connect it by cable, unlock it and tap Trust "
                    "(the person holding the device has to do this)")
        if not self.reachable:
            return f"{self.name} is out of reach: connect it by cable or put it on this Mac's Wi-Fi, and unlock it"
        if self.developer_mode is False:
            return (f"Developer Mode is off on {self.name}: on the device, Settings > Privacy & Security > "
                    "Developer Mode, turn it on and restart (the person holding the device has to do this)")
        return None


def _developer_mode(state: dict, legacy: dict) -> bool | None:
    status = state.get("developerModeStatus")
    if isinstance(status, dict) and status:
        return "enabled" in status
    legacy_status = legacy.get("developerModeStatus")
    return legacy_status == "enabled" if legacy_status else None


def parse_devices(result: dict) -> list[PhysicalDevice]:
    """Physical iOS and iPadOS devices from `devicectl list devices`; simulators are simctl's business.

    Reads the `properties` dictionary; devicectl marks the older top-level blocks as deprecated, so they are
    only a fallback for what `properties` doesn't carry (the DDI state).
    """
    devices = []
    for entry in result.get("devices", []):
        props = entry.get("properties") or {}
        hardware, connection = props.get("hardware") or {}, props.get("connection") or {}
        state, software = props.get("state") or {}, props.get("software") or {}
        legacy = entry.get("deviceProperties") or {}
        if hardware.get("reality") != "physical" or hardware.get("platform") != "iOS":
            continue
        ddi = legacy.get("ddiServicesAvailable")
        devices.append(PhysicalDevice(
            udid=hardware.get("udid") or entry.get("identifier", ""),
            identifier=entry.get("identifier", ""),
            name=state.get("name") or legacy.get("name", ""),
            model=hardware.get("marketingName") or hardware.get("productType", ""),
            os_version=(software.get("osVersionNumber") or {}).get("stringValue") or legacy.get("osVersionNumber", ""),
            transport=connection.get("transportType", ""),
            connection=connection.get("state", ""),
            paired=connection.get("pairingState") == "paired",
            developer_mode=_developer_mode(state, legacy),
            ddi=ddi if isinstance(ddi, bool) else None,
        ))
    return devices


def list_devices() -> list[PhysicalDevice]:
    try:
        return parse_devices(run("list", "devices", timeout=30))
    except (DevicectlError, FileNotFoundError):
        return []  # an Xcode without devicectl, or CoreDevice not answering: no devices rather than a crash


def find(wanted: str, devices: list[PhysicalDevice] | None = None) -> PhysicalDevice | None:
    """By hardware UDID, CoreDevice id or the device's name; None when no paired device matches."""
    for dev in list_devices() if devices is None else devices:
        if wanted in (dev.udid, dev.identifier, dev.name):
            return dev
    return None


def require_ready(dev: PhysicalDevice) -> PhysicalDevice:
    if problem := dev.problem():
        raise DeviceError(problem)
    return dev


def tunnel_address(udid: str) -> str:
    """The device's address inside CoreDevice's tunnel; asking for the details brings the tunnel up."""
    details = run("device", "info", "details", "--device", udid, timeout=60)
    address = (details.get("connectionProperties") or {}).get("tunnelIPAddress") \
        or ((details.get("properties") or {}).get("connection") or {}).get("tunnelIPAddress")
    if not address:
        raise DevicectlError("CoreDevice has no tunnel to the device: unlock it and check the cable or Wi-Fi")
    return address


# --- apps ------------------------------------------------------------------------------------

def parse_apps(result: dict) -> dict[str, dict]:
    """`device info apps` as simctl.apps() shapes it: bundle id -> Info.plist-like keys, plus where it is."""
    found = {}
    for app in result.get("apps", []):
        bundle = app.get("bundleIdentifier")
        if not bundle:
            continue
        found[bundle] = {
            "CFBundleName": app.get("name", ""),
            "CFBundleDisplayName": app.get("name", ""),
            "CFBundleShortVersionString": app.get("version", ""),
            "CFBundleVersion": app.get("bundleVersion", ""),
            "ApplicationType": "User" if app.get("removable", True) and not app.get("defaultApp") else "System",
            "url": app.get("url", ""),
        }
    return found


def apps(udid: str, include_system: bool = True) -> dict[str, dict]:
    extra = ["--include-all-apps"] if include_system else []
    return parse_apps(run("device", "info", "apps", "--device", udid, *extra))


def _bundle_path(url: str) -> str:
    """'file:///private/var/containers/Bundle/Application/X/Habits.app/' -> '/private/var/.../Habits.app'."""
    return unquote(urlparse(url).path).rstrip("/")


def app_info(udid: str, bundle_id: str) -> dict:
    """The same keys as simctl.app_info. The executable is the bundle's name: devicectl doesn't list
    CFBundleExecutable, and Xcode names both after the product unless a project changes it."""
    info = parse_apps(run("device", "info", "apps", "--device", udid, "--include-all-apps", "--bundle-id",
                          bundle_id)).get(bundle_id)
    if info is None:
        raise DevicectlError(f"{bundle_id} is not installed on this device")
    return {
        "package": bundle_id,
        "name": info["CFBundleDisplayName"],
        "versionName": info["CFBundleShortVersionString"],
        "versionCode": info["CFBundleVersion"],
        "executable": Path(_bundle_path(info["url"])).stem,
        "bundle_path": _bundle_path(info["url"]),
    }


def install(udid: str, app: Path) -> None:
    run("device", "install", "app", "--device", udid, str(app), timeout=600)


def uninstall(udid: str, bundle_id: str) -> None:
    run("device", "uninstall", "app", "--device", udid, bundle_id, timeout=120)


def launch(udid: str, bundle_id: str) -> int | None:
    """Launch in the foreground and return the pid. Options go before the bundle id: anything after it is
    passed to the app as its arguments."""
    result = run("device", "process", "launch", "--device", udid, "--terminate-existing", bundle_id, timeout=60)
    return (result.get("process") or {}).get("processIdentifier")


def parse_pids(result: dict, bundle_path: str) -> list[int]:
    """Pids of processes whose executable lives inside the app bundle."""
    prefix = bundle_path.rstrip("/") + "/"
    pids = []
    for proc in result.get("runningProcesses", []):
        executable = _bundle_path(proc.get("executable", "")) if proc.get("executable") else ""
        # /private/var and /var are the same folder on iOS; processes and apps don't always agree on which.
        if executable and (executable + "/").removeprefix("/private").startswith(prefix.removeprefix("/private")):
            pids.append(proc["processIdentifier"])
    return pids


def terminate(udid: str, bundle_id: str) -> bool:
    """False when the app wasn't running."""
    bundle_path = app_info(udid, bundle_id)["bundle_path"]
    pids = parse_pids(run("device", "info", "processes", "--device", udid), bundle_path)
    for pid in pids:
        run("device", "process", "terminate", "--device", udid, "--pid", str(pid))
    return bool(pids)


# --- crash logs ------------------------------------------------------------------------------

def parse_files(result: dict) -> list[str]:
    """Relative paths from `device info files` (one entry per file, folders too)."""
    names = []
    for entry in result.get("files", []):
        if isinstance(entry, str):
            names.append(entry)
            continue
        name = entry.get("relativePath") or entry.get("path") or entry.get("name")
        if name and entry.get("type", "file") not in ("directory", "folder"):
            names.append(name)
    return names


def crash_logs(udid: str) -> list[str]:
    return parse_files(run("device", "info", "files", "--device", udid, "--domain-type", "systemCrashLogs",
                           timeout=60))


def copy_crash_log(udid: str, name: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run("device", "copy", "from", "--device", udid, "--domain-type", "systemCrashLogs", "--source", name,
        "--destination", str(destination), timeout=60)
    return destination


def screenshot(udid: str) -> bytes:
    """Through CoreDevice; slower than the runner's, but works without it."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "screen.png"
        run("device", "capture", "screenshot", "--device", udid, "--destination", str(target), timeout=30)
        return target.read_bytes()
