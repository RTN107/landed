"""Rehearsal mode. Runs the app with all three paid model calls and the sheet write replaced
by fixtures, so the whole flow can be walked through without spending tokens or touching
the sheet. Sheet reads come from scripts/fixtures/quote_db.json (a dump of Quote DB).

Needs no API key, no Google credentials and no particular PDF: the extraction is served from
a fixture regardless of what you upload, so any PDF will take you through the whole flow.

Usage: uv run python scripts/run_offline.py [--port 8501] [--fast] [--headless]
  --fast      skip the artificial delays that stand in for model latency
  --headless  do not open a browser window
"""

import copy
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from landed import claude, sheets  # noqa: E402
from landed.config import SHEET_COLUMNS  # noqa: E402

FIXTURES = ROOT / "scripts" / "fixtures"
EXTRACTION = json.loads((FIXTURES / "metro_extraction.json").read_text(encoding="utf-8"))
DB = json.loads((FIXTURES / "quote_db.json").read_text(encoding="utf-8"))
DELAY = 0.0 if "--fast" in sys.argv else 4.0

CANNED_PROSE = """Headline: Rs 2.70 per roll | Metro undercuts Vector on tissue

Metro Housekeeping is the cheapest quote on three of the four items this month: toilet tissue at Rs 14.20 a roll against Vector's Rs 15.90 and Ace's Rs 16.90, floor cleaner at Rs 50.50 a litre against Rs 56.50 and Rs 59.00, and hand wash at Rs 66.00 a litre against Rs 73.00 and Rs 78.00. Gloves are the exception: Ace Hospitality Supplies is cheapest at Rs 2.02 a piece, with Metro dearest at Rs 2.65. Splitting the order, three items to Metro and gloves to Ace, is the recommendation.

The history shows Ace drifting upward on every item since April, with tissue moving from Rs 15.40 to Rs 16.90 and hand wash from Rs 72.00 to Rs 78.00, and its September quote simply repeats August. Vector has risen more gently and remains below Ace throughout. Metro has no history in this sheet, so its September position cannot yet be read as a trend; it is a single quote.

The notes matter. Ace has delivered on every order placed and has confirmed that part orders are accepted at the quoted rates, so moving gloves alone to Ace carries no penalty. Vector's June tissue order arrived with 6% of the cases damaged, which is worth remembering if Metro's tissue disappoints. Metro has no delivery record with the hotel, so a first order should be watched.

Next month, look for whether Metro holds its rates once it has an order in hand, and whether Ace responds on the three items it has just lost."""


def fake_extract(pdf_bytes: bytes) -> dict:
    time.sleep(DELAY)
    return copy.deepcopy(EXTRACTION)


def fake_resubmit(previous: dict, comment: str) -> dict:
    time.sleep(DELAY * 0.75)
    revised = copy.deepcopy(previous)
    changes = []
    number = re.search(r"\b(\d{2,4})\b", comment)
    for line in revised["line_items"]:
        if line.get("spec_qualifier_label") and line.get("spec_qualifier") is None and number:
            line["spec_qualifier"] = float(number.group(1))
            changes.append(f"spec_qualifier for {line['item_name']} set to {number.group(1)} from user input")
    if not changes:
        changes.append("No change applied: the comment did not supply a value for any field.")
    revised["changes_made"] = changes
    return revised


def fake_analyse(month_label: str, decision_rows: list[dict], history_rows: list[dict]) -> str:
    time.sleep(DELAY)
    vendors = sorted({r["Vendor name"] for r in decision_rows})
    if len(vendors) <= 1:
        who = vendors[0] if vendors else "no vendor"
        return (
            f"Headline: One vendor | no comparison is possible for {month_label}\n\n"
            f"Only {who} quoted in {month_label}, so there is nothing to compare it against. "
            "Its four quotes stand on their own this month.\n\n"
            "With no earlier quotes in the sheet, there is no trend to read either. "
            "This month's figures become the baseline for everything that follows."
        )
    if month_label != "September 2026":
        return (
            f"Headline: {len(vendors)} vendors | quoted in {month_label}\n\n"
            f"Rehearsal text for {month_label}. The comparison table above is built from the sheet; "
            "this prose is a placeholder used only in offline mode."
        )
    return CANNED_PROSE


def fake_read_all() -> list[dict]:
    return copy.deepcopy(DB)


def fake_append(rows: list[list]) -> dict:
    for row in rows:
        DB.append({k: (f"{v:.2f}" if isinstance(v, float) else str(v)) for k, v in zip(SHEET_COLUMNS, row)})
    return {"updatedRows": len(rows), "updatedRange": f"'Quote DB'!A{len(DB) - len(rows) + 2}:H{len(DB) + 1}"}


claude.extract_quotation = fake_extract
claude.resubmit = fake_resubmit
claude.analyse = fake_analyse
sheets.read_all = fake_read_all
sheets.append_rows = fake_append

if __name__ == "__main__":
    from streamlit.web import bootstrap

    port = 8501
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    options = {"server.port": port, "server.headless": "--headless" in sys.argv}
    bootstrap.load_config_options(flag_options=options)
    bootstrap.run(str(ROOT / "app.py"), False, [], options)
