"""Read and structurally validate the uploaded template.

Output:
    ParsedTemplate(
        sheets: dict[str, pandas.DataFrame],   # one DataFrame per template sheet
        issues: list[Issue],                   # structural validation findings
    )

The parser is forgiving about extra columns and the legend rows we wrote
into the template (row 2 = "required", row 3 = example). It strips them by
detecting their content.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Dict, List

import pandas as pd

from core.schema import SHEETS, SHEETS_BY_NAME, SheetSpec


@dataclass
class Issue:
    sheet: str
    severity: str  # "error" | "warn"
    message: str


@dataclass
class ParsedTemplate:
    sheets: Dict[str, pd.DataFrame] = field(default_factory=dict)
    issues: List[Issue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)


def _strip_legend_rows(df: pd.DataFrame, spec: SheetSpec) -> pd.DataFrame:
    """Drop the legend row (row 2: "required" markers) and the example row (row 3)
    that the template writer inserts. We detect them by content rather than
    position so a user who deleted them still parses cleanly.
    """
    if df.empty:
        return df
    out = df.copy()
    # Legend row: first column contains the literal "required".
    first_col = spec.columns[0]
    if first_col in out.columns:
        out = out[out[first_col].astype(str).str.lower() != "required"]
    # Example row: matches the spec's example tuple in the first few cells.
    if spec.example:
        example_first = spec.example[0]
        if example_first is not None and first_col in out.columns:
            # Drop only one matching row to avoid clobbering legitimate user data.
            mask = out[first_col].astype(str) == str(example_first)
            if mask.any():
                idx = out[mask].index[0]
                # Heuristic: also match the 2nd column of the example if present.
                if len(spec.example) > 1 and len(spec.columns) > 1:
                    second_col = spec.columns[1]
                    if second_col in out.columns and str(out.at[idx, second_col]) == str(spec.example[1]):
                        out = out.drop(index=idx)
                else:
                    out = out.drop(index=idx)
    return out.reset_index(drop=True)


def parse_template(file_bytes: bytes) -> ParsedTemplate:
    """Parse an uploaded .xlsx workbook into the canonical sheet dict."""
    result = ParsedTemplate()
    try:
        xls = pd.ExcelFile(BytesIO(file_bytes), engine="openpyxl")
    except Exception as e:  # pragma: no cover - defensive
        result.issues.append(Issue(sheet="(workbook)", severity="error",
                                   message=f"Could not open workbook: {e}"))
        return result

    found = set(xls.sheet_names)
    for spec in SHEETS:
        if spec.name not in found:
            result.issues.append(Issue(sheet=spec.name, severity="error",
                                       message="Required sheet is missing."))
            continue
        df = pd.read_excel(xls, sheet_name=spec.name, engine="openpyxl")
        # Drop any "NOTES" column the template wrote alongside the data.
        df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed") and str(c) != "NOTES"]]
        df = _strip_legend_rows(df, spec)
        # Column-level checks.
        missing_cols = [c for c in spec.columns if c not in df.columns]
        if missing_cols:
            result.issues.append(Issue(sheet=spec.name, severity="error",
                                       message=f"Missing columns: {missing_cols}"))
        # Required-column null checks.
        for col in spec.required:
            if col in df.columns:
                null_count = df[col].isna().sum()
                if null_count:
                    result.issues.append(Issue(
                        sheet=spec.name, severity="error",
                        message=f"Required column '{col}' has {null_count} blank value(s)."))
        # Empty sheet (after legend strip) is a warning, not an error — analyst may not have data for it.
        if df.empty:
            result.issues.append(Issue(sheet=spec.name, severity="warn",
                                       message="Sheet is empty after stripping legend/example rows."))
        result.sheets[spec.name] = df

    _cross_sheet_checks(result)
    return result


def _cross_sheet_checks(parsed: ParsedTemplate) -> None:
    """Key-integrity checks across sheets."""
    if "Account_Group" not in parsed.sheets or "EXP_EQ" not in parsed.sheets:
        return
    ag = parsed.sheets["Account_Group"]
    exp = parsed.sheets["EXP_EQ"]
    if "ACCNTNUM" in ag.columns and "ACCNTNUM" in exp.columns:
        orphan = set(exp["ACCNTNUM"].dropna()) - set(ag["ACCNTNUM"].dropna())
        if orphan:
            parsed.issues.append(Issue(
                sheet="EXP_EQ", severity="error",
                message=f"ACCNTNUM(s) in EXP_EQ not present in Account_Group: {sorted(orphan)}"))
    if "LOBNAME" in ag.columns and "LOBNAME" in exp.columns:
        orphan = set(exp["LOBNAME"].dropna()) - set(ag["LOBNAME"].dropna())
        if orphan:
            parsed.issues.append(Issue(
                sheet="EXP_EQ", severity="warn",
                message=f"LOBNAME(s) in EXP_EQ not present in Account_Group: {sorted(orphan)}"))

    # Every LOB referenced by EXP_EQ should have at least one row in each split sheet.
    exp_lobs = set(exp.get("LOBNAME", pd.Series(dtype=object)).dropna().astype(str))
    for sheet_name, lob_col in (("Occ", "LOB"), ("Cons", "LOBNAME"), ("BH", "LOB"), ("YB", "LOB")):
        if sheet_name not in parsed.sheets:
            continue
        s = parsed.sheets[sheet_name]
        if lob_col not in s.columns:
            continue
        split_lobs = set(s[lob_col].dropna().astype(str))
        missing = exp_lobs - split_lobs
        if missing:
            parsed.issues.append(Issue(
                sheet=sheet_name, severity="error",
                message=f"No split rows for LOB(s) {sorted(missing)} — EXP_EQ rows would not disaggregate."))
