"""Stage 3 — post-import franchise-deductible re-activation SQL.

After Data Bridge has imported the modified CEDE database into Risk Modeler,
we have to:
  1. Find the records flagged with the '_FR' suffix (carried through import).
  2. Re-activate the franchise deductible properly at site level — meaning
     flip the deductible-type back to FR in the EDM location table.
  3. Strip the '_FR' marker from the flag column.

The generated script targets the Risk Modeler EDM. Schema/column names vary
by EDM version; the function takes them as parameters with sensible defaults
matching common RMS EDM 2024 conventions.
"""
from __future__ import annotations

from typing import List


def generate_postimport_sql(
    edm_db_name: str,
    *,
    location_table: str = "Loc",
    ded_type_col: str = "DedType1",
    flag_col: str = "DedTxt1",
    flag_suffix: str = "_FR",
) -> List[str]:
    """Generate the post-import correction SQL block."""
    lines: List[str] = []
    lines.append("-- Stage 3 post-import franchise-deductible re-activation (auto-generated).")
    lines.append(f"USE [{edm_db_name}];")
    lines.append("GO")
    lines.append("BEGIN TRANSACTION;")
    lines.append("")
    lines.append("-- 1. Re-activate FR deductible type on rows that carry the marker.")
    lines.append(f"UPDATE l")
    lines.append(f"SET l.{ded_type_col} = 'FR',")
    lines.append(f"    l.{flag_col} = LEFT(l.{flag_col}, LEN(l.{flag_col}) - {len(flag_suffix)})")
    lines.append(f"FROM dbo.{location_table} l")
    lines.append(f"WHERE l.{flag_col} LIKE '%{flag_suffix}'")
    lines.append(f"  AND l.{ded_type_col} = 'S';")
    lines.append("")
    lines.append("-- 2. Sanity check — count flipped rows and verify no stray markers remain.")
    lines.append(f"DECLARE @flipped INT = @@ROWCOUNT;")
    lines.append(f"DECLARE @stray   INT = (SELECT COUNT(*) FROM dbo.{location_table} WHERE {flag_col} LIKE '%{flag_suffix}');")
    lines.append(f"PRINT CONCAT('FR rows reactivated: ', @flipped, '; stray _FR markers remaining: ', @stray);")
    lines.append("")
    lines.append("-- 3. Commit only if no stray markers remain.")
    lines.append("IF @stray = 0")
    lines.append("    COMMIT TRANSACTION;")
    lines.append("ELSE")
    lines.append("BEGIN")
    lines.append("    ROLLBACK TRANSACTION;")
    lines.append("    THROW 50001, 'Stray _FR markers detected — rolled back.', 1;")
    lines.append("END;")
    lines.append("GO")
    return lines
