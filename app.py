"""Landed. Run with: uv run streamlit run app.py"""

from pathlib import Path

import streamlit as st

_ICON = Path(__file__).resolve().parent / "static" / "favicon.png"
st.set_page_config(
    page_title="Landed",
    page_icon=str(_ICON) if _ICON.exists() else None,
    layout="wide",
    initial_sidebar_state="expanded",
)

from landed.ui import compare_screen, extract_screen, shell  # noqa: E402

shell.inject_css()

ss = st.session_state
ss.setdefault("page", "extract")
ss.setdefault("pending", None)
ss.setdefault("extraction", None)
ss.setdefault("written", None)
ss.setdefault("analysis", None)

shell.sidebar(active=ss.page)

if ss.page == "compare":
    compare_screen.render()
else:
    extract_screen.render()
