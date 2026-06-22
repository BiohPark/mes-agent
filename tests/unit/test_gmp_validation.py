"""GMP validation fixture parsing tests."""

from pathlib import Path

from agent.harness.gmp_validation import load_requirements_csv


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "gmp_function_spec_sample.csv"


def test_fixture_loads_requirement_rows():
    requirements = load_requirements_csv(FIXTURE)

    assert [r.requirement_id for r in requirements] == ["REQ-GMP-001", "REQ-GMP-002", "REQ-GMP-003"]
    assert requirements[0].function_name == "Audit trail review"
    assert requirements[0].gmp_impact == "High"
    assert requirements[0].approval_status == "Approved"
    assert requirements[0].expected_evidence == "RunLedger entry and Obsidian review note"


def test_fixture_rows_can_be_rendered_as_coverage_matrix():
    rows = [r.to_coverage_row() for r in load_requirements_csv(FIXTURE)]

    assert rows[0] == {
        "requirement_id": "REQ-GMP-001",
        "function_name": "Audit trail review",
        "gmp_impact": "High",
        "approval_status": "Approved",
        "expected_evidence": "RunLedger entry and Obsidian review note",
        "coverage_status": "unverified",
        "evidence": "",
        "questions": "",
    }
