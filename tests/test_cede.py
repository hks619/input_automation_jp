"""CEDE module tests — covers the franchise-deductible transformations and
the SQL generators."""
from __future__ import annotations

import pandas as pd

from core.cede.backup import generate_backup_sql
from core.cede.postimport_sql import generate_postimport_sql
from core.cede.preprocess import preprocess_cede


def _loc():
    return pd.DataFrame([
        {"LocID": 1, "PortNum": 1, "AccGrpID": 1, "DedType1": "FR",
         "DedAmt1": 1_000_000, "DedCur1": "JPY", "DedTxt1": ""},
        {"LocID": 2, "PortNum": 1, "AccGrpID": 1, "DedType1": "S",
         "DedAmt1": 0, "DedCur1": "JPY", "DedTxt1": ""},
        {"LocID": 3, "PortNum": 1, "AccGrpID": 1, "DedType1": "FR",
         "DedAmt1": 500_000, "DedCur1": "JPY", "DedTxt1": "note"},
    ])


def test_fr_rows_are_flagged_and_switched_to_S():
    loc, loss, report = preprocess_cede(_loc(), loss_df=None, cedent_id="TEST")
    assert report.franchise_rows_flagged == 2
    assert report.franchise_rows_converted_to_S == 2
    # Marker appended.
    flagged = loc[loc["DedType1"] == "S"]
    fr_marker_rows = flagged[flagged["DedTxt1"].str.endswith("_FR")]
    assert len(fr_marker_rows) == 2
    # Existing text preserved.
    note_row = loc[(loc["LocID"] == 3)]
    assert note_row["DedTxt1"].iloc[0] == "note_FR"


def test_dummy_loss_added_when_loss_table_missing():
    _, loss, report = preprocess_cede(_loc(), loss_df=None, cedent_id="TEST")
    assert report.dummy_loss_row_added is True
    assert len(loss) == 1
    assert loss["LossAmt"].iloc[0] == 0.0


def test_no_dummy_loss_when_loss_table_provided():
    loss_in = pd.DataFrame([{"LossID": "L1", "PortNum": 1, "AccGrpID": 1, "LossAmt": 1.0}])
    _, loss_out, report = preprocess_cede(_loc(), loss_df=loss_in, cedent_id="TEST")
    assert report.dummy_loss_row_added is False
    assert len(loss_out) == 1


def test_backup_sql_includes_db_and_timestamped_file():
    sql = "\n".join(generate_backup_sql("CEDE_X", r"C:\Backups\CEDE", suffix="CED-1"))
    assert "BACKUP DATABASE [CEDE_X]" in sql
    assert ".bak" in sql
    assert "CED-1" in sql


def test_postimport_sql_flips_fr_and_strips_marker():
    sql = "\n".join(generate_postimport_sql("EDM_Prod"))
    assert "USE [EDM_Prod]" in sql
    assert "SET l.DedType1 = 'FR'" in sql
    assert "_FR" in sql
    assert "ROLLBACK" in sql  # transactional safety
