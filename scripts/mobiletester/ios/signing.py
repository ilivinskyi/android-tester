"""The Apple development team that signs the runner for real devices.

Simulators run the runner unsigned; a device only runs code signed by a team it trusts. The team is the
user's, so idt never picks one: the user names it once (`idt runner build --team ID`) and idt remembers it
for this Mac. Xcode's signed-in accounts are offered as hints only.
"""

from __future__ import annotations

import os
import plistlib
import re
import subprocess
from pathlib import Path

from ..core import state

TEAM_ID = re.compile(r"^[A-Z0-9]{10}$")


class MissingTeam(Exception):
    """No team is known: a decision only the user can make."""


def settings_file() -> Path:
    base = Path(os.environ.get("MT_CONFIG_HOME", Path.home() / "Library" / "Application Support" / "mobile-tester"))
    return base / "ios-signing.json"


def team() -> str | None:
    """MT_IOS_TEAM, else the team saved by `idt runner build --team`."""
    return os.environ.get("MT_IOS_TEAM") or (state.read_json(settings_file()) or {}).get("team")


def save_team(team_id: str) -> str:
    team_id = team_id.strip().upper()
    if not TEAM_ID.match(team_id):
        raise ValueError(f"'{team_id}' is not a team id: it is 10 letters and digits, e.g. AB12CD34EF "
                         "(Xcode > Settings > Accounts, or developer.apple.com > Membership)")
    state.write_json(settings_file(), {"team": team_id})
    return team_id


def parse_xcode_teams(prefs: dict) -> list[dict]:
    """Teams of the accounts signed in to Xcode, from its preferences: [{id, name, free}]."""
    teams = {}
    for account_teams in (prefs.get("IDEProvisioningTeamByIdentifier") or {}).values():
        for t in account_teams:
            if t.get("teamID"):
                teams[t["teamID"]] = {"id": t["teamID"], "name": t.get("teamName", ""),
                                      "free": bool(t.get("isFreeProvisioningTeam"))}
    return sorted(teams.values(), key=lambda t: (t["free"], t["name"]))


def xcode_teams() -> list[dict]:
    proc = subprocess.run(["defaults", "export", "com.apple.dt.Xcode", "-"], capture_output=True)
    if proc.returncode != 0:
        return []
    try:
        return parse_xcode_teams(plistlib.loads(proc.stdout))
    except plistlib.InvalidFileException:
        return []


def missing_team_message() -> str:
    teams = xcode_teams()
    hint = ("teams of the accounts in Xcode: " + ", ".join(
        f"{t['id']} ({t['name']}{', free personal team' if t['free'] else ''})" for t in teams)) if teams else (
        "no account is signed in to Xcode: the user adds their Apple ID in Xcode > Settings > Accounts first")
    return ("a real device needs the runner signed by the user's Apple development team. Ask the user for "
            f"their team id (never pick one yourself), then run `idt runner build --team ID`; {hint}")
