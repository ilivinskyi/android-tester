# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11"]
# ///
"""Entry point: `uv run --script scripts/adt.py <command>`. See `--help`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from adtlib.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
