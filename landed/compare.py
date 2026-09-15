"""Month scoping, decision/history split, comparison table and trend strip.

Everything here is built in Python from the rows actually read from the sheet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from .config import CANONICAL_ITEMS, SHEET_COLUMNS
from .convert import D

# The sheet column holding the landed cost, by position rather than by its
# wording, so renaming it in SHEET_COLUMNS does not break the comparison.
LANDED_COLUMN = SHEET_COLUMNS[4]

DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d %B %Y")

Month = tuple[int, int]


def parse_quote_date(text: str) -> date:
    text = (text or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised quote date in the sheet: {text!r}")


def month_of(d: date) -> Month:
    return (d.year, d.month)


def month_label(month: Month) -> str:
    return date(month[0], month[1], 1).strftime("%B %Y")


def short_month(d: date) -> str:
    return d.strftime("%b %Y")


def enrich(rows: list[dict]) -> list[dict]:
    """Attach the parsed date, its month and the Decimal landed cost to each sheet row."""
    out = []
    for row in rows:
        r = dict(row)
        r["_date"] = parse_quote_date(row["Quote date"])
        r["_month"] = month_of(r["_date"])
        r["_landed"] = D(row[LANDED_COLUMN].replace(",", ""))
        out.append(r)
    return out


def available_months(rows: list[dict]) -> list[Month]:
    """Distinct months present in the sheet, most recent first."""
    return sorted({r["_month"] for r in rows}, reverse=True)


def split_rows(rows: list[dict], month: Month) -> tuple[list[dict], list[dict]]:
    """Decision set: rows in the month. History: rows strictly before it. Later rows are dropped."""
    decision = [r for r in rows if r["_month"] == month]
    history = [r for r in rows if r["_month"] < month]
    return decision, history


def public_rows(rows: list[dict]) -> list[dict]:
    """Rows as sent to the model: the sheet columns only, nothing derived."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def _item_order(items: set[str]) -> list[str]:
    known = [i for i in CANONICAL_ITEMS if i in items]
    other = sorted(i for i in items if i not in CANONICAL_ITEMS)
    return known + other


@dataclass
class ComparisonTable:
    items: list[str]
    vendors: list[str]
    units: dict[str, str]
    cells: dict[tuple[str, str], Decimal | None]
    cheapest: dict[str, set[str]] = field(default_factory=dict)

    @property
    def single_vendor(self) -> bool:
        return len(self.vendors) <= 1

    def wins(self) -> dict[str, int]:
        counts = {v: 0 for v in self.vendors}
        for winners in self.cheapest.values():
            for v in winners:
                counts[v] += 1
        return counts


def build_table(decision: list[dict]) -> ComparisonTable:
    """One row per item quoted in the month, one column per vendor that quoted."""
    vendors = sorted({r["Vendor name"] for r in decision})
    items = _item_order({r["Item"] for r in decision})
    units: dict[str, str] = {}
    latest: dict[tuple[str, str], dict] = {}
    for r in decision:
        key = (r["Item"], r["Vendor name"])
        if key not in latest or r["_date"] > latest[key]["_date"]:
            latest[key] = r
        units.setdefault(r["Item"], r["Base unit"])
    cells = {
        (item, vendor): (latest[(item, vendor)]["_landed"] if (item, vendor) in latest else None)
        for item in items
        for vendor in vendors
    }
    table = ComparisonTable(items=items, vendors=vendors, units=units, cells=cells)
    if len(vendors) > 1:
        for item in items:
            quoted = {v: cells[(item, v)] for v in vendors if cells[(item, v)] is not None}
            if len(quoted) > 1:
                low = min(quoted.values())
                table.cheapest[item] = {v for v, value in quoted.items() if value == low}
    return table


@dataclass
class Trend:
    item: str
    vendor: str
    earlier_quotes: int
    first: Decimal | None = None
    first_when: str | None = None
    last: Decimal | None = None
    last_when: str | None = None
    this_month: Decimal | None = None

    @property
    def available(self) -> bool:
        return self.earlier_quotes >= 2

    @property
    def change_percent(self) -> Decimal | None:
        if not self.available or not self.first:
            return None
        return (self.last - self.first) / self.first * 100


def build_trends(decision: list[dict], history: list[dict]) -> list[Trend]:
    """For each item in the decision set, each vendor's movement across its earlier quotes."""
    table = build_table(decision)
    trends = []
    for item in table.items:
        for vendor in table.vendors:
            earlier = sorted(
                (r for r in history if r["Item"] == item and r["Vendor name"] == vendor),
                key=lambda r: r["_date"],
            )
            trend = Trend(item=item, vendor=vendor, earlier_quotes=len(earlier))
            trend.this_month = table.cells[(item, vendor)]
            if earlier:
                trend.first = earlier[0]["_landed"]
                trend.first_when = short_month(earlier[0]["_date"])
            if len(earlier) >= 2:
                trend.last = earlier[-1]["_landed"]
                trend.last_when = short_month(earlier[-1]["_date"])
            trends.append(trend)
    return trends


def split_headline(text: str) -> tuple[str | None, str | None, str]:
    """Pull the 'Headline: figure | caption' line off the model's prose, if present."""
    lines = text.strip().splitlines()
    if lines and lines[0].strip().lower().startswith("headline:"):
        content = lines[0].split(":", 1)[1].strip()
        figure, _, caption = content.partition("|")
        body = "\n".join(lines[1:]).strip()
        return figure.strip() or None, caption.strip() or None, body
    return None, None, text.strip()
