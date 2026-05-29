"""Tab-separated .txt output writer for RMS RiskLink import.

The header order is the single source of truth from core.schema.OUTPUT_HEADER.
This writer maps the disaggregated frame (from splitter) onto that header,
applies the peril rule (mirror_eq | separate_ws | blank_ws), populates
currencies, applies the sitelim rule, and assigns secondary modifiers from
the config-driven rules.
"""
from __future__ import annotations

from io import StringIO
from typing import Dict, Iterable, List, Optional

import pandas as pd

from core.schema import (
    EQ_CUR_COLS,
    EQ_VALUE_COLS,
    OUTPUT_HEADER,
    SEC_MOD_COLS,
    WS_CUR_COLS,
    WS_VALUE_COLS,
)


def _apply_secondary_modifiers(
    df: pd.DataFrame,
    rules: Iterable[dict],
) -> pd.DataFrame:
    """Stamp secondary modifier columns onto df from the (occ_type, bldg_class, lobname) keyed rules.

    A rule with "*" matches any value. The first matching rule wins.
    Unmatched rows get blanks.
    """
    for col in SEC_MOD_COLS:
        df[col] = ""
    rule_list = list(rules)
    if not rule_list:
        return df

    def match(row) -> Optional[dict]:
        for rule in rule_list:
            ok = True
            for key in ("occupancy_type", "bldg_class", "lobname"):
                want = str(rule.get(key, "*"))
                if want == "*":
                    continue
                col = {"occupancy_type": "OCCTYPE",
                       "bldg_class": "BLDGCLASS",
                       "lobname": "LOBNAME"}[key]
                got = str(row.get(col, ""))
                if got != want:
                    ok = False
                    break
            if ok:
                return rule
        return None

    for idx, row in df.iterrows():
        rule = match(row)
        if rule is None:
            continue
        for col in SEC_MOD_COLS:
            if col in rule:
                df.at[idx, col] = rule[col]
    return df


def build_output_frame(
    disagg: pd.DataFrame,
    defaults: dict,
    secondary_rules: Iterable[dict] = (),
) -> pd.DataFrame:
    """Project the disaggregated frame onto the exact OUTPUT_HEADER column order.

    Pure function — does not write to disk. Caller writes via to_tsv_bytes().
    """
    # Empty disaggregation → emit an empty frame with the right schema so
    # downstream code (validation, writer) can still operate.
    if disagg is None or disagg.empty:
        return pd.DataFrame({col: pd.Series(dtype=object) for col in OUTPUT_HEADER})

    df = disagg.copy()
    out = pd.DataFrame(index=df.index)

    def col_or(col: str, default):
        """Return df[col] if present, else a Series of `default` with the right index."""
        if col in df.columns:
            return df[col]
        return pd.Series(default, index=df.index)

    # Identity / geography passthrough.
    out["ACCNTNUM"] = col_or("ACCNTNUM", "")
    out["CNTRYSCHEME"] = col_or("CNTRYSCHEME", defaults.get("country_scheme_default", "ISO"))
    out["POSTALCODE"] = col_or("POSTCODE", "")
    out["CNTRYCODE"] = col_or("CNTRYCODE", defaults.get("country_default", "JP"))
    out["STATE"] = col_or("STATE", "")
    out["COUNTY"] = col_or("COUNTY", "")
    out["DISTRICT"] = col_or("DISTRICT", "")

    out["NUMBLDGS"] = col_or("NUMBLDGS", 0).astype(int)

    # EQ coverage values: cv1=BLDG, cv2=CONT, cv3=BI.
    out["EQCV1VAL"] = col_or("BLDG", 0.0)
    out["EQCV2VAL"] = col_or("CONT", 0.0)
    out["EQCV3VAL"] = col_or("BI",   0.0)

    # SITELIM rule: repeat_whole (default) — value copied per row; divide_proportional
    # (multiply by combo_proportion).
    if defaults.get("sitelim_rule", "repeat_whole") == "divide_proportional":
        out["EQSITELIM"] = col_or("SITELIM", 0.0) * col_or("combo_proportion", 1.0)
    else:
        out["EQSITELIM"] = col_or("SITELIM", 0.0)

    # WS coverage values per peril_rule.
    peril_rule = defaults.get("peril_rule", "mirror_eq")
    if peril_rule == "mirror_eq":
        out["WSCV1VAL"] = out["EQCV1VAL"]
        out["WSCV2VAL"] = out["EQCV2VAL"]
        out["WSCV3VAL"] = out["EQCV3VAL"]
        out["WSSITELIM"] = out["EQSITELIM"]
    elif peril_rule == "blank_ws":
        out["WSCV1VAL"] = 0
        out["WSCV2VAL"] = 0
        out["WSCV3VAL"] = 0
        out["WSSITELIM"] = 0
    elif peril_rule == "separate_ws":
        # Caller must have merged WS columns into df before calling.
        for src, dst in (("WS_BLDG", "WSCV1VAL"), ("WS_CONT", "WSCV2VAL"),
                         ("WS_BI", "WSCV3VAL"), ("WS_SITELIM", "WSSITELIM")):
            out[dst] = col_or(src, 0.0)
    else:
        raise ValueError(f"Unknown peril_rule: {peril_rule}")

    # Currencies — single per portfolio by default.
    cur = col_or("CURRENCY", defaults.get("default_currency", "JPY"))
    for c in EQ_CUR_COLS + WS_CUR_COLS:
        out[c] = cur

    # Occupancy / construction / storeys / year built.
    out["OCCSCHEME"] = col_or("OCCSCHEME", "")
    out["OCCTYPE"]   = col_or("OCCTYPE", "")
    out["BLDGSCHEME"] = col_or("BLDGSCHEME", "")
    out["BLDGCLASS"]  = col_or("BLDGCLASS", "")
    out["NUMSTORIES"] = col_or("NUMSTORIES", "")
    out["YEARBUILT"]  = col_or("YEARBUILT", "")

    # Secondary modifiers — need LOBNAME for the matcher, so attach it temporarily.
    out["LOBNAME"] = col_or("LOBNAME", "")
    out = _apply_secondary_modifiers(out, secondary_rules)
    out = out.drop(columns=["LOBNAME"])

    # Enforce exact column order.
    return out.loc[:, list(OUTPUT_HEADER)]


def to_tsv_bytes(out_df: pd.DataFrame, line_ending: str = "\r\n") -> bytes:
    """Serialize the projected frame to UTF-8 tab-separated bytes."""
    # Use to_csv with sep='\t', then re-encode line endings since pandas uses '\n' internally.
    buf = StringIO()
    out_df.to_csv(buf, sep="\t", index=False, lineterminator="\n")
    text = buf.getvalue()
    if line_ending != "\n":
        text = text.replace("\n", line_ending)
    return text.encode("utf-8")
