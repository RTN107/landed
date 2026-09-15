"""Conversion of extracted line items to landed cost per base unit.

All arithmetic is decimal.Decimal. Nothing is rounded until display or write.
The model never computes a landed cost; everything here is Python.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .config import CURRENCY_SYMBOL, ITEM_NAME_MAP, PLURALS, SPEC_REFERENCE, TAX_NAME

TWO_PLACES = Decimal("0.01")
ONE = Decimal(1)
HUNDRED = Decimal(100)

CLEAR = "clear"
BLOCKED_UNCOMPUTABLE = "blocked_uncomputable"
BLOCKED_INCOMPARABLE = "blocked_incomparable"
LOW_CONFIDENCE = "low_confidence"

# Display plurals come from config; anything missing just gets an "s".
PACK_PLURALS = PLURALS
UNIT_PLURALS = PLURALS

FIELD_DESCRIPTIONS = {
    "quoted_rate": "The quoted rate",
    "pack_quantity": "The number of packs",
    "units_per_pack": "The number of base units per pack",
    "discount_percent": "The discount",
    "freight_value": "The freight charge",
}


def D(value) -> Decimal | None:
    """Decimal from a JSON number without float artefacts. None stays None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round2(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def fmt_money(value: Decimal) -> str:
    """28400 -> '28,400.00'. Rounds only for display."""
    return f"{round2(value):,.2f}"


def fmt_qty(value: Decimal) -> str:
    """2000 -> '2,000'; 12.5 -> '12.5'."""
    if value == value.to_integral_value():
        return f"{int(value):,}"
    return f"{value.normalize():,f}"


def fmt_factor(discount_percent: Decimal) -> str:
    """5 -> '0.95'; 12.5 -> '0.875'. At least two decimals."""
    factor = ONE - discount_percent / HUNDRED
    text = format(factor.normalize(), "f")
    if "." not in text or len(text.split(".")[1]) < 2:
        text = f"{factor.quantize(TWO_PLACES):f}"
    return text


def plural(word: str, count: Decimal, table: dict[str, str]) -> str:
    return word if count == 1 else table.get(word, word + "s")


@dataclass
class LineResult:
    item_name: str
    base_unit: str
    state: str
    confidence: str
    confidence_reason: str | None
    base_units: Decimal | None = None
    gross: Decimal | None = None
    net: Decimal | None = None
    freight: Decimal | None = None
    taxable: Decimal | None = None
    landed: Decimal | None = None
    landed_comparable: Decimal | None = None
    normalisation_factor: Decimal | None = None
    read_parts: list[str] = field(default_factory=list)
    working: str | None = None
    explanation: str | None = None
    attention: bool = False
    canonical_item: str | None = None

    @property
    def status_label(self) -> str:
        return {
            CLEAR: "clear",
            BLOCKED_UNCOMPUTABLE: "blocked",
            BLOCKED_INCOMPARABLE: "blocked",
            LOW_CONFIDENCE: "low confidence",
        }[self.state]


@dataclass
class CrossCheck:
    status: str  # passed | failed | incomplete
    line_sum: Decimal | None
    taxable_value: Decimal | None
    summary_holds: bool | None
    detail: str


@dataclass
class QuotationResult:
    lines: list[LineResult]
    cross_check: CrossCheck

    @property
    def all_clear(self) -> bool:
        return all(line.state == CLEAR and not line.attention for line in self.lines)


def convert_line(item: dict, gst_treatment: str, gst_rate_percent) -> LineResult:
    """One line item to landed cost, following the five steps in the fixed order."""
    result = LineResult(
        item_name=item["item_name"],
        base_unit=item["base_unit"],
        state=CLEAR,
        confidence=item.get("confidence", "high"),
        confidence_reason=item.get("confidence_reason"),
        canonical_item=ITEM_NAME_MAP.get(item["item_name"]),
    )

    quoted_rate = D(item.get("quoted_rate"))
    pack_quantity = D(item.get("pack_quantity"))
    units_per_pack = D(item.get("units_per_pack"))
    discount_percent = D(item.get("discount_percent"))
    freight_type = item.get("freight_type")
    freight_value = D(item.get("freight_value"))
    spec_qualifier = D(item.get("spec_qualifier"))
    spec_label = item.get("spec_qualifier_label")
    pack_unit = item.get("pack_unit", "pack")
    base_unit = item["base_unit"]

    if freight_type == "included":
        freight_value = Decimal(0)

    # Optional pre-step: strip the tax when the quoted figures include it.
    gst_stripped = False
    if gst_treatment == "inclusive":
        divisor = ONE + D(gst_rate_percent) / HUNDRED
        if quoted_rate is not None:
            quoted_rate = quoted_rate / divisor
        if freight_value is not None:
            freight_value = freight_value / divisor
        gst_stripped = True

    # What was read, as separate fragments.
    parts = []
    if pack_quantity is not None and quoted_rate is not None:
        parts.append(
            f"{fmt_qty(pack_quantity)} {plural(pack_unit, pack_quantity, PACK_PLURALS)}"
            f" @ {CURRENCY_SYMBOL} {fmt_money(quoted_rate)}"
        )
    if units_per_pack is not None:
        parts.append(f"{fmt_qty(units_per_pack)} {plural(base_unit, units_per_pack, UNIT_PLURALS)} per {pack_unit}")
    else:
        parts.append(f"{UNIT_PLURALS.get(base_unit, base_unit)} per {pack_unit} not stated")
    if discount_percent is not None:
        parts.append(f"{fmt_qty(discount_percent)}% discount" if discount_percent else "no discount")
    if freight_type == "included":
        parts.append("freight included")
    elif freight_type == "per_unit" and freight_value is not None:
        parts.append(f"freight {CURRENCY_SYMBOL} {fmt_money(freight_value)} per {base_unit}")
    elif freight_type == "flat" and freight_value is not None:
        parts.append(f"freight {CURRENCY_SYMBOL} {fmt_money(freight_value)} flat")
    if spec_label:
        if spec_qualifier is not None:
            parts.append(f"{fmt_qty(spec_qualifier)} {spec_label}")
        else:
            parts.append(f"{spec_label} not stated")
    if gst_stripped:
        parts.append(f"quoted incl. {fmt_qty(D(gst_rate_percent))}% {TAX_NAME}, stripped")
    result.read_parts = parts

    # Blocking rule 1: arithmetic impossible.
    required = {
        "quoted_rate": quoted_rate,
        "pack_quantity": pack_quantity,
        "units_per_pack": units_per_pack,
        "discount_percent": discount_percent,
        "freight_value": freight_value,
    }
    for name, value in required.items():
        if value is None:
            result.state = BLOCKED_UNCOMPUTABLE
            what = FIELD_DESCRIPTIONS[name]
            if name == "units_per_pack":
                what = f"The number of {UNIT_PLURALS.get(base_unit, base_unit)} per {pack_unit}"
            result.explanation = f"{what} is not printed on this quotation, so no landed cost can be worked out."
            return result

    # The five steps, in this exact order.
    base_units = pack_quantity * units_per_pack
    gross = quoted_rate * pack_quantity
    net = gross * (ONE - discount_percent / HUNDRED)
    if freight_type == "flat":
        freight = freight_value
    elif freight_type == "per_unit":
        freight = freight_value * base_units
    else:
        freight = Decimal(0)
    taxable = net + freight
    landed = taxable / base_units

    result.base_units = base_units
    result.gross = gross
    result.net = net
    result.freight = freight
    result.taxable = taxable
    result.landed = landed

    # The working, as one readable string.
    working = f"{fmt_money(quoted_rate)} × {fmt_qty(pack_quantity)}"
    if discount_percent:
        working += f" × {fmt_factor(discount_percent)}"
    if freight_type == "flat":
        working += f" + {fmt_money(freight_value)}"
    elif freight_type == "per_unit":
        working += f" + {fmt_money(freight_value)} × {fmt_qty(base_units)}"
    result.working = f"({working}) ÷ {fmt_qty(base_units)}"

    # Spec qualifier normalisation to the recorded reference.
    reference = SPEC_REFERENCE.get(spec_label) if spec_label else None
    if spec_label and spec_qualifier is not None and reference:
        factor = Decimal(reference) / spec_qualifier
        result.normalisation_factor = factor
        result.landed_comparable = landed * factor
    else:
        result.landed_comparable = landed

    # Blocking rule 2: computable but not comparable.
    if spec_qualifier is None and spec_label is not None:
        result.state = BLOCKED_INCOMPARABLE
        label_sentence = spec_label[0].upper() + spec_label[1:]
        if reference:
            result.explanation = (
                f"{label_sentence} not stated on this quotation. Recorded history uses "
                f"{reference} {spec_label}, so this price cannot be compared."
            )
        else:
            result.explanation = (
                f"{label_sentence} not stated on this quotation. Recorded history is kept on a "
                f"fixed {spec_label}, so this price cannot be compared."
            )
        return result

    if result.confidence in ("medium", "low"):
        result.state = LOW_CONFIDENCE
        result.explanation = result.confidence_reason or f"Read with {result.confidence} confidence."
    return result


def cross_check(extraction: dict, lines: list[LineResult]) -> CrossCheck:
    taxable_value = D(extraction.get("taxable_value"))
    gross_value = D(extraction.get("gross_value"))
    total_discount = D(extraction.get("total_discount"))
    total_freight = D(extraction.get("total_freight"))

    if any(line.taxable is None for line in lines):
        return CrossCheck(
            "incomplete",
            None,
            taxable_value,
            None,
            "Could not be completed: at least one line has no taxable value.",
        )
    if None in (taxable_value, gross_value, total_discount, total_freight):
        return CrossCheck(
            "incomplete",
            None,
            taxable_value,
            None,
            "Could not be completed: the summary block was not fully read.",
        )

    tolerance = TWO_PLACES * max(1, len(lines))
    line_sum = sum((line.taxable for line in lines), Decimal(0))
    lines_hold = abs(line_sum - taxable_value) <= tolerance
    summary_holds = abs((gross_value - total_discount + total_freight) - taxable_value) <= tolerance

    if lines_hold and summary_holds:
        detail = (
            f"Line taxable values sum to {fmt_money(line_sum)}, matching the printed {fmt_money(taxable_value)}."
        )
        return CrossCheck("passed", line_sum, taxable_value, True, detail)

    problems = []
    if not lines_hold:
        problems.append(
            f"line taxable values sum to {fmt_money(line_sum)} but the document prints {fmt_money(taxable_value)}"
        )
    if not summary_holds:
        problems.append(
            f"gross {fmt_money(gross_value)} less discount {fmt_money(total_discount)} plus freight "
            f"{fmt_money(total_freight)} does not equal the printed taxable value {fmt_money(taxable_value)}"
        )
    detail = "; ".join(problems)
    return CrossCheck("failed", line_sum, taxable_value, summary_holds, detail[0].upper() + detail[1:] + ".")


def convert_quotation(extraction: dict) -> QuotationResult:
    lines = [
        convert_line(item, extraction.get("gst_treatment", "exclusive"), extraction.get("gst_rate_percent", 0))
        for item in extraction.get("line_items", [])
    ]
    check = cross_check(extraction, lines)
    if check.status == "failed":
        for line in lines:
            line.attention = True
    return QuotationResult(lines=lines, cross_check=check)


def sheet_rows(extraction: dict, result: QuotationResult) -> tuple[list[list], list[str]]:
    """Rows for Quote DB in column order, plus the names of any lines not written."""
    rows: list[list] = []
    skipped: list[str] = []
    for line in result.lines:
        if line.canonical_item is None:
            skipped.append(f"{line.item_name}: no canonical item name")
            continue
        if line.landed_comparable is None or line.base_units is None:
            skipped.append(f"{line.item_name}: no landed cost could be computed")
            continue
        landed = round2(line.landed_comparable)
        quantity = line.base_units
        rows.append(
            [
                extraction["vendor_name"],
                extraction["quote_date"],
                line.canonical_item,
                line.base_unit,
                float(landed),
                int(quantity) if quantity == quantity.to_integral_value() else float(quantity),
                "",
                "",
            ]
        )
    return rows, skipped


def diff_lines(previous: QuotationResult | None, current: QuotationResult) -> set[str]:
    """Item names whose computed values differ from the previous pass."""
    if previous is None:
        return set()
    before = {line.item_name: line for line in previous.lines}
    changed = set()
    for line in current.lines:
        old = before.get(line.item_name)
        if old is None:
            changed.add(line.item_name)
            continue
        if (
            old.state != line.state
            or old.landed != line.landed
            or old.landed_comparable != line.landed_comparable
            or old.read_parts != line.read_parts
            or old.working != line.working
        ):
            changed.add(line.item_name)
    return changed
