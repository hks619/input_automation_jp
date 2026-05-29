"""Step 4 — Run the splitting engine."""
from __future__ import annotations

import streamlit as st

from core.splitter import project_row_count, run_splitter


st.set_page_config(page_title="Step 4 · Split & disaggregate", layout="wide")
st.title("Step 4 — Split & Disaggregate")

if st.session_state.get("parsed") is None or st.session_state.parsed.has_errors:
    st.warning("Upload + geoprocess a template first.")
    st.stop()

parsed = st.session_state.parsed
defaults = st.session_state.defaults
projected = project_row_count(parsed.sheets)
ceiling = int(defaults.get("output_row_warning", 50000))

col1, col2, col3 = st.columns(3)
col1.metric("Input EXP_EQ rows", len(parsed.sheets["EXP_EQ"]))
col2.metric("Projected output rows", projected)
col3.metric("Pruning threshold", defaults.get("pruning_threshold"))

if projected > ceiling:
    st.warning(f"Projected output ({projected:,}) exceeds the configured ceiling ({ceiling:,}). Consider raising the pruning threshold on the Settings page.")

if st.button("▶ Run splitter", type="primary"):
    disagg, report = run_splitter(
        parsed.sheets,
        pruning_threshold=float(defaults.get("pruning_threshold", 0.0001)),
    )
    st.session_state.disagg = disagg
    st.session_state.splitter_report = report
    # Log everything for the audit trail.
    for (sheet, lob), factor in report.rebasing_factors.items():
        st.session_state.audit.rebase(sheet, lob, factor)
    if report.pruned_combinations:
        st.session_state.audit.prune(
            report.pruned_combinations,
            report.pruned_share_redistributed,
            float(defaults.get("pruning_threshold", 0.0001)),
        )

if st.session_state.get("disagg") is not None:
    disagg = st.session_state.disagg
    report = st.session_state.splitter_report
    st.success(f"Generated {len(disagg):,} disaggregated records.")
    st.metric("Pruned combinations", report.pruned_combinations)
    st.metric("Pruned share redistributed", f"{report.pruned_share_redistributed:.4f}")
    with st.expander("Rebasing factors per (sheet, LOB)"):
        st.json({f"{k[0]} · {k[1]}": v for k, v in report.rebasing_factors.items()})
    st.subheader("Disaggregated preview (first 200 rows)")
    st.dataframe(disagg.head(200), use_container_width=True)
