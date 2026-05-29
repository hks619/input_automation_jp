"""Step 6 — Generate downloadable outputs (.txt + audit + recon, as a zip)."""
from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from core.txt_writer import to_tsv_bytes
from core.validation import reconciliation_report_md


st.set_page_config(page_title="Step 6 · Generate output", layout="wide")
st.title("Step 6 — Generate Output")

if st.session_state.get("output_df") is None or st.session_state.get("validation_report") is None:
    st.warning("Validate first (Step 5).")
    st.stop()

report = st.session_state.validation_report
override = bool(st.session_state.get("override_reason"))

if not report.passing and not override:
    st.error("Cannot generate output — validation is failing and no override is recorded.")
    st.stop()

defaults = st.session_state.defaults
out_df = st.session_state.output_df
recon = st.session_state.recon_df

txt_bytes = to_tsv_bytes(out_df, line_ending=defaults.get("output_line_ending", "\r\n"))
recon_md = reconciliation_report_md(recon)

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
out_name = f"exposure_{stamp}.txt"

st.session_state.audit.output(len(out_df), out_name)

col1, col2, col3, col4 = st.columns(4)
col1.download_button(
    label="⬇️  exposure.txt",
    data=txt_bytes,
    file_name=out_name,
    mime="text/tab-separated-values",
)
col2.download_button(
    label="⬇️  audit_log.md",
    data=st.session_state.audit.to_markdown().encode("utf-8"),
    file_name=f"audit_{stamp}.md",
)
col3.download_button(
    label="⬇️  audit_log.json",
    data=st.session_state.audit.to_json().encode("utf-8"),
    file_name=f"audit_{stamp}.json",
)
col4.download_button(
    label="⬇️  reconciliation.md",
    data=recon_md.encode("utf-8"),
    file_name=f"reconciliation_{stamp}.md",
)

st.divider()
zip_bytes = st.session_state.audit.to_zip(txt_bytes, recon_md, output_txt_filename=out_name)
st.download_button(
    label="📦 Download everything as zip",
    data=zip_bytes,
    file_name=f"rms_exposure_bundle_{stamp}.zip",
    mime="application/zip",
    type="primary",
)

st.subheader("Output preview (first 50 rows)")
st.dataframe(out_df.head(50), use_container_width=True)
