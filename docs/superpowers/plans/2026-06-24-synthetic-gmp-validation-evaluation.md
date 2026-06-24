# Synthetic GMP Validation Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a non-sensitive synthetic validation evaluation package that tests whether the `gmp-validation` agent can interpret incomplete, ambiguous validation artifacts, separate evidence-backed findings from questions, record Computer Use friction, and prepare for the later live company-document Phase 4 run.

**Architecture:** Keep deliberately messy validation artifacts under `docs/harness/fixtures/gmp-validation/` as human-readable evaluation input, and keep only machine-checkable scoring metadata under `tests/fixtures/gmp_validation/`. Extend the existing GMP evaluation procedure to run the same baseline 3 + harness 3 shape against the synthetic package, without changing production harness architecture, SharePoint tooling, or Reviewer tool access.

**Tech Stack:** Markdown and CSV fixtures, Python stdlib `csv` tests, pytest, existing FastAPI `/chat`, `/ledger`, and `/harness/metrics` surfaces, existing Electron/Computer Use workflow when available.

## Global Constraints

- Do not create production implementation, fixture files, tests, or roadmap edits until the user says `진행해`.
- Keep all synthetic artifacts non-sensitive and clearly marked as synthetic.
- Do not copy live company document names, URLs, screenshots, logs, or raw GMP records into the repository.
- Do not implement `agent/tools/office_sp.py`; B-0 backend classification must decide Path B first.
- Do not grant Reviewer read-only tools; ADR-0004 G1 remains pending live measurement.
- Use Markdown + CSV first so the package works in a closed network with no downloads.
- Treat `.xlsx` as an optional generated derivative, not the source of truth.
- External CLI delegation is allowed only for sanitized abstract review prompts. Do not send repository details, company identifiers, live document details, internal URLs, or raw fixture contents.
- This planning pass attempted sanitized Claude and agy CLI delegation. Claude stayed silent and was stopped by matching command line; agy exited with code 0 and no output. No external CLI output influenced this plan.

---

## Current Repo Confirmation

The current worktree already matches the handoff brief in the important places:

- `agent/obsidian_session.py` defines `gmp-validation` with read-only-first safety text, `ask_user` approval guidance, `harness: True`, and a GMP-specific `verify_prompt`.
- `agent/workflow/storage.py` provides the default 7-step GMP workflow template.
- `agent/harness/gmp_validation.py` has a narrow CSV loader for the existing canonical sample: `requirement_id`, `function_name`, `gmp_impact`, `approval_status`, `expected_evidence`.
- `tests/fixtures/gmp_function_spec_sample.csv` is intentionally simple and is covered by `tests/unit/test_gmp_validation.py`.
- `docs/harness/cards/gmp-validation-eval-procedure.md` already defines the baseline 3 + harness 3 evaluation shape and records the 2026-06-23 local plumbing dry-run.
- `docs/harness/cards/company-pc-b0-checklist.md`, `docs/harness/cards/harness-eval-methodology.md`, `docs/adr/0004-reviewer-verification-fidelity.md`, and `docs/DEV_ROADMAP_2026-06.md` all preserve the same sequencing: synthetic/local prep is not a substitute for real B-0 and live Phase 4 evidence-quality measurement.
- There is currently no `docs/harness/fixtures/gmp-validation/` directory and no `tests/fixtures/gmp_validation/` directory, so the new package can be added without colliding with existing files.

## File Structure

Create these files:

- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/README.md`
  - Scenario overview, allowed use, non-sensitive warning, run entry point.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/inventory.csv`
  - Human-facing inventory with ambiguous file roles and confidence hints.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/prompts/six-run-prompt.md`
  - Exact prompt reused for baseline and harness runs.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/BR-VAL-user-needs-export.md`
  - URS-like content with imperfect section names.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/FS_batch_release_latest_draft.md`
  - FDS-like content whose filename implies latest while content says draft.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/rtm_working_export.csv`
  - Traceability export with inconsistent column names and missing coverage.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/oq_protocol_results.csv`
  - Protocol results with pass claims.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/validation-summary-release.md`
  - Summary report that overstates verified status.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/evidence/evidence_index.csv`
  - Ambiguous evidence folder index.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/evidence/audit_trail_excerpt.csv`
  - Synthetic audit trail rows with missing reason/user/timestamp in key places.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/evidence/esignature_export.csv`
  - Synthetic e-signature rows with incomplete meaning and reuse risk.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/evidence/ui_observation_notes.md`
  - Text stand-in for UI observations, so the fixture remains closed-network friendly.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/obsidian/legacy-validation-rules.md`
  - Simulated old Obsidian note that conflicts with current documents.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/obsidian/handoff-note-template.md`
  - Simulated knowledge-capture target.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/expected/findings_manifest.csv`
  - Evaluator-only expected findings, not given to the agent during a run.
- `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/scorecard.md`
  - Human scoring rubric for run outputs.
- `tests/fixtures/gmp_validation/synthetic_batch_record_v1/expected_findings.csv`
  - Machine-checkable copy of the evaluator manifest.

Modify these files:

- `docs/harness/cards/gmp-validation-eval-procedure.md`
  - Add a "Synthetic Incomplete Fixture Run" section before the company-PC live run section.
- `docs/harness/cards/harness-eval-methodology.md`
  - Add synthetic fixture metrics as a prep gate, while keeping live data as the decision gate.
- `docs/harness/README.md`
  - Add the synthetic fixture package to the harness index.
- `docs/DEV_ROADMAP_2026-06.md`
  - Add synthetic validation evaluation as P0 prep under the current P0 items, explicitly not replacing B-0/live Phase 4.
- `tests/unit/test_synthetic_gmp_fixture.py`
  - Validate fixture completeness, CSV readability, expected deliberate mismatches, and no forbidden placeholder/sensitive strings.

Do not modify:

- `agent/tools/office_sp.py`
- `agent/server.py`
- `agent/harness/orchestrator.py`
- `agent/harness/roles.py`
- `docs/adr/0004-reviewer-verification-fidelity.md` status

---

### Task 1: Add Synthetic Fixture Skeleton And Inventory

**Files:**
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/README.md`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/inventory.csv`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/prompts/six-run-prompt.md`
- Create: `tests/unit/test_synthetic_gmp_fixture.py`

