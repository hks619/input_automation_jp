"""Step 2 — Upload the filled template."""
from __future__ import annotations

import streamlit as st

from core.audit import AuditLog
from core.parser import parse_template


st.set_page_config(page_title="Step 2 · Upload template", layout="wide")
st.title("Step 2 — Upload Filled Template")

if "audit" not in st.session_state:
    st.session_state.audit = AuditLog()

uploaded = st.file_uploader("Choose a filled .xlsx", type=["xlsx"])

if uploaded is not None:
    content = uploaded.read()
    parsed = parse_template(content)
    st.session_state.parsed = parsed
    st.session_state.audit.upload(uploaded.name, content)

    err = [i for i in parsed.issues if i.severity == "error"]
    warn = [i for i in parsed.issues if i.severity == "warn"]

    col1, col2 = st.columns(2)
    col1.metric("Errors", len(err), delta=None, delta_color="inverse")
    col2.metric("Warnings", len(warn))

    if err:
        st.error("Structural errors — fix the template and re-upload.")
        for i in err:
            st.write(f"**[{i.sheet}]** {i.message}")
    if warn:
        with st.expander(f"⚠️ {len(warn)} warning(s)"):
            for i in warn:
                st.write(f"**[{i.sheet}]** {i.message}")
    if not err:
        st.success("Template structurally valid. Proceed to Step 3 — Geoprocess.")

    st.divider()
    st.subheader("Sheet previews")
    for name, df in parsed.sheets.items():
        with st.expander(f"{name} — {len(df)} rows"):
            st.dataframe(df, use_container_width=True)
elif st.session_state.get("parsed") is not None:
    st.info("Template already uploaded this session. Re-upload to replace it.")
    parsed = st.session_state.parsed
    for name, df in parsed.sheets.items():
        with st.expander(f"{name} — {len(df)} rows"):
            st.dataframe(df, use_container_width=True)
