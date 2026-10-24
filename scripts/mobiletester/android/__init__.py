"""adt - Android device tool used by the mobile-tester skills."""

from pathlib import Path


def entry_script() -> Path:
    """The file that starts adt, for the times it starts itself (recording worker, hooks).

    scripts/adt.py in a checkout or the Claude Code plugin; android/__main__.py when installed as a tool.
    """
    script = Path(__file__).resolve().parents[2] / "adt.py"
    return script if script.is_file() else Path(__file__).resolve().parent / "__main__.py"