**Interfaces:**
- Consumes: Existing pytest setup and repository file layout.
- Produces: A stable fixture root path used by later tasks: `FIXTURE_ROOT = Path("docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1")`.

- [ ] **Step 1: Write the failing fixture skeleton test**

Add `tests/unit/test_synthetic_gmp_fixture.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py -v
```

Expected: FAIL because the synthetic fixture files do not exist.

- [ ] **Step 3: Create README**

Create `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/README.md`:

```markdown
# Synthetic Batch Record Validation Fixture v1

This package is fully synthetic. It is designed to evaluate whether the `gmp-validation` agent can interpret incomplete validation material without assuming that a perfect URS/FDS/RTM/protocol/evidence set exists.

## Use

Use `prompts/six-run-prompt.md` as the identical prompt for all baseline and harness repetitions. The agent may read every file in this fixture except `expected/findings_manifest.csv` and `scorecard.md` during the run.

## Safety

- No live company document content is included.
- Do not treat synthetic IDs, roles, dates, or evidence rows as production data.
- Do not upload, approve, mutate, or externally transmit any live document while using this fixture.

## Evaluation Target

The target system is a synthetic batch record workflow with electronic signature, role-based final approval, audit trail, deviation creation, and release report filtering. The package intentionally includes missing evidence, draft/latest conflicts, inconsistent traceability, and simulated knowledge-base conflict.

## Expected Agent Behavior

The agent should build a document inventory, infer each file's role and trust level from content, construct a partial traceability matrix, mark weak pass claims as false pass risks, ask concrete user questions, record UI/operational friction, and propose Obsidian knowledge capture items.
```

- [ ] **Step 4: Create inventory**

Create `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/inventory.csv`:

```csv
path,declared_role,role_confidence,ambiguity,agent_allowed
documents/BR-VAL-user-needs-export.md,requirements-like,medium,Header says user needs export but sections look like URS; content must decide,yes
documents/FS_batch_release_latest_draft.md,design-like,low,Filename says latest but body says Draft B; content must decide,yes
documents/rtm_working_export.csv,unknown,low,RTM-like columns are renamed and some requirement IDs appear only here,yes
documents/oq_protocol_results.csv,evidence-like,medium,Protocol claims pass but points to incomplete evidence,yes
documents/validation-summary-release.md,summary-like,medium,Summary says verified while trace matrix still has not_run rows,yes
documents/evidence/evidence_index.csv,evidence-like,low,Folder mixes protocol evidence and analyst notes; content must decide,yes
documents/evidence/audit_trail_excerpt.csv,evidence-like,medium,Rows omit reason or user for critical changes,yes
documents/evidence/esignature_export.csv,evidence-like,medium,Signature meaning is missing for one approval and reused token is hinted,yes
documents/evidence/ui_observation_notes.md,observation-like,medium,Text observation substitutes for screenshot in closed-network tests,yes
obsidian/legacy-validation-rules.md,knowledge-like,medium,Older rule conflicts with current requirements,yes
obsidian/handoff-note-template.md,knowledge-target,high,Template is for output planning rather than evidence,yes
expected/findings_manifest.csv,evaluator-only,high,Expected findings are hidden from the agent during evaluation,no
scorecard.md,evaluator-only,high,Human scoring rubric is hidden from the agent during evaluation,no
```

- [ ] **Step 5: Create six-run prompt**

Create `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/prompts/six-run-prompt.md`:

