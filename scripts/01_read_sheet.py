"""Read every row of the Quote DB tab and print it.

The quickest way to confirm the Google OAuth flow and the sheet wiring work end to end,
before involving the app or any model call.

Usage: uv run python scripts/01_read_sheet.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from landed.config import TAB_NAME  # noqa: E402
from landed.sheets import read_all  # noqa: E402

rows = read_all()
print(f"{len(rows)} data rows in {TAB_NAME}\n")
widths = [26, 11, 38, 6, 9, 8, 40, 11]
for i, row in enumerate(rows, start=2):
    cells = [str(v)[:w].ljust(w) for v, w in zip(row.values(), widths)]
    print(f"{i:>3}  " + "  ".join(cells))
