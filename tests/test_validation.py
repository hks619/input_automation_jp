from __future__ import annotations

import pandas as pd

from core.splitter import run_splitter
from core.txt_writer import build_output_frame
from core.validation import (
    SEVERITY_FAIL,
    SEVERITY_PASS,
    check_count_reconciliation,
    check_mapping_completeness,
    check_tiv_reconciliation,
    run_all_checks,
)


def _defaults():
    return {
        "peril_rule": "mirror_eq",
        "default_currency": "JPY",
        "sitelim_rule": "repeat_whole",
        "country_default": "JP",
        "country_scheme_default": "ISO",
    }


def test_full_pipeline_passes_recon(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, _defaults())
    postal_lookup = {"100": {"prefecture": "Tokyo", "cresta": "JP_13"}}
    report, recon = run_all_checks(sample_sheets, out, postal_lookup=postal_lookup)
    assert report.passing, [(c.name, c.message) for c in report.checks if c.severity == "fail"]


def test_mapping_completeness_fails_on_blank_occtype(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, _defaults())
    out.loc[out.index[0], "OCCTYPE"] = ""
    check = check_mapping_completeness(out)
    assert check.severity == SEVERITY_FAIL


def test_count_reconciliation_fails_when_perturbed(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, _defaults())
    out.loc[out.index[0], "NUMBLDGS"] = int(out.loc[out.index[0], "NUMBLDGS"]) + 5
    check = check_count_reconciliation(sample_sheets["EXP_EQ"], out)
    assert check.severity == SEVERITY_FAIL


def test_tiv_recon_passes_after_split(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, _defaults())
    check, recon = check_tiv_reconciliation(sample_sheets["EXP_EQ"], out)
    assert check.severity == SEVERITY_PASS
    assert (recon["delta_BLDG"].abs() < 1).all()