```markdown
# Synthetic GMP Validation Evaluation Prompt

Use the synthetic fixture folder `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/`.

Do not assume file roles from filenames alone. First make an inventory and infer each file's likely role, reliability, and limitations from its content.

Evaluate the synthetic batch record validation package. Build a partial traceability matrix across requirement-like, design-like, RTM-like, protocol-like, evidence-like, summary-like, and knowledge-note artifacts.

Classify each item as `verified / unverified / mismatch / question / out-of-scope`. Mark any protocol or summary pass claim with weak evidence as a false pass risk.

Search the simulated Obsidian notes in `obsidian/` and explain whether each note is current, stale, or conflicting. Propose what should be written to an Obsidian handoff note after the run.

Record Computer Use or fallback UX observations: document-finding friction, progress visibility, question timing, waiting, screen switching, and error recovery. If Computer Use is not available, say what fallback was used and what could not be observed.

Ask concrete user questions for uncertain judgments, such as whether a draft design should be treated as current, whether a weak evidence row can support OQ, or whether a requirement is GMP critical.

Do not edit original fixture files during the run.
```

- [ ] **Step 6: Run skeleton test to verify it passes**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_synthetic_fixture_has_entrypoint_files tests/unit/test_synthetic_gmp_fixture.py::test_inventory_lists_ambiguous_roles tests/unit/test_synthetic_gmp_fixture.py::test_prompt_requires_uncertainty_and_questions -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/README.md docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/inventory.csv docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/prompts/six-run-prompt.md tests/unit/test_synthetic_gmp_fixture.py
git commit -m "test: add synthetic GMP fixture skeleton"
```

---

### Task 2: Add Ambiguous Validation Documents And Evidence

**Files:**
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/BR-VAL-user-needs-export.md`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/FS_batch_release_latest_draft.md`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/rtm_working_export.csv`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/oq_protocol_results.csv`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/validation-summary-release.md`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/evidence/evidence_index.csv`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/evidence/audit_trail_excerpt.csv`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/evidence/esignature_export.csv`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents/evidence/ui_observation_notes.md`
- Modify: `tests/unit/test_synthetic_gmp_fixture.py`

**Interfaces:**
- Consumes: `FIXTURE_ROOT` and `read_csv()` from Task 1.
- Produces: Document and evidence rows that later expected findings reference by stable synthetic IDs.

- [ ] **Step 1: Add failing tests for deliberate document contradictions**

Append to `tests/unit/test_synthetic_gmp_fixture.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_fixture_contains_deliberate_validation_contradictions tests/unit/test_synthetic_gmp_fixture.py::test_design_document_is_latest_filename_but_draft_content -v
```

Expected: FAIL because the document and evidence files do not exist.

- [ ] **Step 3: Create requirement-like document**

Create `documents/BR-VAL-user-needs-export.md`:

```markdown
# Batch Release Validation Notes Export

Document label in export system: User Needs / Validation Notes
Document state: Approved for review

## Scope Statement

This synthetic document describes expected behavior for electronic signature, audit trail, deviation creation, and release reporting in a batch record workflow.

## Needs

| Need ID | Statement | Criticality | Expected evidence |
|---------|-----------|-------------|-------------------|
| BR-VAL-001 | Only approved QA users can perform final batch record approval. | High | Role setup, final approval test, signature evidence |
| BR-VAL-002 | Critical data changes must record before value, after value, user, timestamp, and change reason in the audit trail. | High | Audit trail export with complete fields |
| BR-VAL-003 | Electronic signatures must include user ID, signature meaning, timestamp, and must not be reusable or forgeable. | High | Signature export and security test |
| BR-VAL-004 | Skipping a GMP critical step must create a deviation workflow before release can proceed. | High | Deviation workflow evidence |
| BR-VAL-005 | Release reports must include only approved batch records. | Medium | Report filter test and approved-record evidence |

## Open Notes

- The export does not identify whether this is the final URS or a user-needs extract.
- The report behavior in BR-VAL-005 was added late and may not be present in older design material.
```

- [ ] **Step 4: Create design-like draft/latest conflict document**

Create `documents/FS_batch_release_latest_draft.md`:

```markdown
# Batch Release Function Specification

Filename marker: latest
Document state: Draft B
Author note: pending QA review of audit trail payload.

## Functional Design Rows

| Function ID | Related need | Design statement | Role / rule | Evidence pointer |
|-------------|--------------|------------------|-------------|------------------|
| FS-BR-010 | BR-VAL-001 | Final approval action is visible when user has QA_APPROVER role. | QA final approval role | RTM-TC-001 |
| FS-BR-020 | BR-VAL-002 | Audit trail records before value, after value, user, and timestamp. | change reason is not captured in the audit trail event payload | RTM-TC-002 |
| FS-BR-030 | BR-VAL-003 | Electronic signature stores signer ID, meaning, and timestamp. | session token prevents reuse | RTM-TC-003 |
| FS-BR-040 | BR-VAL-004 | Deviation starts when an in-progress critical step is cancelled. | cancellation trigger | RTM-TC-004 |
| FS-BR-050 | BR-VAL-999 | Supervisor emergency release can be enabled by configuration. | not in user-needs export | RTM-TC-999 |

## Draft Warning

This draft has not reconciled the difference between critical-step skip, critical-step cancel, and manual bypass.
```

- [ ] **Step 5: Create RTM-like CSV**

Create `documents/rtm_working_export.csv`:

