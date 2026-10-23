import pytest

from adtlib.adb import DeviceError, DeviceInfo, parse_devices, pick_serial

DEVICES_OUTPUT = """List of devices attached
0A1B2C3D4E5F6         device product:lynx model:Pixel_7a device:lynx transport_id:1
emulator-5554          device product:sdk_gphone64_x86_64 model:sdk_gphone64_x86_64 transport_id:2
R5CT1234               unauthorized usb:1-1 transport_id:3

"""


def test_parse_devices():
    devices = parse_devices(DEVICES_OUTPUT)
    assert [d.serial for d in devices] == ["0A1B2C3D4E5F6", "emulator-5554", "R5CT1234"]
    assert devices[0].model == "Pixel 7a" and devices[0].state == "device"
    assert devices[1].is_emulator and not devices[0].is_emulator
    assert devices[2].state == "unauthorized"


def test_pick_single_ready_device():
    devices = [DeviceInfo("A", "device"), DeviceInfo("B", "unauthorized")]
    assert pick_serial(devices, None) == "A"


def test_pick_requires_serial_when_ambiguous():
    with pytest.raises(DeviceError, match="pass -s"):
        pick_serial([DeviceInfo("A", "device"), DeviceInfo("B", "device")], None)


def test_unauthorized_hint():
    with pytest.raises(DeviceError, match="Allow USB debugging"):
        pick_serial([DeviceInfo("A", "unauthorized")], None)


def test_requested_serial_must_exist():
    with pytest.raises(DeviceError, match="not connected"):
        pick_serial([DeviceInfo("A", "device")], "Z")
