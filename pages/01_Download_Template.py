"""Step 1 — Download the blank multi-sheet template."""
from __future__ import annotations

import streamlit as st

from core.schema import SHEETS
from core.template_builder import build_template


st.set_page_config(page_title="Step 1 · Download template", layout="wide")
st.title("Step 1 — Download Template")

st.markdown(
    """
    Click below to download the blank Excel template. It contains six data
    sheets plus an Instructions sheet. Required columns are marked on row 2;
    row 3 shows an example you should delete before filling.
    """
)

template_bytes = build_template()
st.download_button(
    label="⬇️  Download blank template (.xlsx)",
    data=template_bytes,
    file_name="rms_exposure_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

with st.expander("Sheet structure overview"):
    for spec in SHEETS:
        st.markdown(f"**{spec.name}** — {spec.notes}")
        st.code(", ".join(spec.columns), language="text")
        st.caption(f"Required: {', '.join(spec.required)}")