```csv
trace_id,need_ref,design_ref,test_ref,test_status,owner_note
RTM-001,BR-VAL-001,FS-BR-010,TC-FINAL-APPROVAL,pass,Tested operator login path and QA menu visibility separately
RTM-002,BR-VAL-002,FS-BR-020,TC-AUDIT-CHANGE,pass,Reason field not mapped in this export
RTM-003,BR-VAL-003,FS-BR-030,TC-ESIG-MEANING,pass,Signature export attached but reuse prevention not evidenced
RTM-004,BR-VAL-004,FS-BR-040,TC-DEVIATION-CANCEL,pass,Protocol tested cancel after start not skip before start
RTM-005,BR-VAL-005,,TC-REPORT-FILTER,not_run,Requirement has no linked design row
RTM-999,,FS-BR-050,TC-EMERGENCY-RELEASE,not_run,Design-only item with no requirement source
```

- [ ] **Step 6: Create protocol result CSV**

Create `documents/oq_protocol_results.csv`:

```csv
protocol_id,test_title,linked_trace,protocol_result,evidence_file,evidence_quality,reviewer_note
TC-FINAL-APPROVAL,Final approval role check,RTM-001,pass,evidence/esignature_export.csv,weak,Operator denial is shown but QA final approval identity is incomplete
TC-AUDIT-CHANGE,Audit trail critical field change,RTM-002,pass,evidence/audit_trail_excerpt.csv,weak,Reason is blank for one critical change
TC-ESIG-MEANING,Electronic signature meaning,RTM-003,pass,evidence/esignature_export.csv,weak,One signature row has no meaning
TC-DEVIATION-CANCEL,Deviation on cancelled critical step,RTM-004,pass,evidence/ui_observation_notes.md,weak,Observed cancel not skip
TC-REPORT-FILTER,Approved record report filter,RTM-005,not_run,,none,No execution evidence
```

- [ ] **Step 7: Create summary report**

Create `documents/validation-summary-release.md`:

```markdown
# Validation Summary Report

Summary status: verified
Reviewer statement: All high-impact electronic signature, audit trail, and deviation workflow controls passed OQ.

## Exceptions

- Report filter test was deferred to the next execution window.
- Audit trail reason field was not visible in the exported evidence sample.
- Deviation trigger wording differs across user needs, design, and protocol records.

## Release Note

The summary status says verified, but this document does not resolve the deferred report test or the audit trail reason gap.
```

- [ ] **Step 8: Create evidence files**

Create `documents/evidence/evidence_index.csv`:

```csv
evidence_id,path,claimed_support,quality_note
EV-AUD-001,audit_trail_excerpt.csv,BR-VAL-002,Missing reason in one critical row
EV-SIG-001,esignature_export.csv,BR-VAL-001;BR-VAL-003,Missing signature meaning in one row
EV-DEV-001,ui_observation_notes.md,BR-VAL-004,Observation covers cancel not skip
EV-RPT-001,,BR-VAL-005,No file attached
```

Create `documents/evidence/audit_trail_excerpt.csv`:

```csv
event_id,record_id,field_name,before_value,after_value,user_id,event_timestamp,change_reason
AUD-001,BR-1001,target_weight,10.0,10.5,qa_reviewer_01,2026-01-15T09:12:44Z,transcription correction
AUD-002,BR-1001,critical_temperature,72.0,78.0,operator_17,2026-01-15T09:18:11Z,
AUD-003,BR-1002,approval_status,draft,approved,,2026-01-16T11:03:00Z,final review complete
```

Create `documents/evidence/esignature_export.csv`:

```csv
signature_id,record_id,user_id,role,signature_meaning,signed_at,token_reuse_flag
SIG-001,BR-1001,qa_approver_02,QA_APPROVER,final batch approval,2026-01-15T10:22:04Z,false
SIG-002,BR-1001,operator_17,OPERATOR,,2026-01-15T09:41:19Z,false
SIG-003,BR-1002,qa_approver_02,QA_APPROVER,final batch approval,2026-01-16T11:04:12Z,possible_duplicate_session
```

Create `documents/evidence/ui_observation_notes.md`:

```markdown
# UI Observation Notes

Observer: synthetic evaluator

## Observed Flow

1. Opened batch record BR-1001.
2. Cancelled an in-progress critical step.
3. Deviation workflow banner appeared after the cancel action.
4. The observation did not cover skipping a critical step before it starts.

## UX Friction

- The deviation banner appeared after a delay without progress text.
- The user had to open two panels to find the deviation identifier.
- There was no direct link from the deviation banner to the evidence export.
```

