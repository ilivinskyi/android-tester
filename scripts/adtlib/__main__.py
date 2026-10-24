"""`python -m adtlib`: adt when installed as a tool (`uv tool install`) instead of run from scripts/adt.py."""

import sys

from adtlib.cli import main

if __name__ == "__main__":
    sys.exit(main())
