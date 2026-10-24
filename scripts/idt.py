# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11", "pyyaml>=6"]
# ///
"""Entry point: `uv run --script scripts/idt.py <command>`. See `--help`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mobiletester.ios.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
