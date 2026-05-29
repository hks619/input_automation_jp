"""Splitter tests — value- and count-preservation are the non-negotiable
correctness properties of the disaggregation engine.
"""
from __future__ import annotations

import math

from core.splitter import project_row_count, run_splitter


def test_building_count_is_preserved_exactly(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    expected = int(sample_sheets["EXP_EQ"]["NUMBLDGS"].sum())
    assert int(disagg["NUMBLDGS"].sum()) == expected


def test_tiv_is_preserved_within_tolerance(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    exp = sample_sheets["EXP_EQ"].iloc[0]
    for col, src in (("BLDG", "BLDG"), ("CONT", "CONT"), ("BI", "BI")):
        out_total = float(disagg[col].sum())
        in_total = float(exp[src])
        assert math.isclose(out_total, in_total, rel_tol=1e-9), f"{col} not preserved"


def test_row_count_matches_cross_product(sample_sheets):
    disagg, report = run_splitter(sample_sheets, pruning_threshold=0.0)
    # 2 * 2 * 2 * 2 = 16 combinations × 1 EXP row = 16 output rows.
    assert len(disagg) == 16
    assert report.output_row_count == 16


def test_project_row_count_matches_actual(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    assert project_row_count(sample_sheets) == len(disagg)


def test_rebasing_happens_when_occ_shares_not_normalized(sample_sheets):
    # Occ Pre_Rebased_Percentage sums to 100; force a rebase by changing it.
    sample_sheets["Occ"]["Pre_Rebased_Percentage"] = [80.0, 20.0]
    disagg, report = run_splitter(sample_sheets, pruning_threshold=0.0)
    # 80+20 = 100 → factor 100 logged.
    assert report.rebasing_factors.get(("Occ", "RESID")) == 100.0
    # Total still preserved.
    expected = float(sample_sheets["EXP_EQ"]["BLDG"].sum())
    assert math.isclose(float(disagg["BLDG"].sum()), expected, rel_tol=1e-9)


def test_pruning_redistributes_share(sample_sheets):
    # With a high threshold, some combinations should be pruned and their
    # share redistributed; TIV must still be preserved.
    disagg, report = run_splitter(sample_sheets, pruning_threshold=0.05)
    expected = float(sample_sheets["EXP_EQ"]["BLDG"].sum())
    assert math.isclose(float(disagg["BLDG"].sum()), expected, rel_tol=1e-9)
    # Combinations with proportion < 0.05 should be removed.
    assert (disagg["combo_proportion"] >= 0.05).all()
