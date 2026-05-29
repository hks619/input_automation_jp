"""Structured audit log.

Every transformation, mapping confirmation, rebasing factor, prune event,
validation override, and CEDE module action gets appended here. The log is
exportable as both human-readable Markdown and machine-readable JSON.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditEvent:
    timestamp: str
    category: str  # upload | mapping | rebase | prune | default | override | cede | output | validation
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditLog:
    events: List[AuditEvent] = field(default_factory=list)

    def add(self, category: str, message: str, **details: Any) -> None:
        self.events.append(AuditEvent(_utcnow(), category, message, details))

    # Convenience helpers used throughout the app.
    def upload(self, filename: str, content: bytes) -> None:
        self.add("upload", f"Template uploaded: {filename}",
                 sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content))

    def mapping(self, raw_value: str, mapped_to: str, confirmed_by: str) -> None:
        self.add("mapping", f"Mapping confirmed: {raw_value!r} → {mapped_to!r}",
                 confirmed_by=confirmed_by)

    def rebase(self, sheet: str, lob: str, factor: float) -> None:
        self.add("rebase", f"Rebased {sheet} for LOB={lob}",
                 factor=factor)

    def prune(self, n_combinations: int, share_redistributed: float, threshold: float) -> None:
        self.add("prune", f"Pruned {n_combinations} combinations below threshold {threshold}",
                 share_redistributed=share_redistributed, threshold=threshold)

    def default(self, key: str, value: Any) -> None:
        self.add("default", f"Applied default for {key}", value=value)

    def override(self, reason: str, by: str) -> None:
        self.add("override", f"Validation override: {reason}", by=by)

    def cede(self, action: str, **details: Any) -> None:
        self.add("cede", action, **details)

    def output(self, n_rows: int, filename: str) -> None:
        self.add("output", f"Generated output: {filename}", row_count=n_rows)

    def validation(self, check: str, status: str, **details: Any) -> None:
        self.add("validation", f"{check}: {status}", **details)

    # ------------------------------------------------------------------ export
    def to_json(self) -> str:
        return json.dumps([asdict(e) for e in self.events], indent=2)

    def to_markdown(self) -> str:
        lines = ["# Audit Log", "", f"_Exported {_utcnow()}_", "", f"**{len(self.events)} events**", ""]
        for e in self.events:
            lines.append(f"- `{e.timestamp}` **[{e.category}]** {e.message}")
            for k, v in e.details.items():
                lines.append(f"    - {k}: `{v}`")
        return "\n".join(lines)

    def to_zip(
        self,
        output_txt: bytes,
        recon_report: str,
        output_txt_filename: str = "exposure.txt",
    ) -> bytes:
        """Bundle the output txt + this audit log + the reconciliation report."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(output_txt_filename, output_txt)
            z.writestr("audit_log.json", self.to_json())
            z.writestr("audit_log.md", self.to_markdown())
            z.writestr("reconciliation_report.md", recon_report)
        return buf.getvalue()