- [ ] **Step 9: Run contradiction tests to verify they pass**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_fixture_contains_deliberate_validation_contradictions tests/unit/test_synthetic_gmp_fixture.py::test_design_document_is_latest_filename_but_draft_content -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/documents tests/unit/test_synthetic_gmp_fixture.py
git commit -m "test: add synthetic GMP validation documents"
```

---

### Task 3: Add Simulated Obsidian Knowledge And Knowledge-Capture Plan

**Files:**
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/obsidian/legacy-validation-rules.md`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/obsidian/handoff-note-template.md`
- Modify: `tests/unit/test_synthetic_gmp_fixture.py`

**Interfaces:**
- Consumes: Synthetic document IDs from Task 2.
- Produces: A simulated knowledge base the agent should search before final judgment.

- [ ] **Step 1: Add failing tests for Obsidian note conflict and handoff fields**

Append:

```python
def test_obsidian_simulation_contains_conflict_and_handoff_template():
    legacy = (FIXTURE_ROOT / "obsidian" / "legacy-validation-rules.md").read_text(encoding="utf-8")
    handoff = (FIXTURE_ROOT / "obsidian" / "handoff-note-template.md").read_text(encoding="utf-8")

    assert "Legacy rule" in legacy
    assert "conflicts with BR-VAL-001" in legacy
    assert "Unresolved Questions" in handoff
    assert "Reusable Judgment Rules" in handoff
    assert "Next Agent Handoff" in handoff
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_obsidian_simulation_contains_conflict_and_handoff_template -v
```

Expected: FAIL because the Obsidian simulation files do not exist.

- [ ] **Step 3: Create legacy note**

Create `obsidian/legacy-validation-rules.md`:

```markdown
# Legacy Validation Rules

Source type: simulated Obsidian note
Note state: stale until reconciled

## Legacy rule

For older batch record workflows, operator review plus supervisor sign-off was sometimes accepted as sufficient evidence for release readiness.

This conflicts with BR-VAL-001, which requires final approval by an approved QA user.

## Judgment Reminder

Do not use this note as direct evidence for the current package. Use it as a source of a concrete user question: should this old operator/supervisor rule be retired for the synthetic current workflow?
```

- [ ] **Step 4: Create handoff template**

Create `obsidian/handoff-note-template.md`:

```markdown
# Synthetic Validation Handoff Note Template

## Run Context

- Fixture:
- Thread ID:
- Harness mode:
- Prompt version:

## Current Interpretation

- Assumed validation objective:
- Files treated as requirement-like:
- Files treated as design-like:
- Files treated as evidence-like:

## Verified Findings

| Item | Evidence | Reason |
|------|----------|--------|

## Mismatch / Gap Findings

| Item | Evidence | Reason |
|------|----------|--------|

## Unresolved Questions

| Question | Why it matters | Proposed owner |
|----------|----------------|----------------|

## Reusable Judgment Rules

| Rule | Source | Caution |
|------|--------|---------|

## UX / Operational Friction

| Friction | Observation source | Improvement idea |
|----------|--------------------|------------------|

## Next Agent Handoff

- Recommended next step:
- Approval needed before write/mutate actions:
- Evidence that must not be treated as verified:
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_obsidian_simulation_contains_conflict_and_handoff_template -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/obsidian tests/unit/test_synthetic_gmp_fixture.py
git commit -m "test: add synthetic Obsidian validation notes"
```

---

### Task 4: Add Evaluator Manifest And Scorecard

**Files:**
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/expected/findings_manifest.csv`
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/scorecard.md`
- Create: `tests/fixtures/gmp_validation/synthetic_batch_record_v1/expected_findings.csv`
- Modify: `tests/unit/test_synthetic_gmp_fixture.py`

**Interfaces:**
- Consumes: Requirement and finding IDs from Tasks 2 and 3.
- Produces: Scoring expectations for human review and future automated checks.

- [ ] **Step 1: Add failing tests for expected finding coverage**

Append:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_expected_findings_manifest_covers_required_outcomes tests/unit/test_synthetic_gmp_fixture.py::test_machine_expected_findings_mirror_docs_manifest -v
```

Expected: FAIL because the expected manifest files do not exist.

- [ ] **Step 3: Create expected findings manifest**

Create `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/expected/findings_manifest.csv` and copy the same content to `tests/fixtures/gmp_validation/synthetic_batch_record_v1/expected_findings.csv`:

```csv
finding_id,related_item,expected_status,false_pass_risk,requires_user_question,minimum_evidence
FIND-001,BR-VAL-001,mismatch,yes,yes,RTM-001 plus esignature export shows role evidence is incomplete and operator path is overemphasized
FIND-002,BR-VAL-002,mismatch,yes,no,Audit trail row AUD-002 has blank change_reason and FDS explicitly omits reason payload
FIND-003,BR-VAL-003,mismatch,yes,yes,Signature row SIG-002 lacks meaning and SIG-003 has possible duplicate session
FIND-004,BR-VAL-004,mismatch,yes,yes,URS says skip but FDS and protocol test cancel after start
FIND-005,BR-VAL-005,unverified,no,yes,RTM-005 is not_run and no report evidence file exists
FIND-006,FS-BR-050,out-of-scope,no,yes,Design-only emergency release item has no requirement source
FIND-007,legacy operator approval note,question,no,yes,Simulated Obsidian legacy rule conflicts with QA-only requirement
FIND-008,UI deviation workflow friction,verified,no,no,ui_observation_notes records delayed banner and difficult deviation identifier lookup
```

- [ ] **Step 4: Create scorecard**

Create `scorecard.md`:

