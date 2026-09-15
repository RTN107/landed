"""Calls to Claude: extraction, resubmission, analysis.

Prompts live in landed/prompts/*.md and are read at call time, so any of
them can be swapped without touching this file.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import anthropic

from . import config
from .config import MODEL, anthropic_api_key
from .schema import Extraction, Resubmission

PROMPTS = Path(__file__).resolve().parent / "prompts"

# Claude's safety classifiers can decline a request outright (stop_reason
# "refusal") even on ordinary business content - it happens rarely but has been
# observed on this app's own comparison prompt. Enabling the server-side fallback
# re-runs a declined request on Anthropic's recommended substitute model
# automatically, in the same call, rather than surfacing a refusal to the user.
FALLBACK_KWARGS = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}


def prompt_tokens() -> dict[str, str]:
    """The {tokens} a prompt may use, all filled from the placeholder block in config.

    Everything business specific reaches the model through here, so the prompt files
    themselves describe only how the work is done, never who it is done for or what
    they buy.
    """
    return {
        "customer": config.CUSTOMER_NAME,
        "business": config.BUSINESS_CONTEXT,
        "currency": config.CURRENCY_SYMBOL,
        "currency_name": config.CURRENCY_NAME,
        # Singular form for phrases like "to the nearest whole rupee".
        "currency_name_singular": config.CURRENCY_NAME.rstrip("s") or config.CURRENCY_NAME,
        "tax": config.TAX_NAME,
        "vendors": ", ".join(config.VENDORS),
        "pack_units": ", ".join(config.PACK_UNITS),
        "base_units": ", ".join(config.BASE_UNITS),
        "spec_guidance": config.SPEC_QUALIFIER_GUIDANCE,
        # An example qualifier taken from your own SPEC_REFERENCE, so the prompt
        # illustrates the idea with one of your items rather than someone else's.
        "spec_example": next(iter(config.SPEC_REFERENCE), "count per unit"),
        "item_examples": config.ITEM_EXAMPLES,
    }


def load_prompt(name: str) -> str:
    """Read a prompt from landed/prompts and fill in its {tokens} from config.

    Read fresh on every call, so a prompt can be edited while the app is running.
    Plain replaces rather than str.format, so braces anywhere else in a prompt are
    left alone and a prompt using none of the tokens is returned exactly as written.
    An unknown token is left visible in the text rather than raising, so a typo shows
    up in the output instead of taking the app down mid-demo.
    """
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for token, value in prompt_tokens().items():
        text = text.replace("{" + token + "}", value)
    return text


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=anthropic_api_key())


def _guard(response) -> None:
    if response.stop_reason == "refusal":
        details = response.stop_details
        category = getattr(details, "category", None)
        explanation = getattr(details, "explanation", "") or ""
        raise RuntimeError(f"The model declined this request ({category}). {explanation}".strip())
    if response.stop_reason == "max_tokens":
        raise RuntimeError("The model's response was cut off at max_tokens.")


def extract_quotation(pdf_bytes: bytes) -> dict:
    """PDF in, extraction JSON out. The PDF goes up as a base64 document block."""
    data = base64.standard_b64encode(pdf_bytes).decode("ascii")
    response = _client().beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=load_prompt("extraction"),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": data},
                    },
                    {"type": "text", "text": "Extract this quotation."},
                ],
            }
        ],
        output_format=Extraction,
        **FALLBACK_KWARGS,
    )
    _guard(response)
    if response.parsed_output is None:
        raise RuntimeError("The extraction response contained no parsable JSON.")
    return response.parsed_output.model_dump()


def resubmit(previous: dict, comment: str) -> dict:
    """Correct an extraction from the reviewer's comment.

    Sends the previous JSON and the comment, never the PDF again: the document has already
    been read, and re-reading it risks changing fields the reviewer did not question.
    """
    payload = json.dumps(previous, indent=2, ensure_ascii=False)
    response = _client().beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=load_prompt("resubmit"),
        messages=[
            {
                "role": "user",
                "content": f"Previous extraction:\n\n{payload}\n\nReviewer comment:\n\n{comment.strip()}",
            }
        ],
        output_format=Resubmission,
        **FALLBACK_KWARGS,
    )
    _guard(response)
    if response.parsed_output is None:
        raise RuntimeError("The resubmission response contained no parsable JSON.")
    return response.parsed_output.model_dump()


def analyse(month_label: str, decision_rows: list[dict], history_rows: list[dict]) -> str:
    """Prose comparison for the selected month. Rendered as-is by the caller."""
    vendors = sorted({row["Vendor name"] for row in decision_rows})
    context = {
        "selected_month": month_label,
        "vendors_quoting_this_month": vendors,
        "comparison_possible": len(vendors) > 1,
    }
    if len(vendors) <= 1:
        context["instruction"] = (
            "Only one vendor quoted in the selected month, so no comparison between vendors is "
            "possible. Say so plainly and do not invent one."
        )
    text = (
        f"Selected month: {month_label}\n\n"
        "DECISION SET (quotes received in the selected month, the ones being compared):\n"
        f"{json.dumps(decision_rows, indent=2, ensure_ascii=False)}\n\n"
        "HISTORY SET (quotes from before the selected month, for trend and track record):\n"
        f"{json.dumps(history_rows, indent=2, ensure_ascii=False)}\n\n"
        f"Context:\n{json.dumps(context, indent=2)}"
    )
    with _client().beta.messages.stream(
        model=MODEL,
        max_tokens=16000,
        system=load_prompt("analysis"),
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": text}],
        **FALLBACK_KWARGS,
    ) as stream:
        message = stream.get_final_message()
    _guard(message)
    return "".join(block.text for block in message.content if block.type == "text").strip()
