"""Settings — edit defaults and lookup files; persists back to config/."""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import yaml

from core.geoprocess import CONFIG_DIR, load_defaults


st.set_page_config(page_title="Settings", layout="wide")
st.title("Settings")

st.caption("Editing the defaults below writes back to `config/defaults.yaml` and updates this session's defaults.")

current = load_defaults()
edited = {}

edited["peril_rule"] = st.selectbox(
    "Peril rule",
    ["mirror_eq", "separate_ws", "blank_ws"],
    index=["mirror_eq", "separate_ws", "blank_ws"].index(current.get("peril_rule", "mirror_eq")),
    help="How to populate WS coverage values relative to EQ.",
)
edited["default_currency"] = st.text_input("Default currency", current.get("default_currency", "JPY"))
edited["sitelim_rule"] = st.selectbox(
    "SITELIM rule",
    ["repeat_whole", "divide_proportional"],
    index=["repeat_whole", "divide_proportional"].index(current.get("sitelim_rule", "repeat_whole")),
)
edited["output_line_ending"] = st.selectbox(
    "Output line ending",
    ["\\r\\n", "\\n"],
    index=0 if current.get("output_line_ending", "\r\n") == "\r\n" else 1,
)
edited["output_line_ending"] = "\r\n" if edited["output_line_ending"] == "\\r\\n" else "\n"
edited["pruning_threshold"] = st.number_input(
    "Pruning threshold", value=float(current.get("pruning_threshold", 0.0001)),
    format="%.6f", step=0.0001,
)
edited["output_row_warning"] = st.number_input(
    "Output row warning ceiling", value=int(current.get("output_row_warning", 50000)),
    step=1000,
)
edited["recon_tolerance"] = st.number_input(
    "Reconciliation tolerance", value=float(current.get("recon_tolerance", 0.005)),
    format="%.4f", step=0.001,
)
edited["cede_live_db"] = st.checkbox(
    "Allow CEDE module to attempt a read-only DB connection",
    value=bool(current.get("cede_live_db", False)),
)
edited["country_default"] = st.text_input("Default country code", current.get("country_default", "JP"))
edited["rebase_tolerance"] = float(current.get("rebase_tolerance", 0.01))

if st.button("💾 Save settings"):
    with (CONFIG_DIR / "defaults.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(edited, f, sort_keys=False)
    st.session_state.defaults = edited
    st.success("Saved to config/defaults.yaml.")

st.divider()
st.subheader("Lookup files (read-only preview)")
for fname in ("occ_scheme.yaml", "bldg_scheme.yaml",
              "secondary_modifiers.yaml", "japan_postal_to_cresta.yaml"):
    path = CONFIG_DIR / fname
    with st.expander(fname):
        if path.exists():
            st.code(path.read_text(encoding="utf-8"), language="yaml")
        else:
            st.write("(missing)")
