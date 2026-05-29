"""CEDE → Risk Modeler / Data Bridge franchise-deductible module.

Three sub-stages (each a downloadable artifact):
  1. Pre-processing — flag FR rows, switch FR→S, add dummy loss row if needed.
  2. Backup — generate T-SQL BACKUP DATABASE statements.
  3. Post-import fix — generate UPDATE statements that re-activate FR on
     the imported EDM tables.
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import streamlit as st

from core.cede.backup import generate_backup_sql
from core.cede.postimport_sql import generate_postimport_sql
from core.cede.preprocess import preprocess_cede


st.set_page_config(page_title="CEDE · Franchise deductible", layout="wide")
st.title("CEDE → Risk Modeler · Franchise-Deductible Module")

st.markdown(
    """
    Two known problems this module addresses:
    1. **Franchise deductibles** (`FR`) are not preserved through CEDE → Data Bridge import.
    2. Some portfolios have no loss table, but Risk Modeler requires one.

    The module is **auditable**: every transformation is logged with before/after.
    Default mode is **scripts-only** (no live DB connection).
    """
)

st.divider()
st.header("Stage 1 — Pre-processing")
st.write("Upload the CEDE location table (`LocCede`) and, optionally, the loss table (`LossCede`).")

cedent_id = st.text_input("Cedent identifier (used in audit / SQL comments)", value="default")

loc_upload = st.file_uploader("LocCede CSV", type=["csv"], key="loc_upload")
loss_upload = st.file_uploader("LossCede CSV (optional)", type=["csv"], key="loss_upload")

if loc_upload is not None:
    loc_df = pd.read_csv(loc_upload)
    loss_df = pd.read_csv(loss_upload) if loss_upload is not None else None

    transformed_loc, transformed_loss, report = preprocess_cede(loc_df, loss_df, cedent_id=cedent_id)
    st.session_state.audit.cede(
        "preprocess",
        franchise_flagged=report.franchise_rows_flagged,
        franchise_converted=report.franchise_rows_converted_to_S,
        dummy_loss_added=report.dummy_loss_row_added,
        cedent=cedent_id,
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("FR rows flagged", report.franchise_rows_flagged)
    col2.metric("FR → S conversions", report.franchise_rows_converted_to_S)
    col3.metric("Dummy loss added", "yes" if report.dummy_loss_row_added else "no")

    with st.expander("Sample of flagged rows (first 5)"):
        if report.sample_flagged_rows:
            st.dataframe(pd.DataFrame(report.sample_flagged_rows))
        else:
            st.write("None.")

    st.subheader("Stage-1 SQL")
    sql_text = "\n\n".join(report.sql_statements) or "-- No SQL emitted (no FR rows; loss table present)."
    st.code(sql_text, language="sql")

    # Downloads.
    st.download_button("⬇️  stage1_preprocess.sql", sql_text.encode("utf-8"),
                       file_name=f"stage1_preprocess_{cedent_id}.sql")
    buf = io.StringIO()
    transformed_loc.to_csv(buf, index=False)
    st.download_button("⬇️  LocCede_transformed.csv", buf.getvalue().encode("utf-8"),
                       file_name=f"LocCede_transformed_{cedent_id}.csv")
    if transformed_loss is not None:
        buf = io.StringIO()
        transformed_loss.to_csv(buf, index=False)
        st.download_button("⬇️  LossCede_transformed.csv", buf.getvalue().encode("utf-8"),
                           file_name=f"LossCede_transformed_{cedent_id}.csv")

st.divider()
st.header("Stage 2 — Backup")
backup_db = st.text_input("CEDE database name", value="CEDE_Staging")
backup_dir = st.text_input("Backup directory (UNC or local)", value=r"C:\Backups\CEDE")
if st.button("Generate backup SQL"):
    lines = generate_backup_sql(backup_db, backup_dir, suffix=cedent_id)
    sql = "\n".join(lines)
    st.code(sql, language="sql")
    st.download_button("⬇️  stage2_backup.sql", sql.encode("utf-8"),
                       file_name=f"stage2_backup_{cedent_id}.sql")
    st.session_state.audit.cede("backup_sql_generated", db=backup_db, dir=backup_dir)

st.divider()
st.header("Stage 3 — Post-import franchise re-activation")
edm_db = st.text_input("EDM database name (post-import)", value="EDM_Production")
if st.button("Generate post-import SQL"):
    lines = generate_postimport_sql(edm_db)
    sql = "\n".join(lines)
    st.code(sql, language="sql")
    st.download_button("⬇️  stage3_postimport.sql", sql.encode("utf-8"),
                       file_name=f"stage3_postimport_{cedent_id}.sql")
    st.session_state.audit.cede("postimport_sql_generated", db=edm_db)
