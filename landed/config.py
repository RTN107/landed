"""Configuration: secrets from .env, fixed names, canonical mappings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Which Claude model handles all three model calls (extraction, resubmission,
# analysis). Must be a model id your Anthropic account can call. Change it here
# if you don't have access to the one shipped, or want to trade cost for speed.
MODEL = "claude-opus-5"

# Google Sheets
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")

# The tab the app reads and appends to. It must already exist in your spreadsheet,
# with SHEET_COLUMNS below as its first row: the app will not create or reshape it.
TAB_NAME = "Quote DB"
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_COLUMNS = [
    "Vendor name",
    "Quote date",
    "Item",
    "Base unit",
    "Landed cost per base unit excl. GST (INR)",
    "Order quantity",
    "Note",
    "Note date",
]

# ===========================================================================
# EVERYTHING BELOW IS A PLACEHOLDER. REPLACE IT WITH YOUR OWN.
#
# This block describes one fictional hotel buying cleaning consumables. None of
# it is required by the code. It is the only place any of this is stated: the
# prompts in landed/prompts/ carry {tokens} that are filled in from here at call
# time, and schema.py builds the extraction's enums from these lists, so nothing
# business specific is written into the Python or the prompt files themselves.
#
# The lists are closed on purpose. A quotation naming a vendor, pack or base unit
# you have not listed is rejected by the extraction rather than quietly recorded
# as the wrong one.
#
# See the "Where to make your changes" section of the README for what each of
# these does and what happens if you get one wrong.
# ===========================================================================

# --- Who you are -----------------------------------------------------------

# The organisation being bought for. Fills {customer} in every prompt.
CUSTOMER_NAME = "Hotel Meridian Court, Bengaluru"

# Shown at the top of the sidebar on every screen. Your name, or your team's.
NAMEPLATE = "Amogh Aradhya"

# Two or three sentences telling the model what this organisation is and what it
# buys. Fills {business} in the extraction and analysis prompts. This is the
# single biggest lever on output quality: the model reads quotations and writes
# purchasing advice, and both are better when it knows the trade it is working in.
# Replace it with your own business. A print shop, a restaurant group, a clinic
# and a construction firm all want different judgement applied to the same numbers.
BUSINESS_CONTEXT = (
    "The buyer is a hotel that purchases housekeeping and hygiene consumables in "
    "bulk on a monthly cycle, from a small number of regular suppliers. Quotations "
    "arrive as PDFs, priced by the pack, and are compared on cost per unit consumed "
    "rather than on the printed rate."
)

# --- Money and tax ---------------------------------------------------------

# How amounts are shown across the interface and written in the prompts. Change
# both together. CURRENCY_SYMBOL is what prefixes every figure on screen.
CURRENCY_SYMBOL = "Rs"
CURRENCY_NAME = "rupees"

# The recoverable sales tax on your quotations, by the name your documents use:
# GST in India, VAT across much of Europe, sales tax in the US. It is read from
# the document but deliberately excluded from the landed cost, on the assumption
# that you reclaim it and it is therefore not a cost. If you cannot reclaim it,
# see the README section on changing the calculation.
TAX_NAME = "GST"

# --- What you buy ----------------------------------------------------------

# Vendors whose quotations this app will accept.
VENDORS = [
    "Ace Hospitality Supplies",
    "Vector Cleaning Solutions",
    "Metro Housekeeping",
]

# Pack formats a quotation may be priced in.
PACK_UNITS = ["case", "jerrycan", "can", "box"]

# The units you actually consume, and that landed cost is expressed per.
# convert.py pluralises these for display and falls back to adding an "s".
BASE_UNITS = ["roll", "litre", "piece"]

# PDF wording -> canonical item name as stored in column C of the sheet.
# Keyed on the verbatim extracted item_name, because vendors word the same
# product differently. A name with no entry here is not written to the sheet and
# is surfaced on the review screen instead, so nothing is silently dropped.
ITEM_NAME_MAP = {
    "Toilet Tissue Roll": "Toilet tissue roll (2 ply, 300 pulls)",
    "Floor Cleaner, Ready to Use": "Floor cleaner (ready to use)",
    "Hand Wash Liquid": "Hand wash liquid",
    "Nitrile Gloves, Powder Free": "Nitrile gloves (powder free)",
}

CANONICAL_ITEMS = list(ITEM_NAME_MAP.values())

# Quantities hidden inside a unit name that change what one base unit is worth.
# Recorded history is kept at these values, so a quote stating a different figure
# is rescaled to this reference before it is compared or written, and a quote
# stating none at all is blocked from comparison rather than guessed at.
SPEC_REFERENCE = {
    "pulls per roll": 300,
}

# --- Prompt guidance -------------------------------------------------------
# These two are prose written into the prompts. They are here rather than in the
# prompt files because they describe your products, not how the app works.

# Tells the extraction which of your items carry a hidden qualifier from
# SPEC_REFERENCE, so the model labels it even when the document omits the number.
# That labelling is what lets a line be flagged as uncomparable instead of being
# silently compared against history recorded on a different basis. Fills
# {spec_guidance}. Set it to "No item carries such a qualifier." if none do.
SPEC_QUALIFIER_GUIDANCE = (
    "Toilet tissue and other paper rolls always carry this qualifier: return the label "
    '"pulls per roll" for them, and set spec_qualifier to the printed number or to null '
    "when the number is not printed. Items with no such qualifier (cleaners, liquids, "
    "gloves) get null for both fields."
)

# Two ways a reviewer might refer to one of your items in passing, used as
# examples so the model matches a loose comment to the right line. Fills
# {item_examples} in the resubmit prompt.
ITEM_EXAMPLES = '"the tissue" or "the gloves"'

# The greyed-out example in the review screen's comment box. Make it an example of
# a fact your own quotations tend to leave out.
COMMENT_PLACEHOLDER = "Tell it what the document left out, for example: the tissue rolls are 300 pulls."

# Irregular plurals for display only. Anything not listed here just gets an "s",
# so you only need an entry where that would be wrong ("boxes", not "boxs").
PLURALS = {
    "case": "cases",
    "jerrycan": "jerrycans",
    "can": "cans",
    "box": "boxes",
    "roll": "rolls",
    "litre": "litres",
    "piece": "pieces",
}


def anthropic_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is empty. Put the key in the .env file at the project root "
            "(see .env.example) and restart the app."
        )
    return key
