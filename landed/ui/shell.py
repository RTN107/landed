"""The app shell: palette, type scale, motion constants, nameplate, sidebar, buttons, loading.

Everything visual is defined once here and reused by both screens.

Palette      near-black --ink, off-white --paper, four greys between them.
Accent       --accent, ink blue. Used in exactly two places: the cheapest
             cell in the comparison table, and the glow on the primary button.
Type         Bodoni Moda for the nameplate only. Schibsted Grotesk for all
             interface text. Fragment Mono for every number.
Motion       one curve --ease; --t-fast for hovers and presses, --t-slow for
             content appearing; rows stagger by --stagger.
"""

from __future__ import annotations

import html as _html
import re

import streamlit as st

from ..config import CURRENCY_SYMBOL, NAMEPLATE

CSS = r"""
:root {
  --ink: #1B1A18;
  --ink-2: #3D3A35;
  --ink-3: #6E6A62;
  --ink-4: #A8A399;
  --line: #D6D2C9;
  --paper-2: #EAE7E0;
  --paper: #F3F1EC;
  --accent: #2C4BC8;

  --plate: #1B1A18;
  --plate-text: #D8D3C8;
  --plate-dim: #8C877C;
  --plate-base: #CBC5B8;
  --plate-hi: #FBF8F1;

  --serif: "Bodoni Moda", "Didot", "Bodoni 72", Georgia, serif;
  --sans: "Schibsted Grotesk", "Helvetica Neue", Arial, sans-serif;
  --mono: "Fragment Mono", "SF Mono", Menlo, Consolas, monospace;

  --ease: cubic-bezier(0.22, 0.61, 0.36, 1);
  --t-fast: 160ms;
  --t-slow: 480ms;
  --stagger: 45ms;
}

/* The syntax strings use the CSS escapes \3C and \3E for the angle brackets: the
   sanitiser that runs on st.html drops any style block containing a literal opening
   bracket followed by a letter. */
@property --ld-angle { syntax: "\3C angle\3E "; inherits: false; initial-value: 0deg; }
@property --ld-sec { syntax: "\3C integer\3E "; inherits: false; initial-value: 0; }

/* ---------- chrome ---------- */
[data-testid="stDecoration"], [data-testid="stStatusWidget"], #MainMenu, footer,
[data-testid="stSidebarHeader"] { display: none !important; }

/* stHeader and, nested inside it, stToolbar are NOT hidden here, on purpose - a
   version of this rule that display:none'd stHeader was found (live) to also kill the
   reopen-sidebar button, since that button renders nowhere else. Both elements carry
   no visible size or background of their own once MainMenu/decoration/status-widget
   are hidden (confirmed empty by dumping their computed rects), so leaving them alone
   costs nothing visually - they just sit at zero size until the one thing they exist
   to hold (the reopen button, styled below) needs to appear.

   The sidebar's own collapse button stays hidden - the sidebar is fixed by design and
   never meant to be closed from inside it. But the reopen control must stay reachable:
   if the sidebar is ever collapsed by any means - a resize, a restored browser session,
   anything - hiding the only way back in would strand the user. Restyle it to match
   the shell instead of removing it. */
[data-testid="stSidebarCollapseButton"] { display: none !important; }
[data-testid="stExpandSidebarButton"] {
  position: fixed !important; top: 20px; left: 20px; z-index: 999999;
  background: var(--plate) !important; border-radius: 4px; box-shadow: 0 2px 10px rgba(0,0,0,0.18);
}
[data-testid="stExpandSidebarButton"] button, [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {
  color: var(--plate-text) !important; background: transparent !important;
}

[data-testid="stAppViewContainer"], [data-testid="stMain"] { background: var(--paper); }
[data-testid="stMainBlockContainer"], .block-container {
  max-width: 1040px; padding: 64px 72px 128px 72px;
}
[data-testid="stMain"] [data-testid="stVerticalBlock"] { gap: 0.55rem; }
[data-testid="stMain"] [data-testid="stElementContainer"] { min-height: 0; }
[data-testid="stMain"] [data-testid="stHtml"] { overflow: visible; }

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {
  width: 232px !important; min-width: 232px !important; max-width: 232px !important;
  background: var(--plate); border-right: 0;
}
section[data-testid="stSidebar"] > div:first-child { width: 232px !important; }
[data-testid="stSidebarResizeHandle"], [data-testid="stSidebarResizer"] { display: none !important; }
[data-testid="stSidebarContent"] { padding: 0; }
[data-testid="stSidebarUserContent"] { padding: 30px 22px 26px 24px; height: 100vh; display: flex; flex-direction: column; }
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0; }
section[data-testid="stSidebar"] [data-testid="stHtml"] { overflow: visible; }

.np { margin: 0 0 40px; user-select: none; pointer-events: none; }
.np-text {
  display: inline-block;
  font-family: var(--serif); font-variation-settings: "opsz" 96; font-weight: 500;
  font-size: 21px; line-height: 1.2; letter-spacing: 0.012em; white-space: nowrap;
  color: var(--plate-base);
  background-image: linear-gradient(100deg,
    var(--plate-base) 0%, var(--plate-base) 42%, var(--plate-hi) 50%, var(--plate-base) 58%, var(--plate-base) 100%);
  background-size: 320% 100%; background-position: 100% 0;
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
  animation: np-sweep 11s var(--ease) 2.2s infinite;
}
.np.reveal .np-text { animation: np-reveal 1100ms var(--ease) both, np-sweep 11s var(--ease) 2.2s infinite; }
@keyframes np-sweep {
  0%   { background-position: 100% 0; }
  24%  { background-position: 0% 0; }
  100% { background-position: 0% 0; }
}
@keyframes np-reveal {
  from { opacity: 0; transform: translateY(5px); filter: blur(5px); }
  to   { opacity: 1; transform: none; filter: blur(0); }
}

section[data-testid="stSidebar"] [data-testid="stButton"] { margin: 0; }
section[data-testid="stSidebar"] [data-testid="stButton"] button,
section[data-testid="stSidebar"] [data-testid="stButton"] button:hover,
section[data-testid="stSidebar"] [data-testid="stButton"] button:focus,
section[data-testid="stSidebar"] [data-testid="stButton"] button:active {
  font-family: var(--sans); font-size: 15px; font-weight: 400; letter-spacing: 0.005em;
  color: var(--plate-dim); background: transparent; border: 0; box-shadow: none;
  padding: 7px 0 7px 16px; min-height: 0; height: auto; width: auto; position: relative;
  justify-content: flex-start; text-align: left; outline: none;
  transition: color var(--t-fast) var(--ease);
}
section[data-testid="stSidebar"] [data-testid="stButton"] button:hover { color: var(--plate-text); }
section[data-testid="stSidebar"] [data-testid="stButton"] button::before {
  content: ""; position: absolute; left: 0; top: 50%; width: 7px; height: 1px;
  background: var(--plate-text); transform: translateY(-50%) scaleX(0); transform-origin: left center;
  transition: transform var(--t-fast) var(--ease);
}
section[data-testid="stSidebar"] [data-testid="stButton"] button p { font-size: 15px; margin: 0; }
.nav-active [data-testid="stButton"] button { color: var(--plate-text) !important; font-weight: 500 !important; }
.nav-active [data-testid="stButton"] button::before { transform: translateY(-50%) scaleX(1) !important; }

/* ---------- type ---------- */
.ld { font-family: var(--sans); color: var(--ink); font-size: 15px; line-height: 1.45; }
.ld .n { font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 0.94em; }
.ld .cur { margin-right: 0.3em; }
.ld h1 { font-family: var(--sans); font-size: 26px; font-weight: 500; letter-spacing: -0.012em; line-height: 1.2; margin: 0; }
.ld h2 { font-family: var(--sans); font-size: 20px; font-weight: 500; letter-spacing: -0.008em; margin: 0; }
.ld p { margin: 0; }
.muted { color: var(--ink-3); }
.faint { color: var(--ink-4); }

@keyframes ld-rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.ld-in { animation: ld-rise var(--t-slow) var(--ease) both; animation-delay: calc(var(--i, 0) * var(--stagger)); }

/* ---------- empty state ---------- */
.lead { max-width: 56ch; margin: 0 0 22px; font-size: 15px; color: var(--ink-3); }
[data-testid="stFileUploader"] { margin-top: 4px; }
[data-testid="stFileUploader"] > label { display: none; }
[data-testid="stFileUploaderDropzone"] {
  min-height: 320px; border: 1px solid var(--line); border-radius: 4px; background: transparent;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 18px;
  padding: 40px; transition: border-color var(--t-fast) var(--ease), background var(--t-fast) var(--ease);
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--ink-3); }
[data-testid="stFileUploaderDropzoneInstructions"] { display: none; }
[data-testid="stFileUploaderDropzone"]::before {
  content: "Drop a vendor quotation"; order: 0;
  font-family: var(--sans); font-size: 22px; font-weight: 500; letter-spacing: -0.01em; color: var(--ink);
}
[data-testid="stFileUploaderDropzone"]::after {
  content: "One PDF. Nothing is saved until you approve it."; order: 3;
  font-family: var(--sans); font-size: 14px; color: var(--ink-3);
}
[data-testid="stFileUploaderDropzone"] button { order: 2; }
[data-testid="stFileUploaderDropzone"] button [data-testid="stIconMaterial"] { display: none; }
[data-testid="stFileUploaderFile"], [data-testid="stFileUploaderFileName"] { font-family: var(--sans); }
[data-testid="stFileUploaderDeleteBtn"] { display: none; }

/* ---------- review ---------- */
.qhead { padding: 0 0 22px; }
.qmeta { display: flex; flex-wrap: wrap; gap: 6px 30px; margin-top: 12px; font-size: 14px; color: var(--ink-3); }
.qmeta span b { font-weight: 500; color: var(--ink); }
.qcheck { margin-top: 20px; display: flex; align-items: center; gap: 10px; font-size: 15px; color: var(--ink); }
.qcheck .tick { display: inline-block; width: 6px; height: 11px; flex: none; margin: 0 6px 4px 2px;
                border-right: 1.5px solid var(--ink); border-bottom: 1.5px solid var(--ink); transform: rotate(45deg); }
.qcheck .cross { position: relative; display: inline-block; width: 12px; height: 12px; flex: none; margin-right: 2px; }
.qcheck .cross::before, .qcheck .cross::after { content: ""; position: absolute; left: 5px; top: 0; width: 1.5px; height: 12px; background: var(--ink); }
.qcheck .cross::before { transform: rotate(45deg); }
.qcheck .cross::after { transform: rotate(-45deg); }
.qcheck .detail { color: var(--ink-3); }
.qcheck.fail { padding: 14px 16px; border: 1px solid var(--ink); border-radius: 4px; }

.rows { border-top: 1px solid var(--line); }
.row { position: relative; display: grid; grid-template-columns: minmax(0, 1fr) auto; column-gap: 48px;
       align-items: start; padding: 22px 0 24px; border-bottom: 1px solid var(--line); }
.row-main { min-width: 0; }
.row-cost .cur { font-size: 15px; color: var(--ink-3); margin-right: 0.4em; }
.row-name { font-size: 18px; font-weight: 500; letter-spacing: -0.005em; display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 12px; }
.row-tag { font-size: 12px; font-weight: 400; color: var(--ink-3); }
.row-read { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px 22px; font-size: 14px; color: var(--ink-3); }
.row-read .n { color: var(--ink-2); }
.row-work { margin-top: 15px; font-family: var(--mono); font-size: 18px; letter-spacing: -0.005em; color: var(--ink); }
.row-work.none { font-family: var(--sans); font-size: 14px; color: var(--ink-4); }
.row-cost { text-align: right; white-space: nowrap; }
.row-cost .n { font-size: 22px; letter-spacing: -0.01em; }
.row-cost .unit { font-size: 14px; color: var(--ink-3); margin-left: 4px; }
.row-cost .status { display: block; margin-top: 8px; font-size: 12px; color: var(--ink-4); }
.row-note { grid-column: 1 / -1; margin-top: 16px; padding-left: 14px; border-left: 2px solid var(--ink);
            font-size: 15px; line-height: 1.55; max-width: 66ch; color: var(--ink); }
.row.blocked { padding: 28px 0 30px; }
.row.blocked .row-name { font-weight: 600; }
.row.blocked .row-cost .n { color: var(--ink-4); }
.row.blocked .row-cost .unit { color: var(--ink-4); }
.row.blocked .row-cost .status { color: var(--ink); }
.row.low .row-note { border-left-style: dotted; color: var(--ink-2); }
.row.attention .row-cost .status { color: var(--ink); }
.row.changed::before { content: ""; position: absolute; inset: 0 -18px; z-index: -1; border-radius: 4px;
                       animation: ld-settle 2800ms var(--ease) both; }
@keyframes ld-settle { 0% { background: var(--paper-2); } 35% { background: var(--paper-2); } 100% { background: transparent; } }
.row.changed .row-tag { color: var(--ink); }
.rows.dim .row { opacity: 0.45; transition: opacity var(--t-slow) var(--ease); }
.rows .row { transition: opacity var(--t-slow) var(--ease); }

.after-rows { margin-top: 26px; }
.after-rows .hint { font-size: 14px; color: var(--ink-3); margin-bottom: 10px; }
.changes { margin: 18px 0 0; padding: 0; list-style: none; font-size: 14px; color: var(--ink-3); }
.changes li { padding: 4px 0 4px 14px; border-left: 2px solid var(--line); }

/* ---------- inputs ---------- */
[data-testid="stTextArea"] > label { display: none; }
[data-testid="stTextAreaRootElement"] {
  background: transparent !important; border: 1px solid var(--line) !important; border-radius: 4px !important;
  box-shadow: none !important; transition: border-color var(--t-fast) var(--ease);
}
[data-testid="stTextAreaRootElement"]:hover { border-color: var(--ink-3) !important; }
[data-testid="stTextAreaRootElement"]:focus-within { border-color: var(--ink) !important; }
[data-testid="stTextArea"] textarea {
  font-family: var(--sans); font-size: 15px; line-height: 1.5; padding: 14px 16px; color: var(--ink);
  background: transparent !important; caret-color: var(--ink); resize: none;
}
[data-testid="stTextArea"] textarea::placeholder { color: var(--ink-4); }
[data-testid="stTextArea"] textarea:disabled { color: var(--ink-3); -webkit-text-fill-color: var(--ink-3); }
[data-testid="InputInstructions"] { display: none; }

[data-testid="stSelectbox"] > label { display: none; }
[data-testid="stSelectbox"] [role="group"] {
  background: transparent !important; border: 1px solid var(--line) !important; border-radius: 4px !important;
  min-height: 42px; box-shadow: none !important; transition: border-color var(--t-fast) var(--ease);
}
[data-testid="stSelectbox"] [role="group"]:hover { border-color: var(--ink-3) !important; }
[data-testid="stSelectbox"] [role="group"]:focus-within { border-color: var(--ink) !important; }
[data-testid="stSelectbox"] input[role="combobox"] {
  font-family: var(--sans); font-size: 15px; color: var(--ink); background: transparent; padding-left: 14px;
}
[data-testid="stSelectbox"] [role="group"] button { color: var(--ink-3); }
[data-testid="stSelectboxVirtualDropdown"] {
  font-family: var(--sans); font-size: 15px; border: 1px solid var(--line) !important; border-radius: 4px !important;
  box-shadow: 0 8px 24px rgba(27, 26, 24, 0.08) !important; background: var(--paper) !important;
}
[data-testid="stSelectboxVirtualDropdown"] [role="option"] { padding: 9px 14px; color: var(--ink-2); }
[data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"],
[data-testid="stSelectboxVirtualDropdown"] [role="option"][data-focused] { background: var(--paper-2) !important; color: var(--ink); }

/* ---------- buttons, three levels ---------- */
[data-testid="stMain"] [data-testid="stButton"] button {
  font-family: var(--sans); font-size: 15px; font-weight: 500; letter-spacing: 0.002em;
  height: 42px; min-height: 42px; padding: 0 22px; border-radius: 4px; position: relative;
  transition: transform var(--t-fast) var(--ease), border-color var(--t-fast) var(--ease),
              background-color var(--t-fast) var(--ease), color var(--t-fast) var(--ease);
}
[data-testid="stMain"] [data-testid="stButton"] button p { font-size: 15px; }
[data-testid="stMain"] button[kind="primary"] { background: var(--ink); color: var(--paper); border: 1px solid var(--ink); }
[data-testid="stMain"] button[kind="primary"]:hover { background: var(--ink-2); border-color: var(--ink-2); color: var(--paper); transform: translateY(-1px); }
[data-testid="stMain"] button[kind="primary"]:active { transform: translateY(0); }
[data-testid="stMain"] button[kind="primary"]:focus:not(:active) { box-shadow: none; color: var(--paper); }
[data-testid="stMain"] button[kind="primary"]:not(:disabled)::before {
  content: ""; position: absolute; inset: -3px; border-radius: 7px; padding: 2px; pointer-events: none;
  background: conic-gradient(from var(--ld-angle), transparent 0deg, transparent 250deg, var(--accent) 325deg, transparent 360deg);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
  filter: blur(0.8px); opacity: 0.95;
  animation: ld-orbit 5.5s linear infinite;
}
@keyframes ld-orbit { to { --ld-angle: 360deg; } }

[data-testid="stMain"] button[kind="secondary"] { background: transparent; color: var(--ink); border: 1px solid var(--line); }
[data-testid="stMain"] button[kind="secondary"]:hover { background: transparent; color: var(--ink); border-color: var(--ink-3); }
[data-testid="stMain"] button[kind="secondary"]:focus:not(:active) { box-shadow: none; color: var(--ink); border-color: var(--ink-3); }
[data-testid="stMain"] button[kind="tertiary"] { background: transparent; color: var(--ink-3); border: 0; padding: 0; height: auto; min-height: 0; }
[data-testid="stMain"] button[kind="tertiary"]:hover { color: var(--ink); background: transparent; }

[data-testid="stMain"] button:disabled, [data-testid="stMain"] button:disabled:hover {
  background: var(--paper-2); color: var(--ink-4); border-color: var(--paper-2);
  transform: none; cursor: default; box-shadow: none;
}
[data-testid="stMain"] button:disabled p { color: var(--ink-4); }
.busy [data-testid="stButton"] button:disabled, .busy [data-testid="stButton"] button:disabled:hover {
  background-color: var(--ink);
  background-image: linear-gradient(100deg, var(--ink) 0%, var(--ink) 38%, var(--ink-3) 50%, var(--ink) 62%, var(--ink) 100%);
  background-size: 280% 100%; border-color: var(--ink); color: var(--ink-4);
  animation: ld-sheen 1.7s linear infinite;
}
.busy [data-testid="stButton"] button:disabled p { color: var(--plate-text); }
@keyframes ld-sheen { from { background-position: 100% 0; } to { background-position: 0% 0; } }

[data-testid="stHorizontalBlock"] { gap: 12px; align-items: center; }
[data-testid="stColumn"] { min-width: 0; flex: 0 0 auto !important; width: auto !important; }

/* ---------- loading ---------- */
.wait { padding: 10px 0 0; animation: ld-rise var(--t-slow) var(--ease) both; }
.wait-track { height: 1px; background: var(--line); position: relative; overflow: hidden; }
.wait-track::after { content: ""; position: absolute; top: 0; left: -34%; width: 34%; height: 1px; background: var(--ink);
                     animation: ld-sweep 1.9s var(--ease) infinite; }
@keyframes ld-sweep { to { left: 100%; } }
.wait-text { margin-top: 14px; display: flex; justify-content: space-between; align-items: baseline; font-size: 14px; color: var(--ink-3); }
.wait-clock { font-family: var(--mono); font-variant-numeric: tabular-nums; color: var(--ink-4);
              animation: ld-tick 900s linear forwards; counter-reset: sec var(--ld-sec); }
.wait-clock::after { content: counter(sec) " s"; }
@keyframes ld-tick { from { --ld-sec: 0; } to { --ld-sec: 900; } }

/* ---------- written ---------- */
.done { padding: 4px 0 0; }
.done .big { font-family: var(--mono); font-size: 44px; line-height: 1; letter-spacing: -0.02em; }
.done .big small { font-family: var(--sans); font-size: 16px; letter-spacing: 0; color: var(--ink-3); margin-left: 12px; }
.written { width: 100%; border-collapse: collapse; margin-top: 24px; }
.written td { padding: 10px 0; border-bottom: 1px solid var(--line); font-size: 14px; color: var(--ink-2); vertical-align: baseline; }
.written td.r { text-align: right; padding-left: 24px; white-space: nowrap; }
.written td .n { font-size: 15px; color: var(--ink); }
.written td:first-child { color: var(--ink); }
.handoff { margin-top: 30px; }
.skipped { margin-top: 16px; font-size: 14px; color: var(--ink-3); }

/* ---------- compare ---------- */
.headline { padding: 6px 0 36px; }
.headline .fig { font-family: var(--mono); font-size: 76px; line-height: 1; letter-spacing: -0.025em; color: var(--ink); }
.headline .cap { margin-top: 14px; font-size: 16px; color: var(--ink-3); max-width: 54ch; }
.headline.small .fig { font-family: var(--sans); font-size: 30px; font-weight: 500; letter-spacing: -0.012em; }

.cmp { width: 100%; border-collapse: collapse; }
.cmp th, .cmp td { padding: 14px 0 14px 28px; border-bottom: 1px solid var(--line); text-align: right; vertical-align: baseline; }
.cmp th:first-child, .cmp td:first-child { text-align: left; padding-left: 0; }
.cmp th { font-family: var(--sans); font-weight: 400; font-size: 13px; color: var(--ink-3); border-bottom: 1px solid var(--ink); padding-bottom: 10px; }
.cmp td { font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 17px; color: var(--ink); }
.cmp td:first-child { font-family: var(--sans); font-size: 15px; }
.cmp td:first-child small { display: block; font-size: 12px; color: var(--ink-4); margin-top: 3px; }
.cmp td.best { color: var(--accent); }
.cmp td.best span { border-bottom: 2px solid var(--accent); padding-bottom: 3px; }
.cmp td.none { color: var(--ink-4); }
.cmp-note { margin-top: 10px; font-size: 13px; color: var(--ink-4); }

.findings { max-width: 64ch; margin-top: 44px; }
.findings p { font-size: 17px; line-height: 1.68; color: var(--ink-2); margin: 0 0 18px; }

.trend { margin-top: 42px; border-top: 1px solid var(--line); padding-top: 24px; }
.trend h2 { font-size: 14px; font-weight: 500; color: var(--ink-3); margin: 0 0 18px; }
.trend-item { margin-bottom: 20px; }
.trend-item h3 { font-family: var(--sans); font-size: 15px; font-weight: 500; margin: 0 0 6px; color: var(--ink); }
.trend-line { font-size: 14px; line-height: 1.6; color: var(--ink-3); }
.trend-line b { font-weight: 500; color: var(--ink-2); }
.trend-line .n { color: var(--ink-2); }

.single { max-width: 60ch; margin-top: 8px; padding: 18px 20px; border: 1px solid var(--line); border-radius: 4px; font-size: 15px; line-height: 1.55; }
.section-gap { height: 22px; }
.stack { display: flex; flex-direction: column; gap: 0; }
"""