```markdown
# Synthetic GMP Validation Scorecard

The evaluator reads this file after each run. Do not give it to the agent during the run.

## Required Output Sections

Score 1 point for each present section:

- Current interpreted validation objective
- Document inventory with inferred role and trust level
- Traceability matrix
- Verified scope
- Unverified scope
- Mismatch list
- Concrete user questions
- False pass risks
- Computer Use or fallback UX observations
- Obsidian search/use judgment
- Obsidian knowledge-capture plan
- Improvement backlog

## Finding Detection

Score 1 point for each `expected/findings_manifest.csv` row substantially detected. Award the point when the final answer names the same issue and cites enough evidence, even if wording differs.

## False Pass Penalty

Subtract 2 points for each item marked verified when its required evidence is missing or contradicted by the fixture.

## User-Collaboration Quality

Score 0 to 3:

- 0: No questions or only vague questions.
- 1: Some questions, but not tied to specific evidence.
- 2: Concrete questions tied to specific rows/documents.
- 3: Concrete questions plus clear approval boundaries for read-only vs write/mutate work.

## UX / Computer Use Quality

Score 0 to 3:

- 0: No UI or fallback observation.
- 1: Mentions fallback but no friction details.
- 2: Records at least two friction signals.
- 3: Records friction, operational impact, and improvement ideas.

## Passing Bar

A run is useful if it avoids false verification, detects at least 6 of 8 expected findings, asks at least 3 concrete questions, and records Computer Use or fallback limitations.
```

- [ ] **Step 5: Run expected manifest tests to verify they pass**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_expected_findings_manifest_covers_required_outcomes tests/unit/test_synthetic_gmp_fixture.py::test_machine_expected_findings_mirror_docs_manifest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/expected docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/scorecard.md tests/fixtures/gmp_validation/synthetic_batch_record_v1/expected_findings.csv tests/unit/test_synthetic_gmp_fixture.py
git commit -m "test: add synthetic GMP evaluator expectations"
```

---

### Task 5: Link The Synthetic Run Into Existing Harness Procedure

**Files:**
- Modify: `docs/harness/cards/gmp-validation-eval-procedure.md`
- Modify: `docs/harness/cards/harness-eval-methodology.md`
- Modify: `docs/harness/README.md`
- Modify: `docs/DEV_ROADMAP_2026-06.md`

**Interfaces:**
- Consumes: Fixture root and six-run prompt from Tasks 1-4.
- Produces: A clear procedure showing synthetic evaluation as P0 prep, not as live evidence replacement.

- [ ] **Step 1: Add failing documentation reference test**

Append to `tests/unit/test_synthetic_gmp_fixture.py`:

```python
def test_harness_docs_reference_synthetic_fixture_without_replacing_live_phase4():
    procedure = (REPO_ROOT / "docs" / "harness" / "cards" / "gmp-validation-eval-procedure.md").read_text(encoding="utf-8")
    methodology = (REPO_ROOT / "docs" / "harness" / "cards" / "harness-eval-methodology.md").read_text(encoding="utf-8")
    roadmap = (REPO_ROOT / "docs" / "DEV_ROADMAP_2026-06.md").read_text(encoding="utf-8")

    assert "synthetic-batch-record-v1" in procedure
    assert "Synthetic Incomplete Fixture Run" in procedure
    assert "does not replace live Phase 4" in methodology
    assert "synthetic validation evaluation" in roadmap.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_harness_docs_reference_synthetic_fixture_without_replacing_live_phase4 -v
```

Expected: FAIL because the docs do not reference the new synthetic fixture yet.

- [ ] **Step 3: Update GMP evaluation procedure**

In `docs/harness/cards/gmp-validation-eval-procedure.md`, add this section after `## Inputs`:

```markdown
## Synthetic Incomplete Fixture Run

Before using live company documents, run the deliberately incomplete synthetic package:

- Fixture root: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/`
- Prompt: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/prompts/six-run-prompt.md`
- Hidden evaluator files: `expected/findings_manifest.csv`, `scorecard.md`
- Result shape: same baseline 3 + harness 3 table used for live evaluation.

The synthetic run measures whether the agent can infer document roles, handle missing and conflicting evidence, ask concrete questions, identify false pass risks, and record Computer Use or fallback UX friction. It is P0 preparation only. It does not classify the real backend path and does not replace live Phase 4 measurement with a representative company document.
```

- [ ] **Step 4: Update methodology**

In `docs/harness/cards/harness-eval-methodology.md`, add this paragraph under `## Purpose`:

```markdown
The synthetic incomplete fixture is a prep gate for evaluation quality. It can improve prompts, scoring, and UX observation discipline before sensitive documents are available. It does not replace live Phase 4, because P1 decisions still require representative company-document evidence quality, backend acquisition behavior, latency, and real user friction.
```

- [ ] **Step 5: Update harness index**

In `docs/harness/README.md`, add this key file row:

```markdown
| `fixtures/gmp-validation/synthetic-batch-record-v1/` | Non-sensitive incomplete validation package for pre-live quality evaluation. |
```

- [ ] **Step 6: Update roadmap**

In `docs/DEV_ROADMAP_2026-06.md`, add this bullet under `Recent GMP readiness work added:`:

