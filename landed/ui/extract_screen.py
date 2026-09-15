"""Screen 1, Extract: upload, extracting, review, written. Four states on one screen."""

from __future__ import annotations

from decimal import Decimal

import streamlit as st

from landed import claude, sheets
from landed.compare import month_label, month_of, parse_quote_date
from landed.config import COMMENT_PLACEHOLDER, CURRENCY_SYMBOL, TAB_NAME, TAX_NAME
from landed.convert import (
    BLOCKED_INCOMPARABLE,
    BLOCKED_UNCOMPUTABLE,
    CLEAR,
    LOW_CONFIDENCE,
    convert_quotation,
    diff_lines,
    fmt_money,
    fmt_qty,
    round2,
    sheet_rows,
)

from .shell import busy_css, check_glyph, esc, loading_html, mono

def _queue(action: str) -> None:
    ss = st.session_state
    if action == "resubmit":
        comment = (ss.get("comment") or "").strip()
        if not comment:
            ss.comment_hint = "Type a comment first. Resubmit sends it with the previous reading."
            return
        ss.comment_submitted = comment
    ss.comment_hint = None
    ss.pending = action


def render() -> None:
    ss = st.session_state
    if ss.get("written"):
        _written()
    elif ss.get("extraction") is None:
        if ss.get("pending") == "extract":
            _extracting()
        else:
            _empty()
    else:
        _review()


# ---------- state A ----------

def _empty() -> None:
    ss = st.session_state
    file = st.file_uploader("Quotation PDF", type=["pdf"], key="upload", label_visibility="collapsed")
    st.html(
        '<p class="ld lead ld-in" style="--i:2; margin-top:14px">Each line item becomes a landed cost per base '
        f"unit, excluding {TAX_NAME}, shown with its working. You approve it before it reaches the sheet.</p>"
    )
    if file is not None:
        ss.pdf_bytes = file.getvalue()
        ss.pdf_name = file.name
        ss.pending = "extract"
        st.rerun()


# ---------- state B ----------

def _extracting() -> None:
    ss = st.session_state
    title = ss.pdf_name.rsplit(".", 1)[0] if "." in ss.pdf_name else ss.pdf_name
    st.html(f'<div class="ld ld-in"><h1>{esc(title)}</h1></div>')
    st.html(loading_html("Reading the quotation"))
    ss.pending = None
    ss.extraction = claude.extract_quotation(ss.pdf_bytes)
    ss.changed = set()
    ss.changes_made = []
    st.rerun()


# ---------- state C ----------

def _header_html(extraction: dict, result) -> str:
    check = result.cross_check
    ok = check.status == "passed"
    gst = f"{TAX_NAME} {extraction['gst_treatment']}"
    if extraction.get("gst_rate_percent") is not None:
        gst += f" at {fmt_qty(round2(Decimal(str(extraction['gst_rate_percent']))))}%"
    if ok:
        check_html = (
            f'<div class="qcheck">{check_glyph(True)}<span>Totals cross-check passed</span>'
            f'<span class="detail">{mono(check.detail)}</span></div>'
        )
    elif check.status == "failed":
        check_html = (
            f'<div class="qcheck fail">{check_glyph(False)}<span>Totals cross-check failed. '
            f"Every row is marked for attention regardless of its confidence.</span>"
            f'<span class="detail">{mono(check.detail)}</span></div>'
        )
    else:
        check_html = (
            f'<div class="qcheck"><span class="faint">Totals cross-check not completed.</span>'
            f'<span class="detail">{mono(check.detail)}</span></div>'
        )
    return (
        f'<div class="ld qhead ld-in"><h1>{esc(extraction["vendor_name"])}</h1>'
        f'<div class="qmeta">'
        f'<span>Quotation <b>{mono(extraction["quote_number"])}</b></span>'
        f'<span>Dated <b>{mono(extraction["quote_date"])}</b></span>'
        f"<span><b>{mono(gst)}</b></span>"
        f"</div>{check_html}</div>"
    )


def _row_html(index: int, line, changed: bool) -> str:
    classes = ["row"]
    if line.state in (BLOCKED_INCOMPARABLE, BLOCKED_UNCOMPUTABLE):
        classes.append("blocked")
    elif line.state == LOW_CONFIDENCE:
        classes.append("low")
    if line.attention:
        classes.append("attention")
    if changed:
        classes.append("changed")

    name = f'<div class="row-name"><span>{esc(line.item_name)}</span>'
    if changed:
        name += '<span class="row-tag">changed</span>'
    name += "</div>"

    read = '<div class="row-read">' + "".join(f"<span>{mono(p)}</span>" for p in line.read_parts) + "</div>"

    if line.working:
        work = f'<div class="row-work">{esc(line.working)}</div>'
    else:
        work = '<div class="row-work none">No working: the quotation does not give enough to compute a landed cost.</div>'

    if line.landed is not None:
        status = line.status_label
        if line.state == BLOCKED_INCOMPARABLE:
            status = "cannot be compared"
        if line.attention and line.state == CLEAR:
            status = "check against the document"
        if line.normalisation_factor is not None and line.normalisation_factor != 1:
            status = f"{CURRENCY_SYMBOL} {fmt_money(line.landed_comparable)} at the recorded spec. {status}"
        cost = (
            f'<div class="row-cost"><span class="cur">{esc(CURRENCY_SYMBOL)}</span><span class="n">{fmt_money(line.landed)}</span>'
            f'<span class="unit">per {esc(line.base_unit)}</span>'
            f'<span class="status">{mono(status)}</span></div>'
        )
    else:
        cost = '<div class="row-cost"><span class="faint">no landed cost</span><span class="status">blocked</span></div>'

    note = ""
    if line.explanation:
        prefix = ""
        if line.state == LOW_CONFIDENCE:
            prefix = f"Read with {esc(line.confidence)} confidence. "
        note = f'<div class="row-note">{prefix}{mono(line.explanation)}</div>'
    elif line.attention:
        note = (
            '<div class="row-note">The totals cross-check failed, so this figure should be checked '
            "against the printed document before it is trusted.</div>"
        )

    return (
        f'<div class="{" ".join(classes)} ld-in" style="--i:{index}">'
        f'<div class="row-main">{name}{read}{work}</div>{cost}{note}</div>'
    )


