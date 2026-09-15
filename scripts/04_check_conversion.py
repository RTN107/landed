"""Check the landed cost arithmetic against known-good figures, offline.

Runs the conversion over the reference extraction in scripts/fixtures and asserts every
intermediate value, not just the final rate: base units, gross, net, freight, taxable and
the landed cost, plus the blocked state of the tissue line, the totals cross-check, the
rows that would be written to the sheet, the resubmission path, and the GST-inclusive
branch. Costs nothing to run and needs no credentials.

Usage: uv run python scripts/04_check_conversion.py
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from landed.config import TAB_NAME  # noqa: E402
from landed.convert import convert_quotation, diff_lines, round2, sheet_rows  # noqa: E402

extraction = json.loads((Path(__file__).parent / "fixtures" / "metro_extraction.json").read_text())
result = convert_quotation(extraction)

expected = {
    "Toilet Tissue Roll": ("2000", "29000", "27550", "850", "28400", "14.20", "blocked_incomparable"),
    "Floor Cleaner, Ready to Use": ("200", "11000", "9900", "200", "10100", "50.50", "clear"),
    "Hand Wash Liquid": ("100", "7500", "6600", "0", "6600", "66.00", "clear"),
    "Nitrile Gloves, Powder Free": ("5000", "13000", "13000", "250", "13250", "2.65", "clear"),
}

failures = 0
for line in result.lines:
    exp = expected[line.item_name]
    got = (line.base_units, line.gross, line.net, line.freight, line.taxable, round2(line.landed), line.state)
    ok = all(
        (g == Decimal(e)) if isinstance(g, Decimal) else (g == e)
        for g, e in zip(got, exp)
    )
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  {line.item_name}")
    print(f"      read:    {' | '.join(line.read_parts)}")
    print(f"      working: {line.working}")
    print(f"      landed:  Rs {round2(line.landed):.2f} per {line.base_unit}   state={line.state}")
    if line.explanation:
        print(f"      note:    {line.explanation}")
    if not ok:
        print(f"      expected {exp}\n      got      {got}")

print()
print(f"cross-check: {result.cross_check.status} - {result.cross_check.detail}")
failures += 0 if result.cross_check.status == "passed" else 1
failures += 0 if result.cross_check.line_sum == Decimal("58350") else 1

rows, skipped = sheet_rows(extraction, result)
print(f"\nrows for {TAB_NAME}:")
for row in rows:
    print("  ", row)
print("skipped:", skipped)
failures += 0 if len(rows) == 4 and not skipped else 1

# Resubmit simulation: pulls per roll supplied -> tissue row clears and is the only change.
fixed = json.loads(json.dumps(extraction))
fixed["line_items"][0]["spec_qualifier"] = 300
result2 = convert_quotation(fixed)
changed = diff_lines(result, result2)
print("\nafter supplying 300 pulls per roll:", result2.lines[0].state, "| changed rows:", changed)
failures += 0 if result2.lines[0].state == "clear" and changed == {"Toilet Tissue Roll"} else 1
failures += 0 if result2.all_clear else 1

# GST-inclusive path: 725 incl. 18% -> 614.41 ex-GST
inclusive = json.loads(json.dumps(fixed))
inclusive["gst_treatment"] = "inclusive"
line = convert_quotation(inclusive).lines[0]
print("inclusive path working:", line.working, "->", f"{round2(line.landed):.2f}")
failures += 0 if line.working.startswith("(614.41") else 1

print("\nALL CHECKS PASSED" if failures == 0 else f"\n{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
