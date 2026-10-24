"""idt - iOS device tool used by the mobile-tester skills (simulators; real devices later)."""

from pathlib import Path


def entry_script() -> Path:
    """The file that starts idt, for the times it starts itself (hooks).

    scripts/idt.py in a checkout or the Claude Code plugin; ios/__main__.py when installed as a tool.
    """
    script = Path(__file__).resolve().parents[2] / "idt.py"
    return script if script.is_file() else Path(__file__).resolve().parent / "__main__.py"
