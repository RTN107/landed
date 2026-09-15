"""Screen 2, Compare: pick a month, run the analysis, read the verdict."""

from __future__ import annotations

import streamlit as st

from landed import claude, sheets
from landed.compare import (
    available_months,
    build_table,
    build_trends,
    enrich,
    month_label,
    public_rows,
    split_headline,
    split_rows,
)
from landed.config import CURRENCY_NAME, CURRENCY_SYMBOL, TAX_NAME
from landed.convert import fmt_money

from .shell import busy_css, esc, loading_html, mono


def _queue() -> None:
    st.session_state.pending = "compare"


def _months_from_sheet() -> list:
    ss = st.session_state
    if ss.get("sheet_rows") is None or ss.get("sheet_stale"):
        ss.sheet_rows = enrich(sheets.read_all())
        ss.sheet_stale = False
    return available_months(ss.sheet_rows)


def render() -> None:
    ss = st.session_state
    pending = ss.get("pending")
    busy = pending == "compare"
    months = _months_from_sheet()

    st.html(
        '<div class="ld qhead ld-in"><h1>Compare</h1><p class="lead" style="margin:10px 0 0">'
        "Every quote received in a month, set against each other and read in the light of everything "
        "quoted before it.</p></div>"
    )

    if ss.get("month") not in months:
        ss.month = months[0] if months else None
    st.selectbox(
        "Month",
        options=months,
        format_func=month_label,
        key="month",
        label_visibility="collapsed",
        disabled=busy,
    )
    with st.container(key="btn_compare_wrap"):
        st.button(
            "Comparing" if busy else "Run comparison",
            key="btn_compare",
            type="primary",
            on_click=_queue,
            disabled=busy,
        )

    if busy:
        st.html(busy_css("btn_compare_wrap"))
        st.html(loading_html(f"Reading {month_label(ss.month)} against its history"))
        _run(ss.month)
    elif ss.get("analysis"):
        _verdict(ss.analysis)


def _run(month) -> None:
    ss = st.session_state
    ss.pending = None
    fresh = enrich(sheets.read_all())
    ss.sheet_rows = fresh
    decision, history = split_rows(fresh, month)
    table = build_table(decision)
    trends = build_trends(decision, history)
    text = claude.analyse(month_label(month), public_rows(decision), public_rows(history))
    figure, caption, body = split_headline(text)
    ss.analysis = {
        "month": month,
        "table": table,
        "trends": trends,
        "figure": figure,
        "caption": caption,
        "body": body,
    }
    st.rerun()


def _fallback_headline(table) -> tuple[str, str]:
    label = month_label(st.session_state.analysis["month"])
    if table.single_vendor:
        return "One vendor", f"quoted in {label}, so no comparison is possible"
    wins = table.wins()
    leader = max(wins, key=wins.get)
    return f"{wins[leader]} of {len(table.items)}", f"items where {leader} is cheapest in {label}"


def _verdict(analysis: dict) -> None:
    table = analysis["table"]
    label = month_label(analysis["month"])

    figure, caption = analysis["figure"], analysis["caption"]
    if not figure:
        figure, caption = _fallback_headline(table)
    small = " small" if len(figure) > 16 or not any(ch.isdigit() for ch in figure) else ""
    st.html(
        f'<div class="ld headline{small} ld-in" style="--i:0"><div class="fig">{mono(figure)}</div>'
        f'<div class="cap">{mono(caption or "")}</div></div>'
    )

    if table.single_vendor:
        vendor = table.vendors[0] if table.vendors else "No vendor"
        lines = "".join(
            f'<tr><td>{esc(item)}<small>per {esc(table.units[item])}</small></td>'
            f'<td><span class="n">{fmt_money(table.cells[(item, vendor)])}</span></td></tr>'
            for item in table.items
            if table.cells[(item, vendor)] is not None
        )
        st.html(
            f'<div class="ld ld-in" style="--i:3"><div class="single">Only {esc(vendor)} quoted in {esc(label)}, '
            f"so there is nothing to compare it against this month. Its quotes are listed below; "
            f"the history strip shows how they sit against its own earlier prices.</div>"
            f'<table class="cmp" style="margin-top:22px"><tr><th>Item</th><th>{esc(vendor)}</th></tr>{lines}</table></div>'
        )
    else:
        head = "<tr><th>Item</th>" + "".join(f"<th>{esc(v)}</th>" for v in table.vendors) + "</tr>"
        body = ""
        for item in table.items:
            cells = ""
            for vendor in table.vendors:
                value = table.cells[(item, vendor)]
                if value is None:
                    cells += '<td class="none">not quoted</td>'
                elif vendor in table.cheapest.get(item, set()):
                    cells += f'<td class="best"><span>{fmt_money(value)}</span></td>'
                else:
                    cells += f"<td>{fmt_money(value)}</td>"
            body += f'<tr><td>{esc(item)}<small>per {esc(table.units[item])}</small></td>{cells}</tr>'
        st.html(
            f'<div class="ld ld-in" style="--i:3"><table class="cmp">{head}{body}</table>'
            f'<p class="cmp-note">Landed cost per base unit, excluding {TAX_NAME}, in {CURRENCY_NAME}. '
            f"The cheapest quote on each item is marked.</p></div>"
        )

    paragraphs = [p.strip() for p in analysis["body"].split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [analysis["body"]]
    findings = "".join(f"<p>{mono(p.replace(chr(10), ' '))}</p>" for p in paragraphs)
    st.html(f'<div class="ld findings ld-in" style="--i:6">{findings}</div>')

    st.html(_trend_html(analysis["trends"], label))


def _trend_html(trends, label: str) -> str:
    by_item: dict[str, list] = {}
    for t in trends:
        by_item.setdefault(t.item, []).append(t)
    blocks = ""
    for item, group in by_item.items():
        lines = ""
        for t in group:
            if t.available:
                pct = t.change_percent
                if pct is None or abs(pct) < 0.05:
                    move = "unchanged"
                else:
                    move = f"{'up' if pct > 0 else 'down'} {abs(pct):.1f}%"
                text = (
                    f"{CURRENCY_SYMBOL} {fmt_money(t.first)} in {t.first_when} to "
                    f"{CURRENCY_SYMBOL} {fmt_money(t.last)} in {t.last_when}, "
                    f"{move} across {t.earlier_quotes} quotes."
                )
            elif t.earlier_quotes == 1:
                text = (
                    f"No trend available before {label}: only one earlier quote on record, "
                    f"{CURRENCY_SYMBOL} {fmt_money(t.first)} in {t.first_when}."
                )
            else:
                text = f"No trend available before {label}: no earlier quotes on record."
            if t.this_month is not None:
                text += f" This month {CURRENCY_SYMBOL} {fmt_money(t.this_month)}."
            lines += f'<div class="trend-line"><b>{esc(t.vendor)}</b> {mono(text)}</div>'
        blocks += f'<div class="trend-item"><h3>{esc(item)}</h3>{lines}</div>'
    return f'<div class="ld trend ld-in" style="--i:9"><h2>Movement before {esc(label)}</h2>{blocks}</div>'
