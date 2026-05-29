"""Disaggregation engine.

Each EXP_EQ row is exploded into the cross-product of the four split
dimensions (Occ × Cons × BH × YB). For each combination, proportions are
multiplied (independence assumption) and quantities are allocated.

Correctness property: summed allocated values equal input totals within the
recon tolerance, and summed allocated building counts equal input NUMBLDGS
EXACTLY (largest-remainder rounding).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from core.schema import EQ_VALUE_COLS, WS_VALUE_COLS


# Split-sheet dimension metadata: (sheet_name, lob_col, share_col, attribute_cols)
# `attribute_cols` are the columns that get stamped onto the output row from
# the selected split row.
SPLIT_DIMS: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    ("Occ",  "LOB",     "Occ_split",  ("OCCSCHEME", "OCCTYPE", "OCC")),
    ("Cons", "LOBNAME", "Cons_split", ("BLDGSCHEME", "BLDGCLASS", "Construction")),
    ("BH",   "LOB",     "BH_split",   ("NUMSTORIES", "BLDG_HEIGHT_REF")),
    ("YB",   "LOB",     "YB_split",   ("YEARBUILT", "YEARBUILT_BAND")),
)


@dataclass
class SplitterReport:
    """Diagnostics about a single splitter run, for the audit log."""
    rebasing_factors: Dict[Tuple[str, str], float] = field(default_factory=dict)
    pruned_combinations: int = 0
    pruned_share_redistributed: float = 0.0
    output_row_count: int = 0
    per_exp_row_combinations: List[int] = field(default_factory=list)


def _rebase(
    split_df: pd.DataFrame,
    lob: str,
    lob_col: str,
    share_col: str,
    report: SplitterReport,
    sheet_name: str,
) -> pd.DataFrame:
    """Return rows of split_df where lob_col == lob with shares rebased to sum to 1.0.

    If `share_col` is missing or empty, fall back to `Pre_Rebased_Percentage`
    (Occ sheet pattern) when present.
    """
    sub = split_df[split_df[lob_col].astype(str) == str(lob)].copy()
    if sub.empty:
        return sub

    # Prefer the rebased column if populated; otherwise rebase from
    # Pre_Rebased_Percentage; otherwise rebase from share_col itself.
    if share_col in sub.columns and sub[share_col].notna().any() and sub[share_col].sum() > 0:
        weights = sub[share_col].astype(float).fillna(0.0)
    elif "Pre_Rebased_Percentage" in sub.columns and sub["Pre_Rebased_Percentage"].notna().any():
        weights = sub["Pre_Rebased_Percentage"].astype(float).fillna(0.0)
    else:
        weights = sub[share_col].astype(float).fillna(0.0) if share_col in sub.columns else pd.Series(np.ones(len(sub)))

    total = float(weights.sum())
    if total <= 0:
        # Nothing usable — assign uniform.
        weights = pd.Series(np.ones(len(sub)) / len(sub), index=sub.index)
        total = 1.0
    rebased = weights / total
    sub[share_col] = rebased.values
    report.rebasing_factors[(sheet_name, str(lob))] = total
    return sub


def _largest_remainder_round(proportions: np.ndarray, total: int) -> np.ndarray:
    """Allocate `total` integer units across len(proportions) buckets so they
    sum exactly to `total`. Uses the largest-remainder method (Hare).
    """
    if total <= 0 or proportions.size == 0:
        return np.zeros(proportions.size, dtype=int)
    raw = proportions * total
    floor = np.floor(raw).astype(int)
    remainder = raw - floor
    deficit = int(total - floor.sum())
    if deficit > 0:
        # Award the deficit to the buckets with the largest remainders.
        top = np.argsort(-remainder)[:deficit]
        floor[top] += 1
    elif deficit < 0:
        # Pull back from the smallest remainders (rare, but possible with float drift).
        bot = np.argsort(remainder)[: -deficit]
        floor[bot] -= 1
    return floor


def run_splitter(
    sheets: Dict[str, pd.DataFrame],
    pruning_threshold: float = 0.0001,
) -> Tuple[pd.DataFrame, SplitterReport]:
    """Disaggregate EXP_EQ rows into a long-form DataFrame.

    Returns:
        (disagg_df, report)

    disagg_df columns include:
        ACCNTNUM, LOBNAME, geography (CNTRYCODE, POSTCODE, STATE, COUNTY, DISTRICT, CRESTA, CNTRYSCHEME),
        currency, NUMBLDGS (allocated), BLDG/CONT/BI (allocated),
        SITELIM (per sitelim_rule — handled by caller; here we just copy),
        OCC, OCCSCHEME, OCCTYPE, Construction, BLDGSCHEME, BLDGCLASS,
        NUMSTORIES, BLDG_HEIGHT_REF, YEARBUILT, YEARBUILT_BAND,
        combo_proportion (for audit).
    """
    report = SplitterReport()
    exp = sheets["EXP_EQ"].copy()
    out_rows: List[pd.DataFrame] = []

    for _, row in exp.iterrows():
        lob = row["LOBNAME"]
        # Pull rebased per-dimension frames.
        dim_frames: List[pd.DataFrame] = []
        skip = False
        for sheet_name, lob_col, share_col, _ in SPLIT_DIMS:
            df = sheets.get(sheet_name)
            if df is None or df.empty or lob_col not in df.columns:
                skip = True
                break
            rebased = _rebase(df, lob, lob_col, share_col, report, sheet_name)
            if rebased.empty:
                skip = True
                break
            dim_frames.append(rebased)
        if skip:
            continue

        # Cross-product. Start with a 1-row marker and merge each dimension via cross join.
        # pandas .merge(how='cross') is available in 1.2+.
        combo = dim_frames[0].assign(_join=1)
        combo["_proportion"] = combo[SPLIT_DIMS[0][2]]
        for i in range(1, len(dim_frames)):
            right = dim_frames[i].assign(_join=1)
            share_col_i = SPLIT_DIMS[i][2]
            combo = combo.merge(right, on="_join", suffixes=("", f"_{SPLIT_DIMS[i][0]}"))
            combo["_proportion"] = combo["_proportion"] * combo[share_col_i]
        combo = combo.drop(columns=[c for c in combo.columns if c == "_join"])

        # Prune negligible combinations and redistribute their proportion.
        keep_mask = combo["_proportion"] >= pruning_threshold
        pruned_share = float(combo.loc[~keep_mask, "_proportion"].sum())
        if pruned_share > 0:
            report.pruned_combinations += int((~keep_mask).sum())
            report.pruned_share_redistributed += pruned_share
            combo = combo.loc[keep_mask].copy()
            if combo.empty:
                continue
            # Renormalize so kept proportions sum to 1.0.
            combo["_proportion"] = combo["_proportion"] / combo["_proportion"].sum()

        # Allocate quantities.
        proportions = combo["_proportion"].to_numpy(dtype=float)
        n_buildings = int(row.get("NUMBLDGS", 0) or 0)
        alloc_bldgs = _largest_remainder_round(proportions, n_buildings)

        out = pd.DataFrame(index=combo.index)
        out["ACCNTNUM"] = row.get("ACCNTNUM")
        out["LOBNAME"] = lob
        # Geography passthrough.
        for col in ("STATE", "COUNTY", "DISTRICT", "POSTCODE", "CNTRYCODE", "CNTRYSCHEME", "CRESTA"):
            out[col] = row.get(col)
        out["CURRENCY"] = row.get("CURRENCY")
        out["NUMBLDGS"] = alloc_bldgs
        # Financial allocation (proportional, value-preserving up to float).
        out["BLDG"] = float(row.get("BLDG", 0) or 0) * proportions
        out["CONT"] = float(row.get("CONT", 0) or 0) * proportions
        out["BI"]   = float(row.get("BI",   0) or 0) * proportions
        # SITELIM: caller applies sitelim_rule; here we carry the raw value.
        out["SITELIM"] = float(row.get("SITELIM", 0) or 0)
        # Stamp split attributes.
        for sheet_name, _, _, attr_cols in SPLIT_DIMS:
            for attr in attr_cols:
                # Attribute column may have been suffixed during the cross-merge if it collided.
                if attr in combo.columns:
                    out[attr] = combo[attr].values
                else:
                    # Check suffixed variants.
                    for suffix_dim in (sheet_name,):
                        cand = f"{attr}_{suffix_dim}"
                        if cand in combo.columns:
                            out[attr] = combo[cand].values
                            break
        out["combo_proportion"] = proportions
        report.per_exp_row_combinations.append(len(out))
        out_rows.append(out)

    if not out_rows:
        return pd.DataFrame(), report

    disagg = pd.concat(out_rows, ignore_index=True)
    report.output_row_count = len(disagg)
    return disagg, report


def project_row_count(sheets: Dict[str, pd.DataFrame]) -> int:
    """Cheap projection of the worst-case output-row count, shown to the analyst
    before they trigger a full split. Ignores pruning."""
    exp = sheets.get("EXP_EQ")
    if exp is None or exp.empty:
        return 0
    total = 0
    for lob in exp["LOBNAME"].dropna().unique():
        size = 1
        for sheet_name, lob_col, _, _ in SPLIT_DIMS:
            s = sheets.get(sheet_name)
            if s is None or lob_col not in s.columns:
                size = 0
                break
            n = int((s[lob_col].astype(str) == str(lob)).sum())
            if n == 0:
                size = 0
                break
            size *= n
        # Each EXP_EQ row for this LOB contributes `size` output rows.
        n_exp_rows = int((exp["LOBNAME"].astype(str) == str(lob)).sum())
        total += n_exp_rows * size
    return total
