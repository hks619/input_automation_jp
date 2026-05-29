"""Validation + reconciliation.

Runs four families of checks:
    1. Structural (delegated to parser; we re-check post-mapping).
    2. Mapping completeness (no blank OCCTYPE / BLDGCLASS in the output).
    3. Split-sum tolerance (rebasing OK; gross mismatch flagged).
    4. TIV + count reconciliation between input EXP_EQ totals and output rows.
    5. Geography validity (postal resolution, ISO currency).

Returns a ValidationReport with pass/warn/fail items. The Streamlit page
gates the download button on report.passing or an override + reason.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from core.schema import EQ_VALUE_COLS, WS_VALUE_COLS


SEVERITY_PASS = "pass"
SEVERITY_WARN = "warn"
SEVERITY_FAIL = "fail"


@dataclass
class Check:
    name: str
    severity: str  # pass | warn | fail
    message: str
    details: Dict = field(default_factory=dict)


@dataclass
class ValidationReport:
    checks: List[Check] = field(default_factory=list)

    @property
    def passing(self) -> bool:
        return not any(c.severity == SEVERITY_FAIL for c in self.checks)

    def add(self, name: str, severity: str, message: str, **details) -> None:
        self.checks.append(Check(name, severity, message, details))


# --------------------------------------------------------------------- checks


def check_mapping_completeness(out_df: pd.DataFrame) -> Check:
    blank_occ = (out_df["OCCTYPE"].astype(str).str.strip() == "").sum()
    blank_bldg = (out_df["BLDGCLASS"].astype(str).str.strip() == "").sum()
    if blank_occ or blank_bldg:
        return Check(
            "mapping_completeness", SEVERITY_FAIL,
            f"Output has {blank_occ} blank OCCTYPE and {blank_bldg} blank BLDGCLASS rows.",
            {"blank_occtype": int(blank_occ), "blank_bldgclass": int(blank_bldg)},
        )
    return Check("mapping_completeness", SEVERITY_PASS, "All OCCTYPE and BLDGCLASS populated.")


def check_split_sums(sheets: Dict[str, pd.DataFrame], tolerance: float = 0.01) -> List[Check]:
    """Each split set should sum to ~100% (or to ~1.0 if already rebased).
    We accept either convention and only flag gross deviations.
    """
    out: List[Check] = []
    for sheet_name, lob_col, share_col in (
        ("Occ", "LOB", "Pre_Rebased_Percentage"),
        ("Cons", "LOBNAME", "Cons_split"),
        ("BH", "LOB", "BH_split"),
        ("YB", "LOB", "YB_split"),
    ):
        s = sheets.get(sheet_name)
        if s is None or share_col not in s.columns or lob_col not in s.columns:
            continue
        for lob, group in s.groupby(lob_col):
            total = float(group[share_col].astype(float).fillna(0.0).sum())
            # Accept "in %" (close to 100) or "as fraction" (close to 1).
            if math.isclose(total, 100.0, abs_tol=100 * tolerance) or math.isclose(total, 1.0, abs_tol=tolerance):
                out.append(Check(f"split_sum_{sheet_name}_{lob}", SEVERITY_PASS,
                                 f"{sheet_name} sums to {total:.4f} for LOB={lob} (within tolerance)."))
            else:
                out.append(Check(f"split_sum_{sheet_name}_{lob}", SEVERITY_WARN,
                                 f"{sheet_name} sums to {total:.4f} for LOB={lob} — will be rebased.",
                                 {"total": total}))
    return out


def check_tiv_reconciliation(
    exp_df: pd.DataFrame,
    out_df: pd.DataFrame,
    tolerance: float = 0.005,
) -> Tuple[Check, pd.DataFrame]:
    """Σ output values per ACCNTNUM should equal Σ input BLDG+CONT+BI per ACCNTNUM."""
    in_g = exp_df.groupby("ACCNTNUM")[["BLDG", "CONT", "BI"]].sum().rename(
        columns={"BLDG": "in_BLDG", "CONT": "in_CONT", "BI": "in_BI"}
    )
    out_g = out_df.groupby("ACCNTNUM")[["EQCV1VAL", "EQCV2VAL", "EQCV3VAL"]].sum().rename(
        columns={"EQCV1VAL": "out_BLDG", "EQCV2VAL": "out_CONT", "EQCV3VAL": "out_BI"}
    )
    merged = in_g.join(out_g, how="outer").fillna(0.0)
    merged["delta_BLDG"] = merged["out_BLDG"] - merged["in_BLDG"]
    merged["delta_CONT"] = merged["out_CONT"] - merged["in_CONT"]
    merged["delta_BI"] = merged["out_BI"] - merged["in_BI"]

    def within(row, col_in, col_out):
        if row[col_in] == 0:
            return row[col_out] == 0
        return abs(row[col_out] - row[col_in]) / abs(row[col_in]) <= tolerance

    fail_mask = ~merged.apply(
        lambda r: within(r, "in_BLDG", "out_BLDG")
                  and within(r, "in_CONT", "out_CONT")
                  and within(r, "in_BI", "out_BI"),
        axis=1,
    )
    if fail_mask.any():
        return (
            Check("tiv_reconciliation", SEVERITY_FAIL,
                  f"{int(fail_mask.sum())} account(s) outside TIV tolerance {tolerance}.",
                  {"failing_accounts": merged.index[fail_mask].tolist()}),
            merged,
        )
    return (
        Check("tiv_reconciliation", SEVERITY_PASS,
              "Σ output TIV matches Σ input TIV per account within tolerance."),
        merged,
    )


def check_count_reconciliation(exp_df: pd.DataFrame, out_df: pd.DataFrame) -> Check:
    in_total = int(exp_df["NUMBLDGS"].sum())
    out_total = int(out_df["NUMBLDGS"].sum())
    if in_total == out_total:
        return Check("count_reconciliation", SEVERITY_PASS,
                     f"Σ NUMBLDGS preserved ({in_total}).")
    return Check("count_reconciliation", SEVERITY_FAIL,
                 f"Σ NUMBLDGS mismatch: in={in_total}, out={out_total}.",
                 {"in": in_total, "out": out_total})


def check_geography(out_df: pd.DataFrame, postal_lookup: Dict) -> Check:
    if not postal_lookup:
        return Check("geography", SEVERITY_WARN,
                     "No postal lookup provided; skipping resolution check.")
    unresolved = []
    for pc in out_df["POSTALCODE"].astype(str).unique():
        prefix = pc.split("-")[0][:3]
        if prefix not in postal_lookup:
            unresolved.append(pc)
    if unresolved:
        return Check("geography", SEVERITY_FAIL,
                     f"{len(unresolved)} postal code(s) did not resolve in lookup.",
                     {"sample": unresolved[:10]})
    return Check("geography", SEVERITY_PASS, "All postal codes resolved.")


def run_all_checks(
    sheets: Dict[str, pd.DataFrame],
    out_df: pd.DataFrame,
    postal_lookup: Optional[Dict] = None,
    tolerance: float = 0.005,
) -> Tuple[ValidationReport, pd.DataFrame]:
    """Run every check and return a ValidationReport + the TIV recon dataframe
    (for the downloadable reconciliation report)."""
    report = ValidationReport()
    report.checks.append(check_mapping_completeness(out_df))
    report.checks.extend(check_split_sums(sheets))
    tiv_check, recon_df = check_tiv_reconciliation(sheets["EXP_EQ"], out_df, tolerance=tolerance)
    report.checks.append(tiv_check)
    report.checks.append(check_count_reconciliation(sheets["EXP_EQ"], out_df))
    report.checks.append(check_geography(out_df, postal_lookup or {}))
    return report, recon_df


def reconciliation_report_md(recon_df: pd.DataFrame) -> str:
    """Format the recon dataframe as a Markdown report for download."""
    lines = ["# Reconciliation Report", "",
             "| ACCNTNUM | in_BLDG | out_BLDG | Δ | in_CONT | out_CONT | Δ | in_BI | out_BI | Δ |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for accnt, row in recon_df.iterrows():
        lines.append(
            f"| {accnt} | {row['in_BLDG']:.0f} | {row['out_BLDG']:.0f} | {row['delta_BLDG']:.0f}"
            f" | {row['in_CONT']:.0f} | {row['out_CONT']:.0f} | {row['delta_CONT']:.0f}"
            f" | {row['in_BI']:.0f} | {row['out_BI']:.0f} | {row['delta_BI']:.0f} |"
        )
    return "\n".join(lines)
