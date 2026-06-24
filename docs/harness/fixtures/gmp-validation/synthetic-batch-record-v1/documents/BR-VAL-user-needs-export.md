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
