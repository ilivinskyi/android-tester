"""`python -m mobiletester.ios`: idt when installed with `uv tool install` instead of run from scripts/idt.py."""

import sys

from mobiletester.ios.cli import main

if __name__ == "__main__":
    sys.exit(main())
