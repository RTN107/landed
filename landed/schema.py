"""The structured-output schema the extraction and resubmission calls must return.

The vendor, pack unit and base unit enums are built from the catalogue in config.py, so
that is the only file to edit when adapting this to a different hotel. They are closed on
purpose: a quotation naming something not in the catalogue is rejected outright rather
than quietly mis-parsed into the wrong vendor or unit.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import BASE_UNITS, PACK_UNITS, VENDORS

# Literal accepts a tuple and expands it, so these produce exactly the same JSON schema
# enum as spelling the values out here would, while keeping config.py authoritative.
Vendor = Literal[tuple(VENDORS)]  # type: ignore[valid-type]
PackUnit = Literal[tuple(PACK_UNITS)]  # type: ignore[valid-type]
BaseUnit = Literal[tuple(BASE_UNITS)]  # type: ignore[valid-type]

# These are properties of how quotations work, not of any one catalogue.
GstTreatment = Literal["exclusive", "inclusive"]
FreightType = Literal["flat", "per_unit", "included"]
Confidence = Literal["high", "medium", "low"]


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_name: str = Field(description="Verbatim from the PDF. Not normalised, tidied or mapped.")
    hsn: str
    quoted_rate: float = Field(description="The rate column, as printed.")
    pack_quantity: float = Field(description="Number of packs ordered.")
    pack_unit: PackUnit
    units_per_pack: float | None = Field(description="Base units contained in one pack. Null if not printed.")
    base_unit: BaseUnit
    spec_qualifier: float | None = Field(
        description="A quantity hidden inside the unit name, e.g. pulls per roll. Null if not printed."
    )
    spec_qualifier_label: str | None = Field(
        description="What that qualifier measures, e.g. 'pulls per roll'. Null if the item has no such qualifier."
    )
    discount_percent: float = Field(description="0 where the document states Nil.")
    line_amount: float = Field(description="The amount column.")
    freight_type: FreightType
    freight_value: float = Field(description="0 where freight_type is included.")
    confidence: Confidence
    confidence_reason: str | None = Field(description="Populated only when confidence is not high.")


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: Vendor
    quote_date: str = Field(description="DD/MM/YYYY")
    quote_number: str
    gst_treatment: GstTreatment
    gst_rate_percent: float
    line_items: list[LineItem] = Field(
        min_length=1, description="One object per row of the quotation's item table. Never empty."
    )
    gross_value: float
    total_discount: float = Field(description="Positive value, not negative.")
    net_value: float
    total_freight: float
    taxable_value: float
    grand_total: float


class Resubmission(Extraction):
    """Same schema as Extraction plus a plain-language change log."""

    changes_made: list[str] = Field(
        description="One plain-language sentence per change, e.g. "
        "'spec_qualifier for Toilet Tissue Roll set to 300 from user input'. Empty if nothing changed."
    )
