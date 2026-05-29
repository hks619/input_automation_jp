"""txt_writer tests — exact header order, tab separation, peril/currency rules."""
from __future__ import annotations

from core.schema import OUTPUT_HEADER
from core.splitter import run_splitter
from core.txt_writer import build_output_frame, to_tsv_bytes


def _defaults():
    return {
        "peril_rule": "mirror_eq",
        "default_currency": "JPY",
        "sitelim_rule": "repeat_whole",
        "country_default": "JP",
        "country_scheme_default": "ISO",
    }


def test_header_order_matches_spec(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, _defaults())
    assert tuple(out.columns) == OUTPUT_HEADER


def test_first_line_is_tab_separated_header(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, _defaults())
    data = to_tsv_bytes(out, line_ending="\n").decode("utf-8")
    first_line = data.split("\n", 1)[0]
    assert first_line == "\t".join(OUTPUT_HEADER)


def test_mirror_eq_peril_rule_copies_values(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, _defaults())
    assert (out["WSCV1VAL"] == out["EQCV1VAL"]).all()
    assert (out["WSCV2VAL"] == out["EQCV2VAL"]).all()
    assert (out["WSCV3VAL"] == out["EQCV3VAL"]).all()
    assert (out["WSSITELIM"] == out["EQSITELIM"]).all()


def test_blank_ws_peril_rule_zeros_ws(sample_sheets):
    d = _defaults() | {"peril_rule": "blank_ws"}
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, d)
    assert (out["WSCV1VAL"] == 0).all()


def test_currency_columns_populated(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, _defaults())
    for col in ("EQCV1VCUR", "EQSITELCUR", "WSCV1VCUR", "WSSITELCUR"):
        assert (out[col] == "JPY").all(), col


def test_sitelim_repeat_whole_is_not_divided(sample_sheets):
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, _defaults())
    expected = float(sample_sheets["EXP_EQ"]["SITELIM"].iloc[0])
    assert (out["EQSITELIM"] == expected).all()


def test_secondary_modifier_rule_matches(sample_sheets):
    rules = [{
        "occupancy_type": "311", "bldg_class": "311", "lobname": "*",
        "ENGFOUND": "Y", "STRUCTUP": "N", "IFMVERTICALEXPDIST": "M", "IFMEQUIPBRACING": "N",
    }]
    disagg, _ = run_splitter(sample_sheets, pruning_threshold=0.0)
    out = build_output_frame(disagg, _defaults(), secondary_rules=rules)
    # OCCTYPE=311 AND BLDGCLASS=311 rows should have ENGFOUND=Y.
    mask = (out["OCCTYPE"] == "311") & (out["BLDGCLASS"] == "311")
    assert mask.any()
    assert (out.loc[mask, "ENGFOUND"] == "Y").all()
    # Other rows should be blank.
    assert (out.loc[~mask, "ENGFOUND"] == "").all()