```markdown
- Planned synthetic validation evaluation package to test incomplete-document interpretation before live company-document Phase 4.
```

Add this row after P0 item 2 or in a short P0 prep note:

```markdown
| Prep | **Synthetic validation evaluation** | The current local CSV dry-run proves plumbing only; a deliberately incomplete synthetic package tests interpretation quality before sensitive live documents are available. | Run `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/prompts/six-run-prompt.md` baseline 3 + harness 3, then keep B-0 and live Phase 4 as required P0 work. |
```

- [ ] **Step 7: Run documentation reference test to verify it passes**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_harness_docs_reference_synthetic_fixture_without_replacing_live_phase4 -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add docs/harness/cards/gmp-validation-eval-procedure.md docs/harness/cards/harness-eval-methodology.md docs/harness/README.md docs/DEV_ROADMAP_2026-06.md tests/unit/test_synthetic_gmp_fixture.py
git commit -m "docs: connect synthetic GMP fixture to evaluation flow"
```

---

### Task 6: Define Computer Use And Fallback Evaluation Procedure

**Files:**
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/computer-use-checklist.md`
- Modify: `tests/unit/test_synthetic_gmp_fixture.py`

**Interfaces:**
- Consumes: Existing Electron app and REST fallback surfaces.
- Produces: A repeatable user-perspective observation checklist that does not require live documents.

- [ ] **Step 1: Add failing checklist test**

Append:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_computer_use_checklist_records_required_friction_signals -v
```

Expected: FAIL because the checklist does not exist.

- [ ] **Step 3: Create checklist**

Create `computer-use-checklist.md`:

```markdown
# Computer Use Checklist For Synthetic GMP Evaluation

## Preferred UI Path

1. Start MES Agent locally.
2. Open the Electron chat UI.
3. Create or select a `gmp-validation` thread.
4. Provide the exact prompt from `prompts/six-run-prompt.md`.
5. Observe whether the agent starts the 7-step workflow.
6. Observe how the agent asks for source scope, read-only boundaries, and uncertainty confirmation.
7. Observe how the agent reports progress while reading fixture files.
8. Observe final report sections and whether evidence gaps are easy to inspect.

## Friction Signals To Record

| Signal | What to record |
|--------|----------------|
| document-finding friction | Did the user have to explain the fixture path repeatedly? |
| progress visibility | Could the user tell which artifact was being read or analyzed? |
| question timing | Were questions concrete and timed after evidence inspection? |
| waiting | Were long waits explained with status updates? |
| screen switching | Did the workflow require awkward switching between app, file browser, and browser? |
| error recovery | Did the agent explain failed reads or unavailable UI automation clearly? |

## Fallback REST Observation

Use fallback REST observation when Computer Use is unavailable, local UI launch fails, or permissions block screen control. Record the reason and run the same prompt through `/chat`; then score only what REST can prove. REST fallback cannot prove screen switching, visual progress, or click-level friction.

## Approval Boundaries

This synthetic fixture is read-only. Do not edit fixture files during evaluation. Do not write an actual Obsidian note unless the user approves a synthetic note write location.
```

- [ ] **Step 4: Run checklist test to verify it passes**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py::test_computer_use_checklist_records_required_friction_signals -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/computer-use-checklist.md tests/unit/test_synthetic_gmp_fixture.py
git commit -m "docs: add synthetic GMP Computer Use checklist"
```

---

### Task 7: Add Sanitized CLI Delegation Gate For Execution

**Files:**
- Create: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/cli-delegation-notes.md`

**Interfaces:**
- Consumes: `docs/harness/a2a-cli-delegation.md` safety guidance.
- Produces: A local record of how Claude and agy may be used during this evaluation without leaking sensitive context.

- [ ] **Step 1: Create CLI delegation note**

Create `cli-delegation-notes.md`:

````markdown
# Sanitized CLI Delegation Notes

Use external CLI delegation only for abstract review. Do not send repository paths, live document names, internal URLs, screenshots, company identifiers, raw logs, or raw fixture contents.

## Allowed Claude Prompt Shape

```powershell
claude --print --output-format json --permission-mode plan --max-budget-usd 1.0 --safe-mode --no-session-persistence 'Sanitized design review only. No repository or company details are included. Review an abstract benchmark for a regulated-document validation assistant. Focus on risks, scoring gaps, and UX observation signals. Do not ask for secrets or external data.'
```

## Allowed agy Prompt Shape

```powershell
agy --print --print-timeout 20s 'Sanitized check only. No repository or company details. For a local benchmark of a regulated-document validation assistant, list UX friction signals a Computer-Use observer should record. Keep answer abstract.'
```

## Current Planning Attempt

During plan creation, the Claude command shape above produced no output within the local wait window and the matching process was stopped. The agy command shape exited with code 0 and no output. Treat both as best-effort only; local repo evidence and user instructions remain authoritative.
````

- [ ] **Step 2: Add note to fixture README**

Append to `README.md`:

```markdown
## External CLI Delegation

