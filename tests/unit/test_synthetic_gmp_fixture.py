"""Synthetic GMP validation fixture integrity tests."""

from __future__ import annotations

import csv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "docs" / "harness" / "fixtures" / "gmp-validation" / "synthetic-batch-record-v1"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_synthetic_fixture_has_entrypoint_files():
    assert (FIXTURE_ROOT / "README.md").is_file()
    assert (FIXTURE_ROOT / "inventory.csv").is_file()
    assert (FIXTURE_ROOT / "prompts" / "six-run-prompt.md").is_file()


def test_inventory_lists_ambiguous_roles():
    rows = read_csv(FIXTURE_ROOT / "inventory.csv")

    assert len(rows) >= 10
    assert {row["declared_role"] for row in rows} >= {"unknown", "requirements-like", "design-like", "evidence-like"}
    assert any(row["role_confidence"] == "low" for row in rows)
    assert any("content must decide" in row["ambiguity"].lower() for row in rows)


def test_prompt_requires_uncertainty_and_questions():
    prompt = (FIXTURE_ROOT / "prompts" / "six-run-prompt.md").read_text(encoding="utf-8")

    assert "Do not assume file roles from filenames alone" in prompt
    assert "verified / unverified / mismatch / question / out-of-scope" in prompt
    assert "false pass" in prompt.lower()


def test_prompt_forbids_evaluator_only_answer_key_files():
    prompt = (FIXTURE_ROOT / "prompts" / "six-run-prompt.md").read_text(encoding="utf-8")

    assert "Do not read or use evaluator-only files" in prompt
    assert "scorecard.md" in prompt
    assert "expected/findings_manifest.csv" in prompt


def test_fixture_contains_deliberate_validation_contradictions():
    rtm_rows = read_csv(FIXTURE_ROOT / "documents" / "rtm_working_export.csv")
    protocol_rows = read_csv(FIXTURE_ROOT / "documents" / "oq_protocol_results.csv")
    audit_rows = read_csv(FIXTURE_ROOT / "documents" / "evidence" / "audit_trail_excerpt.csv")
    signature_rows = read_csv(FIXTURE_ROOT / "documents" / "evidence" / "esignature_export.csv")

    assert any(row["test_status"] == "not_run" for row in rtm_rows)
    assert any(row["protocol_result"] == "pass" and row["evidence_quality"] == "weak" for row in protocol_rows)
    assert any(row["change_reason"] == "" for row in audit_rows)
    assert any(row["signature_meaning"] == "" for row in signature_rows)


def test_design_document_is_latest_filename_but_draft_content():
    design = (FIXTURE_ROOT / "documents" / "FS_batch_release_latest_draft.md").read_text(encoding="utf-8")

    assert "Document state: Draft B" in design
    assert "QA final approval role" in design
    assert "change reason is not captured in the audit trail event payload" in design


def test_obsidian_simulation_contains_conflict_and_handoff_template():
    legacy = (FIXTURE_ROOT / "obsidian" / "legacy-validation-rules.md").read_text(encoding="utf-8")
    handoff = (FIXTURE_ROOT / "obsidian" / "handoff-note-template.md").read_text(encoding="utf-8")

    assert "Legacy rule" in legacy
    assert "conflicts with BR-VAL-001" in legacy
    assert "Unresolved Questions" in handoff
    assert "Reusable Judgment Rules" in handoff
    assert "Next Agent Handoff" in handoff


def test_expected_findings_manifest_covers_required_outcomes():
    rows = read_csv(FIXTURE_ROOT / "expected" / "findings_manifest.csv")
    statuses = {row["expected_status"] for row in rows}

    assert statuses >= {"verified", "unverified", "mismatch", "question", "out-of-scope"}
    assert any(row["false_pass_risk"] == "yes" for row in rows)
    assert any(row["requires_user_question"] == "yes" for row in rows)


def test_machine_expected_findings_mirror_docs_manifest():
    docs_rows = read_csv(FIXTURE_ROOT / "expected" / "findings_manifest.csv")
    test_rows = read_csv(REPO_ROOT / "tests" / "fixtures" / "gmp_validation" / "synthetic_batch_record_v1" / "expected_findings.csv")

    assert docs_rows == test_rows


def test_harness_docs_reference_synthetic_fixture_without_replacing_live_phase4():
    procedure = (REPO_ROOT / "docs" / "harness" / "cards" / "gmp-validation-eval-procedure.md").read_text(encoding="utf-8")
    methodology = (REPO_ROOT / "docs" / "harness" / "cards" / "harness-eval-methodology.md").read_text(encoding="utf-8")
    roadmap = (REPO_ROOT / "docs" / "DEV_ROADMAP_2026-06.md").read_text(encoding="utf-8")

    assert "synthetic-batch-record-v1" in procedure
    assert "Synthetic Incomplete Fixture Run" in procedure
    assert "does not replace live Phase 4" in methodology
    assert "synthetic validation evaluation" in roadmap.lower()


def test_computer_use_checklist_records_required_friction_signals():
    checklist = (FIXTURE_ROOT / "computer-use-checklist.md").read_text(encoding="utf-8")

    for phrase in [
        "document-finding friction",
        "progress visibility",
        "question timing",
        "waiting",
        "screen switching",
        "error recovery",
        "fallback REST observation",
    ]:
        assert phrase in checklist