_NUMBER = re.compile(r"(" + re.escape(CURRENCY_SYMBOL) + r"\s?)?([+−-]?\d[\d,]*(?:\.\d+)?%?)")


def esc(text) -> str:
    return _html.escape(str(text), quote=True)


def mono(text: str) -> str:
    """Escape text and set every number in the mono face. A currency prefix stays in the text face."""
    text = str(text)
    out = []
    pos = 0
    for m in _NUMBER.finditer(text):
        out.append(esc(text[pos : m.start()]))
        if m.group(1):
            out.append(f'<span class="cur">{esc(CURRENCY_SYMBOL)}</span>')
        out.append(f'<span class="n">{esc(m.group(2))}</span>')
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def inject_css(extra: str = "") -> None:
    st.html(f"<style>{CSS}{extra}</style>")


def nameplate_html(reveal: bool) -> str:
    cls = "np reveal" if reveal else "np"
    return f'<div class="{cls}" aria-label="{esc(NAMEPLATE)}"><span class="np-text">{esc(NAMEPLATE)}</span></div>'


def _go(page: str) -> None:
    st.session_state.page = page


def sidebar(active: str) -> None:
    """Nameplate and the two destinations."""
    reveal = not st.session_state.get("_revealed", False)
    st.session_state["_revealed"] = True
    with st.sidebar:
        st.html(nameplate_html(reveal))
        for key, label in (("extract", "Extract"), ("compare", "Compare")):
            with st.container(key=f"nav_{key}_wrap"):
                st.button(label, key=f"nav_{key}", type="tertiary", on_click=_go, args=(key,))
    st.html(f"<style>.st-key-nav_{active}_wrap {{ }} .st-key-nav_{active}_wrap [data-testid='stButton'] button "
            f"{{ color: var(--plate-text) !important; font-weight: 500 !important; }} "
            f".st-key-nav_{active}_wrap [data-testid='stButton'] button::before "
            f"{{ transform: translateY(-50%) scaleX(1) !important; }}</style>")


