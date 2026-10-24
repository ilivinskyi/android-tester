"""adt - Android device tool used by the android-tester skills."""

from pathlib import Path


def entry_script() -> Path:
    """The file that starts adt, for the times it starts itself (recording worker, hooks).

    scripts/adt.py in a checkout or the Claude Code plugin; adtlib/__main__.py when installed as a tool.
    """
    script = Path(__file__).resolve().parent.parent / "adt.py"
    return script if script.is_file() else Path(__file__).resolve().parent / "__main__.py"
