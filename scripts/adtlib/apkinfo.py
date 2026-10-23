"""Inspecting APKs and split-APK bundles (.xapk, .apks) without the Android SDK.

Used before installing a build that didn't come from a store: who signed it, is every split signed
by the same key, and does it ask for permissions a normal app of its kind wouldn't.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import struct
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

_SIG_BLOCK_MAGIC = b"APK Sig Block 42"
_SCHEMES = {0x7109871A: "v2", 0xF05368C0: "v3", 0x1B93AD61: "v3.1"}

# Permissions and bindings that deserve a human look in a third-party app.
NOTABLE_PERMISSIONS = {
    "android.permission.BIND_ACCESSIBILITY_SERVICE", "android.permission.BIND_DEVICE_ADMIN",
    "android.permission.BIND_NOTIFICATION_LISTENER_SERVICE", "android.permission.SYSTEM_ALERT_WINDOW",
    "android.permission.REQUEST_INSTALL_PACKAGES", "android.permission.QUERY_ALL_PACKAGES",
    "android.permission.READ_SMS", "android.permission.SEND_SMS", "android.permission.RECEIVE_SMS",
    "android.permission.READ_CALL_LOG", "android.permission.CALL_PHONE", "android.permission.READ_CONTACTS",
    "android.permission.RECORD_AUDIO", "android.permission.MANAGE_EXTERNAL_STORAGE",
    "android.permission.PACKAGE_USAGE_STATS", "android.permission.READ_PHONE_STATE",
}


@dataclass
class ApkInfo:
    file: str
    package: str = ""
    version_name: str = ""
    version_code: str = ""
    schemes: list[str] = field(default_factory=list)
    cert_sha256: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)


# --- binary manifest -------------------------------------------------------------------------

def _string_pool(data: bytes, offset: int) -> list[str]:
    _, header_size, _, count, _, flags, strings_start, _ = struct.unpack_from("<HHIIIIII", data, offset)
    utf8 = bool(flags & 0x100)
    offsets = struct.unpack_from(f"<{count}I", data, offset + header_size)
    base = offset + strings_start
    strings = []
    for off in offsets:
        p = base + off
        if utf8:
            p += 2 if data[p] & 0x80 else 1           # length in characters, unused
            n = data[p]
            if n & 0x80:
                n = ((n & 0x7F) << 8) | data[p + 1]
                p += 1
            strings.append(data[p + 1:p + 1 + n].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", data, p)[0]
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, p + 2)[0]
                p += 2
            strings.append(data[p + 2:p + 2 + n * 2].decode("utf-16le", "replace"))
    return strings


def parse_manifest(axml: bytes) -> tuple[dict, list[str]]:
    """(manifest attributes, permissions) from a binary AndroidManifest.xml.

    Permissions include <uses-permission> names and the `permission` guarding any component
    (that's how accessibility services and device admins show up).
    """
    pos = struct.unpack_from("<H", axml, 2)[0]  # skip the XML chunk header
    strings: list[str] = []
    manifest: dict = {}
    permissions: list[str] = []
    while pos < len(axml):
        chunk_type, header_size, size = struct.unpack_from("<HHI", axml, pos)
        if chunk_type == 0x0001:
            strings = _string_pool(axml, pos)
        elif chunk_type == 0x0102:
            name = strings[struct.unpack_from("<I", axml, pos + 20)[0]]
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, pos + 24)
            attrs = {}
            for i in range(attr_count):
                a = pos + 16 + attr_start + i * attr_size
                _, a_name, raw, _, _, data_type, value = struct.unpack_from("<IIIHBBI", axml, a)
                key = strings[a_name] if a_name < len(strings) else ""
                attrs[key] = strings[raw] if raw != 0xFFFFFFFF else (value if data_type in (0x10, 0x11) else raw)
            if name == "manifest" and not manifest:
                manifest = attrs
            elif name in ("uses-permission", "uses-permission-sdk-23") and isinstance(attrs.get("name"), str):
                permissions.append(attrs["name"])
            elif isinstance(attrs.get("permission"), str):
                permissions.append(attrs["permission"])
        pos += size if size else header_size
    return manifest, sorted(set(permissions))


# --- signatures ------------------------------------------------------------------------------

def _prefixed(buf: bytes, pos: int) -> tuple[bytes, int]:
    n = struct.unpack_from("<I", buf, pos)[0]
    return buf[pos + 4:pos + 4 + n], pos + 4 + n


def signing_certificates(apk: bytes) -> tuple[list[str], list[bytes]]:
    """(schemes, DER certificates) from the APK Signing Block. Empty for v1-only or unsigned APKs."""
    eocd = apk.rfind(b"PK\x05\x06")
    if eocd < 0:
        return [], []
    cd_offset = struct.unpack_from("<I", apk, eocd + 16)[0]
    if apk[cd_offset - 16:cd_offset] != _SIG_BLOCK_MAGIC:
        return [], []
    size = struct.unpack_from("<Q", apk, cd_offset - 24)[0]
    block = apk[cd_offset - size - 8:cd_offset - 24]
    schemes, certs, pos = [], [], 8
    while pos < len(block):
        length, pair_id = struct.unpack_from("<QI", block, pos)
        value = block[pos + 12:pos + 8 + length]
        pos += 8 + length
        if pair_id not in _SCHEMES:
            continue
        schemes.append(_SCHEMES[pair_id])
        if certs:
            continue  # every scheme carries the same signer certificates
        signers, _ = _prefixed(value, 0)
        p = 0
        while p < len(signers):
            signer, p = _prefixed(signers, p)
            signed_data, _ = _prefixed(signer, 0)
            _, q = _prefixed(signed_data, 0)          # digests
            cert_seq, _ = _prefixed(signed_data, q)
            c = 0
            while c < len(cert_seq):
                cert, c = _prefixed(cert_seq, c)
                certs.append(cert)
    return schemes, certs


def certificate_subject(der: bytes) -> str:
    """Human-readable owner of a certificate, via keytool (JDK) or openssl when available."""
    with tempfile.NamedTemporaryFile(suffix=".der", delete=False) as fh:
        fh.write(der)
        path = fh.name
    try:
        if keytool := shutil.which("keytool"):
            out = subprocess.run([keytool, "-printcert", "-file", path], capture_output=True, text=True).stdout
            for line in out.splitlines():
                if line.strip().startswith(("Owner:", "Eigenaar:")):
                    return line.split(":", 1)[1].strip()
        if openssl := shutil.which("openssl"):
            out = subprocess.run([openssl, "x509", "-inform", "DER", "-in", path, "-noout", "-subject"],
                                 capture_output=True, text=True).stdout
            return out.strip().removeprefix("subject=").strip()
        return "(install a JDK or openssl to show the certificate owner)"
    finally:
        Path(path).unlink(missing_ok=True)


# --- files -----------------------------------------------------------------------------------

def _apks_in(path: Path) -> list[tuple[str, bytes]]:
    if path.suffix.lower() == ".apk":
        return [(path.name, path.read_bytes())]
    with zipfile.ZipFile(path) as bundle:
        return [(n, bundle.read(n)) for n in bundle.namelist() if n.lower().endswith(".apk")]


def inspect(path: Path) -> dict:
    infos: list[ApkInfo] = []
    subjects: dict[str, str] = {}
    for name, data in _apks_in(path):
        info = ApkInfo(file=name)
        info.schemes, certs = signing_certificates(data)
        for der in certs:
            digest = hashlib.sha256(der).hexdigest()
            info.cert_sha256.append(digest)
            if digest not in subjects:
                subjects[digest] = certificate_subject(der)
        with zipfile.ZipFile(io.BytesIO(data)) as apk:
            if "AndroidManifest.xml" in apk.namelist():
                manifest, info.permissions = parse_manifest(apk.read("AndroidManifest.xml"))
                info.package = str(manifest.get("package", ""))
                info.version_name = str(manifest.get("versionName", ""))
                info.version_code = str(manifest.get("versionCode", ""))
        infos.append(info)
    base = next((i for i in infos if i.version_name or i.permissions), infos[0] if infos else ApkInfo(file=""))
    signer_sets = {tuple(i.cert_sha256) for i in infos}
    return {
        "file": str(path),
        "package": base.package,
        "version_name": base.version_name,
        "version_code": base.version_code,
        "apks": [i.__dict__ for i in infos],
        "signers": {d: subjects[d] for d in subjects},
        "same_signer_for_all": len(signer_sets) == 1 and () not in signer_sets,
        "notable_permissions": sorted(p for p in base.permissions if p in NOTABLE_PERMISSIONS),
        "permissions": base.permissions,
    }


def extract_bundle(path: Path, target: Path) -> list[Path]:
    """Write the APKs of a .xapk/.apks bundle to `target` for `adb install-multiple`."""
    target.mkdir(parents=True, exist_ok=True)
    files = []
    for name, data in _apks_in(path):
        out = target / Path(name).name
        out.write_bytes(data)
        files.append(out)
    return files


def to_text(result: dict) -> str:
    lines = [f"package: {result['package']}  version: {result['version_name']} ({result['version_code']})"]
    for apk in result["apks"]:
        signer = ", ".join(d[:16] + "..." for d in apk["cert_sha256"]) or "UNSIGNED / v1 only"
        lines.append(f"  {apk['file']}: {'+'.join(apk['schemes']) or '-'} signer {signer}")
    for digest, subject in result["signers"].items():
        lines.append(f"signer {digest}: {subject}")
    lines.append("all APKs signed by the same key: " + ("yes" if result["same_signer_for_all"] else "NO"))
    notable = result["notable_permissions"]
    lines.append("permissions of note: " + (", ".join(notable) if notable else "none"))
    lines.append(f"all permissions ({len(result['permissions'])}): " + json.dumps(result["permissions"]))
    return "\n".join(lines)
