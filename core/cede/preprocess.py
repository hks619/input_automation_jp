"""Stage 1 — pre-CEDE-import transformations.

The CEDE database is delivered as flat tables. Before Data Bridge import we:
  1. Detect a missing/empty loss table and emit statements to create a
     dummy loss record with zero value so the import succeeds.
  2. Identify franchise deductibles (deductible type 'FR').
  3. Preserve the FR flag by appending '_FR' to a carried-through text field
     (default: a deductible currency / text field) so it survives import.
  4. Convert FR → S in the deductible type field so the deductible value
     ports through Data Bridge.
  5. Optionally adjust limit columns to match the EDM schema.

Inputs are pandas DataFrames (one per CEDE table). Outputs are:
  - transformed DataFrames
  - a list of SQL statements (as strings) the analyst can run against
    the CEDE staging database, OR can persist alongside the transformed CSVs.
  - a PreprocessReport (counts, samples) for the audit log.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd


# Common CEDE column names (these vary by version; configurable per cedent).
DEFAULT_LOC_TABLE = "LocCede"
DEFAULT_LOSS_TABLE = "LossCede"
DEFAULT_DED_TYPE_COL = "DedType1"
DEFAULT_DED_AMT_COL = "DedAmt1"
DEFAULT_DED_CUR_COL = "DedCur1"
DEFAULT_FLAG_COL = "DedTxt1"  # text carrier for the _FR marker; configurable.


@dataclass
class PreprocessReport:
    franchise_rows_flagged: int = 0
    franchise_rows_converted_to_S: int = 0
    dummy_loss_row_added: bool = False
    limit_adjustments: int = 0
    sample_flagged_rows: List[Dict] = field(default_factory=list)
    sql_statements: List[str] = field(default_factory=list)


def preprocess_cede(
    loc_df: pd.DataFrame,
    loss_df: Optional[pd.DataFrame] = None,
    *,
    cedent_id: str = "default",
    ded_type_col: str = DEFAULT_DED_TYPE_COL,
    ded_amt_col: str = DEFAULT_DED_AMT_COL,
    ded_cur_col: str = DEFAULT_DED_CUR_COL,
    flag_col: str = DEFAULT_FLAG_COL,
    loss_table_name: str = DEFAULT_LOSS_TABLE,
    flag_suffix: str = "_FR",
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], PreprocessReport]:
    """Apply the four CEDE preprocessing transformations."""
    report = PreprocessReport()
    loc = loc_df.copy()

    # 1. Missing/empty loss table → dummy zero loss record.
    if loss_df is None or loss_df.empty:
        loss_df = pd.DataFrame([{
            "LossID": "DUMMY-0001",
            "PortNum": loc["PortNum"].iloc[0] if "PortNum" in loc.columns and not loc.empty else 1,
            "AccGrpID": loc["AccGrpID"].iloc[0] if "AccGrpID" in loc.columns and not loc.empty else 1,
            "LossAmt": 0.0,
            "LossDate": None,
        }])
        report.dummy_loss_row_added = True
        report.sql_statements.append(
            f"-- Stage 1.1 dummy loss insert (auto-generated; cedent={cedent_id})\n"
            f"INSERT INTO {loss_table_name} (LossID, PortNum, AccGrpID, LossAmt) "
            f"VALUES ('DUMMY-0001', 1, 1, 0);"
        )

    # 2 + 3 + 4. Franchise-deductible handling.
    if ded_type_col in loc.columns:
        fr_mask = loc[ded_type_col].astype(str).str.upper() == "FR"
        if fr_mask.any():
            # Ensure flag column exists.
            if flag_col not in loc.columns:
                loc[flag_col] = ""
            loc.loc[fr_mask, flag_col] = (
                loc.loc[fr_mask, flag_col].fillna("").astype(str) + flag_suffix
            )
            report.franchise_rows_flagged = int(fr_mask.sum())
            # Convert FR → S so the deductible value ports through Data Bridge.
            loc.loc[fr_mask, ded_type_col] = "S"
            report.franchise_rows_converted_to_S = int(fr_mask.sum())
            report.sample_flagged_rows = (
                loc.loc[fr_mask, [c for c in (ded_type_col, ded_amt_col, ded_cur_col, flag_col)
                                  if c in loc.columns]]
                .head(5).to_dict(orient="records")
            )
            report.sql_statements.append(
                f"-- Stage 1.2 franchise-deductible preservation (auto-generated; cedent={cedent_id})\n"
                f"-- Mark FR rows with '{flag_suffix}' suffix in {flag_col}, then switch FR→S.\n"
                f"UPDATE LocCede SET {flag_col} = CONCAT(COALESCE({flag_col}, ''), '{flag_suffix}'), "
                f"{ded_type_col} = 'S' WHERE {ded_type_col} = 'FR';"
            )

    return loc, loss_df, report
