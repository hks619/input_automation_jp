"""Step 5 — Validation + reconciliation."""
from __future__ import annotations

import streamlit as st

from core.geoprocess import load_postal_lookup
from core.txt_writer import build_output_frame
from core.validation import run_all_checks


st.set_page_config(page_title="Step 5 · Validate", layout="wide")
st.title("Step 5 — Validate & Reconcile")

if st.session_state.get("disagg") is None:
    st.warning("Run the splitter first (Step 4).")
    st.stop()

defaults = st.session_state.defaults
disagg = st.session_state.disagg

# Build the output frame; load secondary modifier rules from config.
from core.geoprocess import load_secondary_modifier_config  # local import to keep header tidy
sec_cfg = load_secondary_modifier_config()
out_df = build_output_frame(disagg, defaults, secondary_rules=sec_cfg.get("rules", []))
st.session_state.output_df = out_df

report, recon = run_all_checks(
    st.session_state.parsed.sheets,
    out_df,
    postal_lookup=load_postal_lookup(),
    tolerance=float(defaults.get("recon_tolerance", 0.005)),
)
st.session_state.validation_report = report
st.session_state.recon_df = recon

for c in report.checks:
    icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(c.severity, "•")
    st.write(f"{icon} **{c.name}** — {c.message}")
    if c.details:
        with st.expander("details"):
            st.json(c.details)

st.divider()
st.subheader("Reconciliation by ACCNTNUM")
st.dataframe(recon, use_container_width=True)

# Log validation outcomes.
for c in report.checks:
    st.session_state.audit.validation(c.name, c.severity, **c.details)

if not report.passing:
    st.error("Validation failed — fix the underlying issue or override below.")
    reason = st.text_area("Override reason (required to enable download)")
    if reason.strip() and st.button("Apply override"):
        st.session_state.override_reason = reason.strip()
        st.session_state.audit.override(reason.strip(), by="analyst")
        st.success("Override recorded. You can proceed to Step 6.")
else:
    st.success("All checks pass. Proceed to Step 6 — Generate Output.")
