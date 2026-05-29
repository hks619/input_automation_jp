"""Shared fixtures.

Provides a small in-memory `sheets` dict that mimics the parsed template.
Used by splitter, writer, and validation tests so they share one truth.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Make the project root importable regardless of where pytest is invoked from.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def sample_sheets() -> dict:
    account = pd.DataFrame([
        {"ACCNTNUM": "ACC-1", "LOBNAME": "RESID", "ACCNTNAME": "A", "CEDANTID": "CED-1",
         "PARTOF": 1.0, "PARTOFCUR": "JPY", "BLANLIMAMT": 0, "BLANLIMCUR": "JPY"},
    ])
    exp = pd.DataFrame([
        {"ACCNTNUM": "ACC-1", "LOBNAME": "RESID",
         "STATE": "Tokyo", "COUNTY": "Chiyoda", "DISTRICT": "Marunouchi",
         "POSTCODE": "100-0001", "CNTRYCODE": "JP", "CNTRYSCHEME": "ISO", "CRESTA": "JP_13",
         "NUMBLDGS": 100, "NUMFLOORS": 3,
         "BLDG": 1_000_000_000, "CONT": 200_000_000, "BI": 50_000_000,
         "eTIV": 1_250_000_000, "SITELIM": 5_000_000_000, "CURRENCY": "JPY"},
    ])
    # 2 occ × 2 cons × 2 bh × 2 yb = 16 combinations per EXP row.
    occ = pd.DataFrame([
        {"LOB": "RESID", "LOB_TYPE": "Residential", "OCC": "Apartment",
         "OCCSCHEME": "RMS", "OCCTYPE": "311", "Pre_Rebased_Percentage": 60.0, "Occ_split": None},
        {"LOB": "RESID", "LOB_TYPE": "Residential", "OCC": "SFD",
         "OCCSCHEME": "RMS", "OCCTYPE": "300", "Pre_Rebased_Percentage": 40.0, "Occ_split": None},
    ])
    cons = pd.DataFrame([
        {"Cedant": "CED-1", "LOBNAME": "RESID", "Construction": "RC",
         "BLDGSCHEME": "RMS", "BLDGCLASS": "311", "Cons_split": 0.7},
        {"Cedant": "CED-1", "LOBNAME": "RESID", "Construction": "Wood",
         "BLDGSCHEME": "RMS", "BLDGCLASS": "100", "Cons_split": 0.3},
    ])
    bh = pd.DataFrame([
        {"Cedant": "CED-1", "LOB": "RESID", "NUMSTORIES": 3,
         "BLDG_HEIGHT_REF": "Low (1-3)", "BH_split": 0.6},
        {"Cedant": "CED-1", "LOB": "RESID", "NUMSTORIES": 8,
         "BLDG_HEIGHT_REF": "Mid (4-9)", "BH_split": 0.4},
    ])
    yb = pd.DataFrame([
        {"Cedant": "CED-1", "LOB": "RESID", "YEARBUILT": 2005,
         "YEARBUILT_BAND": "2001-2010", "YB_split": 0.5},
        {"Cedant": "CED-1", "LOB": "RESID", "YEARBUILT": 1985,
         "YEARBUILT_BAND": "1981-1990", "YB_split": 0.5},
    ])
    return {
        "Account_Group": account,
        "EXP_EQ": exp,
        "Occ": occ,
        "Cons": cons,
        "BH": bh,
        "YB": yb,
    }
