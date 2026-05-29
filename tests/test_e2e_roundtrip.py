"""End-to-end: filled sample template → parser → splitter → writer → validation.

Covers spec Section 12 acceptance criteria #2, #3, #4 in one test.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from core.parser import parse_template
from core.schema import OUTPUT_HEADER
from core.splitter import run_splitter
from core.template_builder import build_template
from core.txt_writer import build_output_frame, to_tsv_bytes
from core.validation import run_all_checks


SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "sample_filled_template.xlsx"


def test_blank_template_parses_structurally_cleanly():
    """The template the tool emits must itself round-trip with no structural
    errors (warnings about empty sheets are acceptable)."""
    parsed = parse_template(build_template())
    assert not parsed.has_errors, [
        (i.sheet, i.message) for i in parsed.issues if i.severity == "error"
    ]


@pytest.mark.skipif(not SAMPLE.exists(),
                    reason="Run `python sample_data/build_sample.py` first to generate the sample.")
def test_filled_sample_full_pipeline():
    parsed = parse_template(SAMPLE.read_bytes())
    assert not parsed.has_errors, [
        (i.sheet, i.message) for i in parsed.issues if i.severity == "error"
    ]

    sheets = parsed.sheets
    disagg, _ = run_splitter(sheets, pruning_threshold=0.0001)
    defaults = {
        "peril_rule": "mirror_eq",
        "default_currency": "JPY",
        "sitelim_rule": "repeat_whole",
        "country_default": "JP",
        "country_scheme_default": "ISO",
    }
    out = build_output_frame(disagg, defaults)
    assert tuple(out.columns) == OUTPUT_HEADER

    # Header line is tab-separated and matches spec.
    txt = to_tsv_bytes(out, line_ending="\n").decode("utf-8")
    assert txt.split("\n", 1)[0] == "\t".join(OUTPUT_HEADER)

    # TIV + count recon should pass for both accounts.
    postal_lookup = {"100": {"prefecture": "Tokyo", "cresta": "JP_13"},
                     "530": {"prefecture": "Osaka", "cresta": "JP_27"}}
    report, recon = run_all_checks(sheets, out, postal_lookup=postal_lookup)
    fails = [(c.name, c.message) for c in report.checks if c.severity == "fail"]
    assert not fails, fails

    # Σ output BLDG ≈ Σ input BLDG.
    in_tot = float(sheets["EXP_EQ"]["BLDG"].sum())
    out_tot = float(out["EQCV1VAL"].sum())
    assert math.isclose(in_tot, out_tot, rel_tol=1e-9)

    # Σ NUMBLDGS preserved exactly.
    assert int(out["NUMBLDGS"].sum()) == int(sheets["EXP_EQ"]["NUMBLDGS"].sum())
