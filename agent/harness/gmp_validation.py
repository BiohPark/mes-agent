from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


REQUIRED_COLUMNS = {
    "requirement_id",
    "function_name",
    "gmp_impact",
    "approval_status",
    "expected_evidence",
}


@dataclass(frozen=True)
class GmpRequirement:
    requirement_id: str
    function_name: str
    gmp_impact: str
    approval_status: str
    expected_evidence: str

    def to_coverage_row(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "function_name": self.function_name,
            "gmp_impact": self.gmp_impact,
            "approval_status": self.approval_status,
            "expected_evidence": self.expected_evidence,
            "coverage_status": "unverified",
            "evidence": "",
            "questions": "",
        }


def load_requirements_csv(path: str | Path) -> list[GmpRequirement]:
    """Load the canonical non-sensitive GMP fixture CSV."""
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"Missing GMP requirement columns: {names}")
        rows = []
        for raw in reader:
            rows.append(GmpRequirement(
                requirement_id=(raw.get("requirement_id") or "").strip(),
                function_name=(raw.get("function_name") or "").strip(),
                gmp_impact=(raw.get("gmp_impact") or "").strip(),
                approval_status=(raw.get("approval_status") or "").strip(),
                expected_evidence=(raw.get("expected_evidence") or "").strip(),
            ))
    return rows
