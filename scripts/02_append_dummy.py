"""Append one dummy row to the Quote DB tab and confirm it arrives.

Confirms write access, separately from read access, before trusting the app with a real
quotation. The row is left in place by default so you can see it in the sheet yourself.
Pass --cleanup to have the script delete the exact row it just wrote.

Usage: uv run python scripts/02_append_dummy.py [--cleanup]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from landed.config import SHEET_ID, TAB_NAME  # noqa: E402
from landed.sheets import _service, append_rows, read_all  # noqa: E402

DUMMY = [
    "DUMMY - delete me",
    "01/01/2000",
    "Dummy item",
    "piece",
    0.01,
    1,
    "written by scripts/02_append_dummy.py",
    "",
]

before = len(read_all())
updates = append_rows([DUMMY])
print("append response:", updates)
after = read_all()
print(f"rows before: {before}, after: {len(after)}")
last = after[-1]
assert last["Vendor name"] == DUMMY[0], f"last row is not the dummy: {last}"
print("dummy row confirmed at sheet row", len(after) + 1)

if "--cleanup" in sys.argv:
    service = _service()
    meta = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    sheet_id = next(s["properties"]["sheetId"] for s in meta["sheets"] if s["properties"]["title"] == TAB_NAME)
    row_index = len(after)  # zero-based index of the last data row; the header is index 0
    service.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": row_index,
                            "endIndex": row_index + 1,
                        }
                    }
                }
            ]
        },
    ).execute()
    print(f"dummy row deleted; rows now: {len(read_all())}")
else:
    print("delete the dummy row manually (or rerun with --cleanup)")
