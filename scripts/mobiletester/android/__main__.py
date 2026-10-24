"""`python -m mobiletester.android`: adt when installed with `uv tool install` instead of run from scripts/adt.py."""

import sys

from mobiletester.android.cli import main

if __name__ == "__main__":
    sys.exit(main())
