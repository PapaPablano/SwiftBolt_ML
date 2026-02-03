#!/usr/bin/env python3
"""
Wrapper to run ml/scripts/backfill_ohlc_d1_alpaca.py from repo root.

Usage (from repo root):
    python scripts/backfill_ohlc_d1_alpaca.py --symbols PG KO JNJ MRK MSFT AMGN BRK.B NVDA MU ALB --start 2020-01-01 --end 2026-02-02

Or from ml/:
    cd ml && python scripts/backfill_ohlc_d1_alpaca.py --symbols PG KO ... --start 2020-01-01 --end 2026-02-02
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ML_SCRIPT = REPO_ROOT / "ml" / "scripts" / "backfill_ohlc_d1_alpaca.py"


def main():
    if not ML_SCRIPT.exists():
        print(f"Not found: {ML_SCRIPT}", file=sys.stderr)
        sys.exit(1)
    os.chdir(REPO_ROOT / "ml")
    sys.exit(subprocess.call([sys.executable, str(ML_SCRIPT)] + sys.argv[1:]))


if __name__ == "__main__":
    main()
