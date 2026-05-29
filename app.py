"""RMS Exposure Preparation tool — Streamlit entry point.

The app is multipage; each step is a separate file in pages/. Shared state
lives in st.session_state and is initialized here.
"""
from __future__ import annotations

import streamlit as st

from core.audit import AuditLog
from core.geoprocess import load_defaults


def _init_session_state() -> None:
    ss = st.session_state
    ss.setdefault("parsed", None)              # ParsedTemplate
    ss.setdefault("mapping", {"occ": {}, "cons": {}})  # cedent value→RMS code map
    ss.setdefault("disagg", None)              # disaggregated DataFrame
    ss.setdefault("splitter_report", None)
    ss.setdefault("output_df", None)
    ss.setdefault("validation_report", None)
    ss.setdefault("recon_df", None)
    ss.setdefault("audit", AuditLog())
    ss.setdefault("defaults", load_defaults())
    ss.setdefault("override_reason", "")


def main() -> None:
    st.set_page_config(
        page_title="RMS Exposure Prep — input_automation_jp",
        page_icon="📊",
        layout="wide",
    )
    _init_session_state()

    st.title("RMS Exposure Preparation")
    st.caption("Convert cedent exposure data → RMS RiskLink-ready tab-separated `.txt`, with first-class support for Japan renewals.")

    st.markdown(
        """
        ### Workflow
        Use the sidebar to navigate the six steps in order. State is preserved
        across pages — you can go back and re-run a step without re-uploading.

        1. **Download template** — blank multi-sheet `.xlsx`.
        2. **Upload filled template** — structural validation.
        3. **Geoprocess** — value matching + geography resolution.
        4. **Split & disaggregate** — apply Occ × Cons × BH × YB splits.
        5. **Validate & reconcile** — TIV + count checks (must pass to download).
        6. **Generate output** — `.txt`, audit log, recon report (as zip).

        A separate **CEDE / Franchise-Deductible** tab handles the
        Risk Modeler / Data Bridge `FR` deductible workflow.
        """
    )

    with st.expander("Assumptions in effect (Section 13 defaults)", expanded=False):
        d = st.session_state.defaults
        st.markdown(
            f"""
            - **Peril rule:** `{d.get('peril_rule')}` (WS coverage values relative to EQ)
            - **Default currency:** `{d.get('default_currency')}`
            - **SITELIM rule:** `{d.get('sitelim_rule')}`
            - **Pruning threshold:** `{d.get('pruning_threshold')}` (combinations below this are removed and redistributed)
            - **CEDE live DB:** `{d.get('cede_live_db')}` (scripts-only mode by default)
            - **Output line ending:** `{repr(d.get('output_line_ending'))}`

            Change these on the **Settings** page.
            """
        )


if __name__ == "__main__":
    main()