def loading_html(message: str) -> str:
    return (
        f'<div class="ld wait"><div class="wait-track"></div>'
        f'<div class="wait-text"><span>{esc(message)}</span><span class="wait-clock"></span></div></div>'
    )


def busy_css(*container_keys: str) -> str:
    """Per-run rule that gives the named button containers the busy treatment."""
    selectors = ", ".join(f".st-key-{k} [data-testid='stButton'] button:disabled" for k in container_keys)
    hover = ", ".join(f".st-key-{k} [data-testid='stButton'] button:disabled:hover" for k in container_keys)
    return (
        f"<style>{selectors}, {hover} {{ background-color: var(--ink); "
        "background-image: linear-gradient(100deg, var(--ink) 0%, var(--ink) 38%, var(--ink-3) 50%, var(--ink) 62%, var(--ink) 100%); "
        "background-size: 280% 100%; border-color: var(--ink); animation: ld-sheen 1.7s linear infinite; } "
        + ", ".join(f".st-key-{k} [data-testid='stButton'] button:disabled p" for k in container_keys)
        + " { color: var(--plate-text) !important; }</style>"
    )


def check_glyph(ok: bool) -> str:
    """A tick or a cross drawn in CSS; inline SVG does not survive the st.html sanitiser."""
    return '<span class="tick"></span>' if ok else '<span class="cross"></span>'
