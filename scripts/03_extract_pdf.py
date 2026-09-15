"""Run the extraction call against a quotation PDF and print the raw JSON it returns.

Usage: uv run python scripts/03_extract_pdf.py "<path to quotation pdf>"

No sample quotation ships with this repository, so pass the path to your own. Note that the
extraction schema only accepts the three vendors named in landed/schema.py, so a quotation
from anyone else will not validate without editing that file first.

If the PDF happens to be the Metro Housekeeping quotation this project was built against,
the result is also checked field by field against scripts/fixtures/metro_extraction.json and
any difference is printed.

Requires ANTHROPIC_API_KEY in .env, since this makes a real (paid) model call.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from landed.claude import extract_quotation  # noqa: E402

if len(sys.argv) < 2:
    sys.exit('Usage: uv run python scripts/03_extract_pdf.py "<path to quotation pdf>"')

pdf_path = Path(sys.argv[1])
if not pdf_path.is_file():
    sys.exit(f"No such file: {pdf_path}")

print("reading", pdf_path)
extraction = extract_quotation(pdf_path.read_bytes())
print(json.dumps(extraction, indent=2, ensure_ascii=False))

expected = json.loads((Path(__file__).parent / "fixtures" / "metro_extraction.json").read_text())
if extraction.get("quote_number") == expected["quote_number"]:
    mismatches = []
    for key, value in expected.items():
        if key != "line_items" and extraction.get(key) != value:
            mismatches.append(f"{key}: expected {value!r}, got {extraction.get(key)!r}")
    got_lines = extraction.get("line_items", [])
    if len(got_lines) != len(expected["line_items"]):
        mismatches.append(f"line item count: expected {len(expected['line_items'])}, got {len(got_lines)}")
    for i, (exp_line, got_line) in enumerate(zip(expected["line_items"], got_lines), start=1):
        for key, value in exp_line.items():
            if key in ("confidence", "confidence_reason"):
                continue
            if got_line.get(key) != value:
                mismatches.append(f"line {i} {key}: expected {value!r}, got {got_line.get(key)!r}")
    print(
        "\nMATCHES THE REFERENCE EXTRACTION"
        if not mismatches
        else "\nDIFFERS FROM THE REFERENCE EXTRACTION:\n  " + "\n  ".join(mismatches)
    )
