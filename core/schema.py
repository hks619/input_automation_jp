"""Single source of truth for the input template and the output txt header.

Template builder, parser, writer, and validation all read from this module so
the schema cannot drift across components.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Output (.txt) header — exact order required by RMS RiskLink import.
# ---------------------------------------------------------------------------
OUTPUT_HEADER: Tuple[str, ...] = (
    "ACCNTNUM",
    "CNTRYSCHEME",
    "POSTALCODE",
    "CNTRYCODE",
    "STATE",
    "COUNTY",
    "DISTRICT",
    "NUMBLDGS",
    "EQCV1VAL",
    "EQCV2VAL",
    "EQCV3VAL",
    "EQSITELIM",
    "WSCV1VAL",
    "WSCV2VAL",
    "WSCV3VAL",
    "WSSITELIM",
    "EQCV1VCUR",
    "EQCV2VCUR",
    "EQCV3VCUR",
    "EQSITELCUR",
    "WSCV1VCUR",
    "WSCV2VCUR",
    "WSCV3VCUR",
    "WSSITELCUR",
    "OCCSCHEME",
    "OCCTYPE",
    "ENGFOUND",
    "STRUCTUP",
    "IFMVERTICALEXPDIST",
    "IFMEQUIPBRACING",
    "BLDGSCHEME",
    "BLDGCLASS",
    "NUMSTORIES",
    "YEARBUILT",
)


# ---------------------------------------------------------------------------
# Input template — six sheets. Each sheet has a name, a column order, a list
# of required columns (a subset of columns), and an example row.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SheetSpec:
    name: str
    columns: Tuple[str, ...]
    required: Tuple[str, ...]
    example: Tuple = field(default_factory=tuple)
    notes: str = ""


ACCOUNT_GROUP = SheetSpec(
    name="Account_Group",
    columns=(
        "ACCNTNUM", "ACCNTNAME", "POLICYNUM", "POLICYTYPE", "LOBNAME",
        "CEDANTID", "CEDANTNAME", "PARTOF", "PARTOFCUR",
        "BLANLIMAMT", "BLANLIMCUR",
    ),
    required=("ACCNTNUM", "LOBNAME"),
    example=(
        "ACC-001", "Example Account", "POL-001", "Treaty", "RESID",
        "CED-JP-01", "Example Cedent JP", 1.0, "JPY",
        0, "JPY",
    ),
    notes="One row per policy/account. ACCNTNUM + LOBNAME are the keys joined to EXP_EQ and split sheets.",
)

EXP_EQ = SheetSpec(
    name="EXP_EQ",
    columns=(
        "ACCNTNUM", "LOBNAME",
        "STATE", "COUNTY", "DISTRICT", "POSTCODE", "CNTRYCODE", "CNTRYSCHEME", "CRESTA",
        "NUMBLDGS", "NUMFLOORS",
        "BLDG", "CONT", "BI", "eTIV", "SITELIM",
        "CURRENCY",
    ),
    required=(
        "ACCNTNUM", "LOBNAME", "POSTCODE", "CNTRYCODE",
        "NUMBLDGS", "BLDG", "CONT", "BI", "SITELIM", "CURRENCY",
    ),
    example=(
        "ACC-001", "RESID",
        "Tokyo", "Chiyoda", "Marunouchi", "100-0001", "JP", "ISO", "JP_13",
        10, 3,
        500_000_000, 100_000_000, 50_000_000, 650_000_000, 1_000_000_000,
        "JPY",
    ),
    notes="One row per aggregated exposure cell. Will be disaggregated into many output rows.",
)

OCC = SheetSpec(
    name="Occ",
    columns=(
        "LOB", "LOB_TYPE", "OCC", "OCCSCHEME", "OCCTYPE",
        "Pre_Rebased_Percentage", "Occ_split",
    ),
    required=("LOB", "OCC", "OCCSCHEME", "OCCTYPE", "Pre_Rebased_Percentage"),
    example=("RESID", "Residential", "Apartment", "RMS", "311", 60.0, None),
    notes="Occupancy distribution by LOB. Pre_Rebased_Percentage need not sum to 100; tool rebases.",
)

CONS = SheetSpec(
    name="Cons",
    columns=("Cedant", "LOBNAME", "Construction", "BLDGSCHEME", "BLDGCLASS", "Cons_split"),
    required=("LOBNAME", "Construction", "BLDGSCHEME", "BLDGCLASS", "Cons_split"),
    example=("CED-JP-01", "RESID", "Reinforced concrete", "RMS", "311", 0.7),
    notes="Construction-type distribution by LOB/cedant.",
)

BH = SheetSpec(
    name="BH",
    columns=("Cedant", "LOB", "NUMSTORIES", "BLDG_HEIGHT_REF", "BH_split"),
    required=("LOB", "NUMSTORIES", "BH_split"),
    example=("CED-JP-01", "RESID", 3, "Low-rise (1-3)", 0.5),
    notes="Building-height (storeys) distribution by LOB.",
)

YB = SheetSpec(
    name="YB",
    columns=("Cedant", "LOB", "YEARBUILT", "YEARBUILT_BAND", "YB_split"),
    required=("LOB", "YEARBUILT", "YB_split"),
    example=("CED-JP-01", "RESID", 2005, "2001-2010", 0.4),
    notes="Year-built distribution by LOB.",
)


SHEETS: Tuple[SheetSpec, ...] = (ACCOUNT_GROUP, EXP_EQ, OCC, CONS, BH, YB)
SHEETS_BY_NAME: Dict[str, SheetSpec] = {s.name: s for s in SHEETS}

# Names of the four split sheets, in the dimension order used by the splitter.
SPLIT_SHEETS: Tuple[str, ...] = ("Occ", "Cons", "BH", "YB")


# ---------------------------------------------------------------------------
# Output header helpers.
# ---------------------------------------------------------------------------
def output_header_line(separator: str = "\t") -> str:
    """Return the output header row joined by `separator`."""
    return separator.join(OUTPUT_HEADER)


# Subsets of the output header that the splitter populates from a single source.
EQ_VALUE_COLS: Tuple[str, ...] = ("EQCV1VAL", "EQCV2VAL", "EQCV3VAL")
WS_VALUE_COLS: Tuple[str, ...] = ("WSCV1VAL", "WSCV2VAL", "WSCV3VAL")
EQ_CUR_COLS:   Tuple[str, ...] = ("EQCV1VCUR", "EQCV2VCUR", "EQCV3VCUR", "EQSITELCUR")
WS_CUR_COLS:   Tuple[str, ...] = ("WSCV1VCUR", "WSCV2VCUR", "WSCV3VCUR", "WSSITELCUR")
GEO_COLS:      Tuple[str, ...] = ("CNTRYSCHEME", "POSTALCODE", "CNTRYCODE", "STATE", "COUNTY", "DISTRICT")
SEC_MOD_COLS:  Tuple[str, ...] = ("ENGFOUND", "STRUCTUP", "IFMVERTICALEXPDIST", "IFMEQUIPBRACING")
