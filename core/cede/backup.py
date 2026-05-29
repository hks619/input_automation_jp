"""Stage 2 — back up the modified CEDE database before Data Bridge import.

Generates SQL Server T-SQL backup statements. The analyst runs them; we don't
connect to the DB by default. If config/defaults.yaml: cede_live_db is true,
a future enhancement can pipe these through a read-only connection.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List


def generate_backup_sql(
    cede_db_name: str,
    backup_dir: str = r"C:\Backups\CEDE",
    *,
    suffix: str = "",
) -> List[str]:
    """Return a list of SQL Server BACKUP DATABASE statements.

    The default form takes a full backup with COMPRESSION + CHECKSUM. The file
    name embeds a UTC timestamp so multiple backups don't collide.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fname = f"{cede_db_name}_{stamp}{('_' + suffix) if suffix else ''}.bak"
    backup_path = f"{backup_dir.rstrip('/').rstrip(chr(92))}\\{fname}"
    return [
        "-- Stage 2 backup (auto-generated).",
        f"-- Take a full backup of [{cede_db_name}] before Data Bridge import.",
        f"BACKUP DATABASE [{cede_db_name}]",
        f"TO DISK = N'{backup_path}'",
        "WITH FORMAT, INIT, COMPRESSION, CHECKSUM,",
        f"NAME = N'{cede_db_name} pre-import backup {stamp}';",
    ]
