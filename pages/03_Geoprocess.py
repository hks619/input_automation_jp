"""Step 3 — Value matching + geography resolution.

Interactive mapping of cedent raw values → RMS scheme codes, plus geography
validation. Confirmed mappings are persisted per-cedent so renewals pre-fill.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.geoprocess import (
    annotate_geography,
    load_bldg_codes,
    load_cedent_mapping,
    load_occ_codes,
    load_postal_lookup,
    save_cedent_mapping,
    suggest_bldg_codes,
    suggest_occ_codes,
    unmapped_values,
)


st.set_page_config(page_title="Step 3 · Geoprocess", layout="wide")
st.title("Step 3 — Geoprocess / Value Matching")

if st.session_state.get("parsed") is None or st.session_state.parsed.has_errors:
    st.warning("Upload a structurally valid template first (Step 2).")
    st.stop()

parsed = st.session_state.parsed

# Identify cedent for per-cedent mapping persistence.
ag = parsed.sheets["Account_Group"]
cedent_id = str(ag["CEDANTID"].dropna().iloc[0]) if "CEDANTID" in ag.columns and not ag["CEDANTID"].dropna().empty else "default"
st.caption(f"Cedent: `{cedent_id}` — confirmed mappings persist to `config/mappings/{cedent_id}.yaml`.")

# Initialize mapping state from disk on first visit.
if not st.session_state.mapping.get("occ") and not st.session_state.mapping.get("cons"):
    persisted = load_cedent_mapping(cedent_id)
    if persisted:
        st.session_state.mapping = persisted
        st.info(f"Pre-loaded {len(persisted.get('occ', {}))} occupancy and {len(persisted.get('cons', {}))} construction mappings from prior renewal.")

mapping = st.session_state.mapping
occ_codes = load_occ_codes()
bldg_codes = load_bldg_codes()

# --------------------------------------------------------------- 5A. Mappings
st.header("5A · Value matching")

st.subheader("Occupancy")
distinct_occ = sorted({str(v) for v in parsed.sheets["Occ"]["OCC"].dropna()})
for raw in distinct_occ:
    cols = st.columns([2, 3, 1])
    cols[0].write(f"**{raw}**")
    suggestions = suggest_occ_codes(raw, occ_codes)
    options = [f"{s.target} — {s.description} ({s.score}%)" for s in suggestions]
    options = ["(unmapped)"] + options + ["Type code…"]
    current = mapping.get("occ", {}).get(raw)
    default_idx = 0
    if current:
        for i, s in enumerate(suggestions):
            if s.target == current:
                default_idx = i + 1
                break
    choice = cols[1].selectbox(f"map_occ_{raw}", options, index=default_idx, label_visibility="collapsed")
    if choice.startswith("(unmapped)"):
        chosen = None
    elif choice == "Type code…":
        chosen = cols[1].text_input(f"manual_occ_{raw}", value=current or "", label_visibility="collapsed")
    else:
        chosen = choice.split(" — ")[0]
    if cols[2].button("Confirm", key=f"confirm_occ_{raw}"):
        if chosen:
            mapping.setdefault("occ", {})[raw] = chosen
            st.session_state.audit.mapping(raw, chosen, confirmed_by="analyst")
            st.success(f"Mapped {raw} → {chosen}")

st.subheader("Construction")
distinct_cons = sorted({str(v) for v in parsed.sheets["Cons"]["Construction"].dropna()})
for raw in distinct_cons:
    cols = st.columns([2, 3, 1])
    cols[0].write(f"**{raw}**")
    suggestions = suggest_bldg_codes(raw, bldg_codes)
    options = [f"{s.target} — {s.description} ({s.score}%)" for s in suggestions]
    options = ["(unmapped)"] + options + ["Type code…"]
    current = mapping.get("cons", {}).get(raw)
    default_idx = 0
    if current:
        for i, s in enumerate(suggestions):
            if s.target == current:
                default_idx = i + 1
                break
    choice = cols[1].selectbox(f"map_cons_{raw}", options, index=default_idx, label_visibility="collapsed")
    if choice.startswith("(unmapped)"):
        chosen = None
    elif choice == "Type code…":
        chosen = cols[1].text_input(f"manual_cons_{raw}", value=current or "", label_visibility="collapsed")
    else:
        chosen = choice.split(" — ")[0]
    if cols[2].button("Confirm", key=f"confirm_cons_{raw}"):
        if chosen:
            mapping.setdefault("cons", {})[raw] = chosen
            st.session_state.audit.mapping(raw, chosen, confirmed_by="analyst")
            st.success(f"Mapped {raw} → {chosen}")

# Apply confirmed mappings back onto the parsed split sheets so the splitter
# emits the RMS codes (not the raw labels).
def _apply_mappings(sheets):
    if mapping.get("occ"):
        occ = sheets["Occ"].copy()
        occ["OCCTYPE"] = occ.apply(
            lambda r: mapping["occ"].get(str(r["OCC"]), r["OCCTYPE"]), axis=1)
        sheets["Occ"] = occ
    if mapping.get("cons"):
        cons = sheets["Cons"].copy()
        cons["BLDGCLASS"] = cons.apply(
            lambda r: mapping["cons"].get(str(r["Construction"]), r["BLDGCLASS"]), axis=1)
        sheets["Cons"] = cons
    return sheets

unresolved = unmapped_values(parsed.sheets, mapping)
if unresolved["occ"] or unresolved["cons"]:
    st.warning(
        f"Unmapped values remain — occupancy: {unresolved['occ']}, construction: {unresolved['cons']}."
        " These will block output until mapped."
    )
else:
    st.success("All cedent values mapped to RMS codes.")
    parsed.sheets = _apply_mappings(parsed.sheets)

if st.button("💾 Save mappings for this cedent"):
    save_cedent_mapping(cedent_id, mapping)
    st.success(f"Saved to config/mappings/{cedent_id}.yaml")

# ----------------------------------------------------------- 5B. Geography
st.divider()
st.header("5B · Geography resolution")
postal_lookup = load_postal_lookup()
exp = parsed.sheets["EXP_EQ"]
annot = annotate_geography(exp, postal_lookup)
unresolved_postal = annot.loc[~annot["_postal_resolved"], "POSTCODE"].astype(str).tolist()
st.metric("Postal codes resolved", f"{int(annot['_postal_resolved'].sum())} / {len(annot)}")
if unresolved_postal:
    st.error(f"Unresolved postal codes: {unresolved_postal}")
st.dataframe(
    annot[["POSTCODE", "CNTRYCODE", "STATE", "_resolved_prefecture", "_resolved_cresta", "_postal_resolved"]],
    use_container_width=True,
)
