"""Round-trip test: template_builder → parser produces the expected sheets."""
from __future__ import annotations

from core.parser import parse_template
from core.schema import SHEETS
from core.template_builder import build_template


def test_template_roundtrip_has_all_required_sheets():
    parsed = parse_template(build_template())
    for spec in SHEETS:
        assert spec.name in parsed.sheets
    # The example rows are present so structural validation may flag required-
    # column nulls in some sheets where the example is None — but no sheet
    # should be entirely missing.
    error_sheets = {i.sheet for i in parsed.issues if i.severity == "error"}
    # Sheets that ONLY contain a sample row are valid structurally.
    assert "Account_Group" not in error_sheets
    assert "EXP_EQ" not in error_sheets