def _review() -> None:
    ss = st.session_state
    extraction = ss.extraction
    result = convert_quotation(extraction)
    pending = ss.get("pending")
    busy = pending in ("resubmit", "approve")
    changed = ss.get("changed") or set()

    st.html(_header_html(extraction, result))
    rows_html = "".join(_row_html(i + 1, line, line.item_name in changed) for i, line in enumerate(result.lines))
    st.html(f'<div class="ld rows">{rows_html}</div>')
    if busy:
        st.html("<style>.rows .row { opacity: 0.45; }</style>")

    changes = ss.get("changes_made") or []
    if changes:
        items = "".join(f"<li>{mono(c)}</li>" for c in changes)
        st.html(f'<ul class="ld changes ld-in" style="--i:{len(result.lines) + 1}">{items}</ul>')

    st.html('<div class="section-gap"></div>')

    if busy:
        st.text_area(
            "Comment",
            value=ss.get("comment_submitted", "") if pending == "resubmit" else (ss.get("comment") or ""),
            key="comment_busy",
            height=96,
            disabled=True,
            label_visibility="collapsed",
        )
    else:
        st.text_area(
            "Comment",
            key="comment",
            height=96,
            placeholder=COMMENT_PLACEHOLDER,
            label_visibility="collapsed",
        )
        if ss.get("comment_hint"):
            st.html(f'<p class="ld muted" style="font-size:14px">{esc(ss.comment_hint)}</p>')

    approve_primary = result.all_clear
    c1, c2 = st.columns([1, 1])
    with c1:
        with st.container(key="btn_resubmit_wrap"):
            st.button(
                "Resubmitting" if pending == "resubmit" else "Resubmit",
                key="btn_resubmit",
                type="secondary" if approve_primary else "primary",
                on_click=_queue,
                args=("resubmit",),
                disabled=busy,
            )
    with c2:
        with st.container(key="btn_approve_wrap"):
            st.button(
                "Writing to the sheet" if pending == "approve" else "Approve",
                key="btn_approve",
                type="primary" if approve_primary else "secondary",
                on_click=_queue,
                args=("approve",),
                disabled=busy,
            )

    if pending == "resubmit":
        st.html(busy_css("btn_resubmit_wrap"))
        st.html(loading_html("Re-reading with your comment"))
        _do_resubmit(extraction, result)
    elif pending == "approve":
        st.html(busy_css("btn_approve_wrap"))
        st.html(loading_html(f"Writing to {TAB_NAME}"))
        _do_approve(extraction, result)


def _do_resubmit(extraction: dict, result) -> None:
    ss = st.session_state
    comment = ss.get("comment_submitted", "")
    ss.pending = None
    revised = claude.resubmit(extraction, comment)
    changes_made = revised.pop("changes_made", [])
    new_result = convert_quotation(revised)
    ss.changed = diff_lines(result, new_result)
    ss.changes_made = list(changes_made)
    ss.extraction = revised
    ss.comment = ""
    ss.comment_submitted = ""
    st.rerun()


def _do_approve(extraction: dict, result) -> None:
    ss = st.session_state
    ss.pending = None
    rows, skipped = sheet_rows(extraction, result)
    updates = sheets.append_rows(rows)
    ss.written = {
        "rows": rows,
        "skipped": skipped,
        "updates": updates,
        "month": month_of(parse_quote_date(extraction["quote_date"])),
    }
    ss.sheet_stale = True
    st.rerun()


# ---------- state D ----------

def _handoff() -> None:
    ss = st.session_state
    ss.month = ss.written["month"]
    ss.analysis = None
    ss.page = "compare"


def _written() -> None:
    ss = st.session_state
    w = ss.written
    n = len(w["rows"])
    body = "".join(
        f"<tr><td>{esc(r[2])}</td><td>{esc(r[0])}</td><td>{mono(r[1])}</td>"
        f'<td class="r">{mono(f"{CURRENCY_SYMBOL} {fmt_money(round2(Decimal(str(r[4]))))}")} '
        f'<span class="muted">per {esc(r[3])}</span></td>'
        f'<td class="r"><span class="n">{fmt_qty(Decimal(str(r[5])))}</span> '
        f'<span class="muted">{esc(r[3])}{"" if str(r[5]) == "1" else "s"}</span></td></tr>'
        for r in w["rows"]
    )
    skipped = ""
    if w["skipped"]:
        skipped = '<p class="skipped">Not written: ' + "; ".join(esc(s) for s in w["skipped"]) + "</p>"
    st.html(
        f'<div class="ld done ld-in"><div class="big"><span class="n">{n}</span>'
        f'<small>{"row" if n == 1 else "rows"} written to {esc(TAB_NAME)}</small></div>'
        f'<table class="written">{body}</table>{skipped}</div>'
    )
    st.html('<div class="ld-in handoff" style="--i:3"></div>')
    with st.container(key="btn_handoff_wrap"):
        st.button(f"Compare {month_label(w['month'])}", key="btn_handoff", type="primary", on_click=_handoff)