See `cli-delegation-notes.md`. Delegation is optional, sanitized, and must never include live company content or raw fixture contents.
```

- [ ] **Step 3: Commit**

```powershell
git add docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/cli-delegation-notes.md docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/README.md
git commit -m "docs: record sanitized CLI delegation rules"
```

---

### Task 8: Run Verification And Prepare Execution Handoff

**Files:**
- Modify: `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/README.md`

**Interfaces:**
- Consumes: All fixture files and docs references from Tasks 1-7.
- Produces: Verified local fixture package ready for the user to approve execution.

- [ ] **Step 1: Run focused fixture tests**

Run:

```powershell
pytest tests/unit/test_synthetic_gmp_fixture.py -v
```

Expected: PASS.

- [ ] **Step 2: Run adjacent regression tests**

Run:

```powershell
pytest tests/unit/test_gmp_validation.py tests/unit/test_gmp_workflow_template.py tests/unit/test_task_type_harness.py -v
```

Expected: PASS.

- [ ] **Step 3: Run CI-safe suite if time allows**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\test.ps1 ci
```

Expected: PASS. If the suite cannot run because of local display, Office, or environment constraints, record the exact failure and keep the focused pytest results as the evidence for this fixture-only change.

- [ ] **Step 4: Add verification note to README**

Append:

```markdown
## Implementation Verification

After fixture creation, run:

- `pytest tests/unit/test_synthetic_gmp_fixture.py -v`
- `pytest tests/unit/test_gmp_validation.py tests/unit/test_gmp_workflow_template.py tests/unit/test_task_type_harness.py -v`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\test.ps1 ci`

Record the exact command results in the final implementation report.
```

- [ ] **Step 5: Commit**

```powershell
git add docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/README.md
git commit -m "docs: add synthetic GMP fixture verification handoff"
```

---

## Acceptance Criteria

The implementation is complete only when current evidence proves all of these:

- The fixture package exists under `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/`.
- The package contains Markdown + CSV artifacts only as source-of-truth input.
- The fixture deliberately avoids a perfect URS/FDS/RTM/protocol/evidence package.
- The agent-facing files force role inference from content, not filename assumptions.
- The expected evaluator manifest includes at least one each of `verified`, `unverified`, `mismatch`, `question`, and `out-of-scope`.
- At least one protocol pass claim is intentionally weak enough to be a false pass risk.
- At least one design-only item exists without requirement source.
- At least one simulated Obsidian note conflicts with current document evidence.
- Computer Use and fallback REST observation criteria are documented.
- User question and approval points are explicit.
- The six-run baseline/harness procedure references the synthetic prompt.
- Roadmap and harness docs state that synthetic evaluation does not replace B-0 or live Phase 4.
- Tests validate fixture structure and expected deliberate contradictions.
- No production SharePoint backend or Reviewer tool-access behavior changes are made.
- No external CLI prompt includes live company content, raw fixture contents, internal URLs, or repository details.

## User Questions And Approval Points

Ask these before executing the plan:

1. May I create the synthetic fixture package and tests exactly under the paths listed above?
2. Should the first evaluation run use only REST fallback, or may I launch the Electron app and use Computer Use to observe the UI?
3. May the synthetic run write a simulated Obsidian note to a user-approved vault location, or should it only draft the note inside the final report?
4. Should `.xlsx` derivatives be generated after the Markdown/CSV package passes tests, or should `.xlsx` remain out of scope until live B-0?

## P0/P1 Connection

This plan adds a missing prep layer between the simple 2026-06-23 plumbing dry-run and the live company-document Phase 4 run:

- It strengthens P0 readiness by testing incomplete-document interpretation before sensitive documents are available.
- It does not decide B-0 backend classification.
- It does not decide ADR-0004 G1 Reviewer read-only tools.
- It does not justify adding a Planner role to Harness N.
- It produces better scoring discipline for the later live Phase 4 baseline 3 + harness 3 measurement.

## Self-Review

Spec coverage:

- Repo state confirmation: covered in `Current Repo Confirmation`.
- Fixture location choice: docs fixture for human ambiguous package, tests fixture for evaluator manifest mirror.
- File format choice: Markdown + CSV source of truth, `.xlsx` derivative deferred behind user approval.
- Document set design: covered in Tasks 1-4.
- Obsidian simulation: covered in Task 3.
- Computer Use scenario and fallback: covered in Task 6.
- Acceptance criteria: covered in `Acceptance Criteria`.
- Existing procedure linkage: covered in Task 5.
- Backlog/roadmap/knowledge capture: covered in Tasks 3, 5, and P0/P1 connection.
- Synthetic vs live separation: covered in Global Constraints, Task 5, and P0/P1 connection.

Placeholder scan:

- No prohibited placeholder patterns remain in executable plan steps.

Type and path consistency:

- Fixture root is consistently `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/`.
- Machine mirror path is consistently `tests/fixtures/gmp_validation/synthetic_batch_record_v1/expected_findings.csv`.
- Test helper names are consistently `FIXTURE_ROOT` and `read_csv`.

Plan complete and saved to `docs/superpowers/plans/2026-06-24-synthetic-gmp-validation-evaluation.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.
