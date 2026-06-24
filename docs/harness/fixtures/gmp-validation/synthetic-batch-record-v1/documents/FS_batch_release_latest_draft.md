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
